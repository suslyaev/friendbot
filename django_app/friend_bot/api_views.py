from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from friend_bot.models import User, TelegramGroup, UserInGroup, Message, DailyCheckin, MessageTypePoints, Rank
from .serializers import IngestMessageSerializer
from datetime import timedelta
import os


class IngestMessageView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = IngestMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data['auth_token'] != settings.SECRET_KEY:
            return Response({'detail': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        # User
        user, _ = User.objects.get_or_create(
            telegram_id=data['user_telegram_id'],
            defaults={
                'first_name': data.get('user_first_name') or '',
                'last_name': data.get('user_last_name') or '',
                'username': data.get('user_username') or '',
                'is_active': True,
            }
        )
        # Update basic fields if changed
        changed = False
        for field, key in [('first_name','user_first_name'), ('last_name','user_last_name'), ('username','user_username')]:
            val = data.get(key)
            if val is not None and getattr(user, field) != val:
                setattr(user, field, val)
                changed = True
        if changed:
            user.save()

        # Group
        group, _ = TelegramGroup.objects.get_or_create(
            telegram_id=data['chat_telegram_id'],
            defaults={'title': data.get('chat_title') or f'Group {data["chat_telegram_id"]}', 'is_active': True}
        )
        if data.get('chat_title') and group.title != data['chat_title']:
            group.title = data['chat_title']
            group.save()

        # Link user in group and get/create UserInGroup
        user_in_group, _ = UserInGroup.objects.get_or_create(
            user=user, 
            group=group, 
            defaults={
                'is_active': True,
                'rating': 0,
                'message_count': 0,
                'coefficient': 0.5  # Начинаем с 0.5 для новых пользователей
            }
        )

        # Message
        msg, created = Message.objects.get_or_create(
            telegram_id=data['telegram_message_id'],
            chat=group,
            defaults={
                'date': data['date_iso'],
                'user': user,
                'message_type': data['message_type'],
                'text': data.get('text') or '',
                'related_message': data.get('related_telegram_message_id'),
            }
        )
        if not created:
            # idempotency update
            updated = False
            for field, key in [('message_type','message_type'), ('text','text')]:
                val = data.get(key)
                if val is not None and getattr(msg, field) != val:
                    setattr(msg, field, val)
                    updated = True
            if updated:
                msg.save()

        # Add message points to UserInGroup
        result = user_in_group.add_message_points(data['message_type'])
        
        # Check if this is the first message and assign initial rank
        if not user_in_group.rank:
            user_in_group.update_rank()
        
        # Если звание изменилось, отправляем уведомление в чат
        if result.get('rank_changed') and result.get('new_rank'):
            self._send_rank_notification(group, user, result['old_rank'], result['new_rank'])

        # DailyCheckin - используем timezone.now() для корректной работы с часовыми поясами
        checkin, created = DailyCheckin.objects.get_or_create(
            user=user, 
            group=group, 
            defaults={
                'consecutive_days': 0,  # Начинаем с 0 дней
                'last_checkin': timezone.now()  # Используем Django timezone.now() с учетом часового пояса
            }
        )
        if not created:
            # Используем московское время для корректного сравнения дат
            import pytz
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Конвертируем last_checkin в московское время
            if checkin.last_checkin.tzinfo is None:
                # Если время без часового пояса, считаем его UTC
                last_checkin_utc = pytz.utc.localize(checkin.last_checkin)
            else:
                last_checkin_utc = checkin.last_checkin
            last_checkin_moscow = last_checkin_utc.astimezone(moscow_tz)
            last_date = last_checkin_moscow.date()
            
            # Конвертируем текущее время в московское
            current_time = timezone.now()  # Используем Django timezone.now() вместо data['date_iso']
            if current_time.tzinfo is None:
                # Если время без часового пояса, считаем его UTC
                current_utc = pytz.utc.localize(current_time)
            else:
                current_utc = current_time
            current_moscow = current_utc.astimezone(moscow_tz)
            today = current_moscow.date()
            
            diff = (today - last_date).days
            print(f"🔍 DailyCheckin: last_date={last_date}, today={today}, diff={diff} дней")
            
            if diff == 1:
                checkin.consecutive_days += 1
                print(f"🔍 Увеличиваем consecutive_days до {checkin.consecutive_days}")
            elif diff > 1:
                checkin.consecutive_days = 0
                print(f"🔍 Сбрасываем consecutive_days (прошло {diff} дней)")
            elif diff == 0:
                print(f"🔍 Уже чекинились сегодня")
            else:
                print(f"🔍 Отрицательная разница дней: {diff} (возможно, проблема с часовыми поясами)")
            
            checkin.last_checkin = timezone.now()  # Используем Django timezone.now() с учетом часового пояса
            checkin.save()
        else:
            # Для нового пользователя оставляем consecutive_days = 0
            # Первый чекин не считается как "непрерывный день"
            print(f"🔍 Создан новый DailyCheckin для пользователя {user.first_name}")
            pass

        # Обновляем коэффициент на основе DailyCheckin
        try:
            checkin = DailyCheckin.objects.get(user=user, group=group)
            if checkin.consecutive_days == 0:
                user_in_group.coefficient = 0.5
            elif checkin.consecutive_days == 1:
                user_in_group.coefficient = 1.0
            else:
                user_in_group.coefficient = 1.0 + (checkin.consecutive_days - 1) * 0.1
            user_in_group.save()
        except DailyCheckin.DoesNotExist:
            pass

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    def _send_rank_notification(self, group, user, old_rank, new_rank):
        """Отправляет уведомление о новом звании пользователя"""
        try:
            # Формируем текст уведомления
            if old_rank is None:
                message = f"🎉 <b>Поздравляем!</b>\n\n@{user.username or user.first_name} получил первое звание: <b>{new_rank.name}</b>"
            else:
                message = f"🏆 <b>Новое звание!</b>\n\n@{user.username or user.first_name} повысился с <b>{old_rank.name}</b> до <b>{new_rank.name}</b>"
            
            # Отправляем уведомление в чат через Bot API
            self._send_telegram_message_direct(group.telegram_id, message)
            
        except Exception as e:
            print(f"Ошибка при отправке уведомления о звании: {e}")
    
    def _send_telegram_message_direct(self, chat_id, message_text):
        """Отправляет сообщение напрямую через Bot API (для уведомлений)"""
        try:
            import requests
            
            print(f"📤 Начинаем отправку уведомления о звании в Telegram")
            print(f"📤 Chat ID: {chat_id}")
            print(f"📤 Длина сообщения: {len(message_text)} символов")
            
            # Получаем токен бота из переменных окружения
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                print("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден")
                return False
            
            print(f"📤 Токен бота получен: {bot_token[:10]}...")
            
            # URL для отправки сообщения через Telegram Bot API
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            print(f"📤 URL API: {url}")
            
            # Подготавливаем данные для отправки
            data = {
                'chat_id': chat_id,
                'text': message_text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            print(f"📤 Данные для отправки: {data}")
            
            # Отправляем запрос
            print(f"📤 Отправляем POST запрос...")
            response = requests.post(url, json=data, timeout=10)
            print(f"📤 Получен ответ: {response.status_code}")
            
            response.raise_for_status()
            
            result = response.json()
            print(f"📤 Ответ API: {result}")
            
            if result.get('ok'):
                print(f"✅ Уведомление о звании отправлено в чат {chat_id}")
                return True
            else:
                print(f"❌ Ошибка отправки уведомления: {result.get('description', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления: {e}")
            import traceback
            traceback.print_exc()
            return False


class StatisticsView(APIView):
    """API для получения статистики пользователей в группе"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            print(f"🔍 Получен запрос на получение статистики")
            print(f"🔍 Данные запроса: {request.data}")
            
            # Проверяем токен авторизации
            auth_token = request.data.get('auth_token')
            chat_id = request.data.get('chat_id')
            
            if not auth_token or not chat_id:
                return Response({'detail': 'Missing auth_token or chat_id'}, status=status.HTTP_400_BAD_REQUEST)
            
            if auth_token != settings.SECRET_KEY:
                return Response({'detail': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
            
            print(f"🔍 Получен запрос на статистику для чата {chat_id}")
            
            # Получаем группу по telegram_id
            try:
                group = TelegramGroup.objects.get(telegram_id=chat_id)
                print(f"🔍 Найдена группа: {group.title}")
            except TelegramGroup.DoesNotExist:
                print(f"❌ Группа с telegram_id {chat_id} не найдена")
                return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Получаем ВСЕХ пользователей по рейтингу (убираем лимит)
            users_in_group = UserInGroup.objects.filter(
                group=group,
                is_active=True
            ).select_related('user', 'rank').order_by('-rating')
            
            print(f"🔍 Найдено пользователей в группе: {users_in_group.count()}")
            
            if not users_in_group:
                return Response({
                    'success': True,
                    'statistics': 'В этой группе пока нет статистики.'
                }, status=status.HTTP_200_OK)
            
            # Формируем сообщение со статистикой
            stat_text = f"📊 <b>Статистика пользователей в группе:</b>\n\n"
            
            for i, user_in_group in enumerate(users_in_group, 1):
                username = f"@{user_in_group.user.username}" if user_in_group.user.username else user_in_group.user.first_name
                rank_name = user_in_group.rank.name if user_in_group.rank else "Нет звания"
                
                # Получаем количество непрерывных дней из DailyCheckin
                try:
                    checkin = DailyCheckin.objects.get(user=user_in_group.user, group=group)
                    consecutive_days = checkin.consecutive_days
                except DailyCheckin.DoesNotExist:
                    consecutive_days = 0
                
                # Получаем дату последнего сообщения пользователя
                last_message = Message.objects.filter(
                    user=user_in_group.user,
                    chat=group
                ).order_by('-date').first()
                
                # Форматируем дату последней активности (московское время)
                if last_message and last_message.date:
                    # Костыльное решение: добавляем 3 часа для московского времени
                    msg_date = last_message.date
                    
                    print(f"🔍 DEBUG: Исходная дата для {username}: {msg_date}, tzinfo: {msg_date.tzinfo}")
                    
                    # Убеждаемся, что дата aware (с timezone)
                    if msg_date.tzinfo is None:
                        # Если naive, делаем aware в UTC (стандарт Django)
                        import pytz
                        msg_date = pytz.UTC.localize(msg_date)
                        print(f"🔍 DEBUG: Локализовали в UTC: {msg_date}")
                    
                    # Добавляем 3 часа для московского времени (UTC+3)
                    msg_date_moscow = msg_date + timedelta(hours=3)
                    print(f"🔍 DEBUG: После добавления 3 часов: {msg_date_moscow}")
                    last_activity_str = msg_date_moscow.strftime('%d.%m.%Y %H:%M')
                    print(f"🔍 DEBUG: Итоговая строка для {username}: {last_activity_str}")
                else:
                    last_activity_str = "нет данных"
                
                stat_text += (
                    f"{i}. <b>{username}</b>\n"
                    f"   🏆 {rank_name}\n"
                    f"   📈 Рейтинг: {user_in_group.rating}\n"
                    f"   💬 Сообщений: {user_in_group.message_count}\n"
                    f"   🔥 Непрерывных дней: {consecutive_days}\n"
                    f"   ⏰ Был активен: {last_activity_str}\n\n"
                )
            
            print(f"🔍 Статистика сформирована, длина: {len(stat_text)} символов")
            
            return Response({
                'success': True,
                'statistics': stat_text
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ ОШИБКА в StatisticsView:")
            print(f"❌ Тип ошибки: {type(e).__name__}")
            print(f"❌ Сообщение: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'detail': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendMessageView(APIView):
    """API для отправки сообщений в Telegram через бота"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            # Логируем в файл для отладки
            with open('/tmp/debug.log', 'a') as f:
                f.write(f"\n=== {timezone.now()} ===\n")
                f.write(f"Получен запрос на отправку сообщения\n")
                f.write(f"Данные запроса: {request.data}\n")
                f.write(f"Тип данных: {type(request.data)}\n")
            
            print(f"🔍 Получен запрос на отправку сообщения")
            print(f"🔍 Данные запроса: {request.data}")
            print(f"🔍 Тип данных: {type(request.data)}")
            print(f"🔍 Заголовки: {dict(request.headers)}")
            
            # Проверяем, что все необходимые данные есть
            chat_id = request.data.get('chat_id')
            message_text = request.data.get('message_text')
            print(f"🔍 chat_id: {chat_id}")
            print(f"🔍 message_text (первые 100 символов): {message_text[:100] if message_text else 'None'}...")
            
            # Проверяем токен авторизации
            auth_token = request.data.get('auth_token')
            expected_token = settings.SECRET_KEY
            
            # Декодируем HTML-сущности в токене
            if auth_token:
                import html
                auth_token_decoded = html.unescape(auth_token)
                print(f"🔍 Полученный токен (закодированный): {auth_token}")
                print(f"🔍 Полученный токен (декодированный): {auth_token_decoded}")
                auth_token = auth_token_decoded
            
            print(f"🔍 Ожидаемый токен: {expected_token[:20] if expected_token else 'None'}...")
            print(f"🔍 Токены совпадают: {auth_token == expected_token}")
            print(f"🔍 Длина полученного токена: {len(auth_token) if auth_token else 0}")
            print(f"🔍 Длина ожидаемого токена: {len(expected_token) if expected_token else 0}")
            
            if not auth_token or auth_token != expected_token:
                print(f"❌ Неверный токен: {auth_token}")
                return Response({'detail': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
            
            chat_id = request.data.get('chat_id')
            message_text = request.data.get('message_text')
            
            if not chat_id or not message_text:
                return Response({'detail': 'Missing chat_id or message_text'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Отправляем сообщение через бота
            success = self._send_telegram_message(chat_id, message_text)
            
            if success:
                return Response({'status': 'Message sent successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'Failed to send message'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            import traceback
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА в SendMessageView:")
            print(f"❌ Тип ошибки: {type(e).__name__}")
            print(f"❌ Сообщение: {str(e)}")
            print(f"❌ Traceback:")
            traceback.print_exc()
            return Response({'detail': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _send_telegram_message(self, chat_id, message_text):
        """Отправляет сообщение в Telegram через бота"""
        try:
            import requests
            
            # Логируем в файл
            with open('/tmp/debug.log', 'a') as f:
                f.write(f"Начинаем отправку сообщения в чат {chat_id}\n")
                f.write(f"Длина сообщения: {len(message_text)} символов\n")
            
            print(f"🔍 Начинаем отправку сообщения в чат {chat_id}")
            print(f"🔍 Длина сообщения: {len(message_text)} символов")
            
            # Получаем токен бота из переменных окружения
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            print(f"🔍 TELEGRAM_BOT_TOKEN: {bot_token[:10] if bot_token else 'None'}...")
            
            if not bot_token:
                print("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден")
                return False
            
            print(f"🔍 Токен получен, продолжаем...")
            
            # URL для отправки сообщения через Telegram Bot API
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            print(f"🔍 Начинаем очистку текста...")
            
            # Очищаем сообщение от markdown-разметки
            cleaned_text = message_text
            if cleaned_text.startswith('```html'):
                # Убираем markdown-блок
                cleaned_text = cleaned_text.replace('```html', '').replace('```', '').strip()
                print(f"🔍 Очищенный текст (первые 200 символов): {cleaned_text[:200]}...")
            else:
                print(f"🔍 Текст не содержит markdown-разметку")
            
            print(f"🔍 Очистка завершена")
            
            # Проверяем длину сообщения
            if len(cleaned_text) > 4000:
                print(f"⚠️ ВНИМАНИЕ: Сообщение слишком длинное ({len(cleaned_text)} символов)")
                print(f"⚠️ Telegram ограничение: 4096 символов")
                # Обрезаем до безопасной длины
                cleaned_text = cleaned_text[:4000] + "..."
                print(f"🔍 Обрезано до {len(cleaned_text)} символов")
            
            # Подготавливаем данные для отправки
            data = {
                'chat_id': chat_id,
                'text': cleaned_text,
                'parse_mode': 'HTML',  # Поддерживаем HTML-разметку
                'disable_web_page_preview': True
            }
            
            # Логируем детали запроса
            with open('/tmp/debug.log', 'a') as f:
                f.write(f"URL: {url}\n")
                f.write(f"Оригинальный текст (первые 200 символов): {message_text[:200]}\n")
                f.write(f"Очищенный текст (первые 200 символов): {cleaned_text[:200]}\n")
                f.write(f"Данные для отправки: {data}\n")
                f.write(f"Длина оригинального текста: {len(message_text)} символов\n")
                f.write(f"Длина очищенного текста: {len(cleaned_text)} символов\n")
            
            print(f"🔍 URL: {url}")
            print(f"🔍 Данные для отправки: {data}")
            
            # Отправляем запрос
            try:
                print(f"🔍 Отправляем POST запрос...")
                response = requests.post(url, json=data, timeout=10)
                print(f"🔍 Получен ответ: {response.status_code}")
                print(f"🔍 Тело ответа: {response.text}")
                
                response.raise_for_status()
            except Exception as e:
                print(f"❌ Ошибка при отправке запроса: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            result = response.json()
            print(f"🔍 Результат API: {result}")
            
            # Логируем ответ в файл
            with open('/tmp/debug.log', 'a') as f:
                f.write(f"Статус ответа: {response.status_code}\n")
                f.write(f"Тело ответа: {response.text}\n")
                f.write(f"Результат API: {result}\n")
            
            if result.get('ok'):
                print(f"✅ Сообщение успешно отправлено в чат {chat_id}")
                return True
            else:
                print(f"❌ Ошибка отправки: {result.get('description', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Ошибка сети при отправке: {e}")
            return False
        except Exception as e:
            import traceback
            print(f"❌ ОШИБКА в _send_telegram_message:")
            print(f"❌ Тип ошибки: {type(e).__name__}")
            print(f"❌ Сообщение: {str(e)}")
            print(f"❌ Traceback:")
            traceback.print_exc()
            return False
