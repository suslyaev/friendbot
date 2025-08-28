from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from friend_bot.models import User, TelegramGroup, UserInGroup, DailyCheckin, Message, MessageTypePoints


class Command(BaseCommand):
    help = 'Комплексный тест всей системы коэффициентов, чекинов и званий'

    def handle(self, *args, **options):
        self.stdout.write('🧪 Комплексный тест системы...\n')
        
        # Создаем тестовую группу
        group, created = TelegramGroup.objects.get_or_create(
            telegram_id=-1001234567890,
            defaults={'title': 'Тестовая группа', 'is_active': True}
        )
        
        if created:
            self.stdout.write(f'✓ Создана тестовая группа: {group.title}')
        else:
            self.stdout.write(f'- Используется группа: {group.title}')
        
        # Создаем тестового пользователя
        user, created = User.objects.get_or_create(
            telegram_id=123456789,
            defaults={
                'first_name': 'Тест',
                'last_name': 'Пользователь',
                'username': 'testuser',
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'✓ Создан тестовый пользователь: {user.first_name}')
        else:
            self.stdout.write(f'- Используется пользователь: {user.first_name}')
        
        # Создаем связь пользователя с группой
        user_in_group, created = UserInGroup.objects.get_or_create(
            user=user,
            group=group,
            defaults={
                'is_active': True,
                'rating': 0,
                'message_count': 0,
                'coefficient': 0.5
            }
        )
        
        if created:
            self.stdout.write(f'✓ Пользователь добавлен в группу')
        else:
            self.stdout.write(f'- Пользователь уже в группе')
        
        self.stdout.write(f'\n📊 Начальное состояние:')
        self.stdout.write(f'  Рейтинг: {user_in_group.rating}')
        self.stdout.write(f'  Сообщений: {user_in_group.message_count}')
        self.stdout.write(f'  Коэффициент: {user_in_group.coefficient}')
        self.stdout.write(f'  Звание: {user_in_group.rank.name if user_in_group.rank else "Нет"}')
        
        # Создаем DailyCheckin с вчерашней датой
        yesterday = timezone.now() - timedelta(days=1)
        checkin, created = DailyCheckin.objects.get_or_create(
            user=user,
            group=group,
            defaults={
                'consecutive_days': 0,
                'last_checkin': yesterday
            }
        )
        
        if created:
            self.stdout.write(f'✓ Создан чекин на вчера: {checkin.last_checkin}')
        else:
            checkin.last_checkin = yesterday
            checkin.save()
            self.stdout.write(f'- Обновлен чекин на вчера: {checkin.last_checkin}')
        
        self.stdout.write(f'  Непрерывные дни: {checkin.consecutive_days}')
        
        # Симулируем отправку сообщения (сегодня)
        self.stdout.write(f'\n📝 Симулирую отправку сообщения...')
        
        # Создаем сообщение
        message = Message.objects.create(
            telegram_id=1,
            date=timezone.now(),
            user=user,
            chat=group,
            message_type='text',
            text='Тестовое сообщение'
        )
        
        self.stdout.write(f'✓ Сообщение создано: {message.get_message_type_display()}')
        
        # Добавляем очки за сообщение
        result = user_in_group.add_message_points('text')
        
        self.stdout.write(f'📊 Результат добавления очков:')
        self.stdout.write(f'  Базовые очки: 5')
        self.stdout.write(f'  Коэффициент: {result["points"] / 5:.1f}')
        self.stdout.write(f'  Итоговые очки: {result["points"]}')
        self.stdout.write(f'  Новый рейтинг: {user_in_group.rating}')
        self.stdout.write(f'  Новое звание: {user_in_group.rank.name if user_in_group.rank else "Нет"}')
        
        if result.get('rank_changed'):
            self.stdout.write(self.style.SUCCESS(f'  ✅ Звание изменилось!'))
        else:
            self.stdout.write(f'  ℹ️ Звание не изменилось')
        
        # Проверяем DailyCheckin после сообщения
        checkin.refresh_from_db()
        self.stdout.write(f'\n📅 Состояние чекина после сообщения:')
        self.stdout.write(f'  Непрерывные дни: {checkin.consecutive_days}')
        self.stdout.write(f'  Последний чекин: {checkin.last_checkin}')
        
        # Проверяем коэффициент в UserInGroup
        user_in_group.refresh_from_db()
        self.stdout.write(f'\n📊 Финальное состояние:')
        self.stdout.write(f'  Рейтинг: {user_in_group.rating}')
        self.stdout.write(f'  Сообщений: {user_in_group.message_count}')
        self.stdout.write(f'  Коэффициент: {user_in_group.coefficient}')
        self.stdout.write(f'  Звание: {user_in_group.rank.name if user_in_group.rank else "Нет"}')
        
        # Очищаем тестовые данные
        self.stdout.write(f'\n🧹 Очищаю тестовые данные...')
        message.delete()
        user_in_group.delete()
        checkin.delete()
        user.delete()
        group.delete()
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Комплексный тест завершен!'))

