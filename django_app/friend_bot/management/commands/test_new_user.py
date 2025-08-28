from django.core.management.base import BaseCommand
from friend_bot.models import User, TelegramGroup, UserInGroup, DailyCheckin


class Command(BaseCommand):
    help = 'Тестирует коэффициент для нового пользователя'

    def handle(self, *args, **options):
        self.stdout.write('Тестирую коэффициент для нового пользователя...\n')
        
        # Находим пользователя с самым низким рейтингом (скорее всего нового)
        try:
            user_in_group = UserInGroup.objects.order_by('rating').first()
            if not user_in_group:
                self.stdout.write('❌ Пользователи не найдены')
                return
            
            self.stdout.write(f'Тестирую на пользователе: {user_in_group.user.first_name}')
            self.stdout.write(f'Рейтинг: {user_in_group.rating}')
            self.stdout.write(f'Сообщений: {user_in_group.message_count}')
            self.stdout.write(f'Коэффициент в UserInGroup: {user_in_group.coefficient}')
            
            # Проверяем DailyCheckin
            try:
                checkin = DailyCheckin.objects.get(user=user_in_group.user, group=user_in_group.group)
                self.stdout.write(f'DailyCheckin найден:')
                self.stdout.write(f'  Непрерывные дни: {checkin.consecutive_days}')
                self.stdout.write(f'  Последний чекин: {checkin.last_checkin}')
                
                # Проверяем расчет коэффициента
                if checkin.consecutive_days == 0:
                    expected_coef = 0.5
                elif checkin.consecutive_days == 1:
                    expected_coef = 1.0
                else:
                    expected_coef = 1.0 + (checkin.consecutive_days - 1) * 0.1
                
                self.stdout.write(f'Ожидаемый коэффициент: {expected_coef}')
                
                if abs(user_in_group.coefficient - expected_coef) < 0.01:
                    self.stdout.write(self.style.SUCCESS('✅ Коэффициент рассчитан правильно!'))
                else:
                    self.stdout.write(self.style.ERROR(f'❌ Коэффициент неверный! Ожидалось: {expected_coef}, получено: {user_in_group.coefficient}'))
                
            except DailyCheckin.DoesNotExist:
                self.stdout.write('❌ DailyCheckin не найден')
            
            # Тестируем расчет очков
            self.stdout.write(f'\nТестирую расчет очков:')
            base_points = 5  # текстовое сообщение
            coefficient = user_in_group.coefficient
            total_points = int(base_points * coefficient)
            
            self.stdout.write(f'  Базовые очки: {base_points}')
            self.stdout.write(f'  Коэффициент: {coefficient}')
            self.stdout.write(f'  Итоговые очки: {base_points} × {coefficient} = {total_points}')
            
        except Exception as e:
            self.stdout.write(f'❌ Ошибка: {e}')
        
        self.stdout.write('\n✅ Тест завершен!')

