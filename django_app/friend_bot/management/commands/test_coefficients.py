from django.core.management.base import BaseCommand
from friend_bot.models import UserInGroup, DailyCheckin


class Command(BaseCommand):
    help = 'Тестирует новую логику коэффициентов непрерывности'

    def handle(self, *args, **options):
        self.stdout.write('Тестирую новую логику коэффициентов...\n')
        
        # Показываем примеры коэффициентов
        self.stdout.write('Примеры коэффициентов:')
        for days in range(0, 11):
            if days == 0:
                coef = 0.5
            elif days == 1:
                coef = 1.0
            else:
                coef = 1.0 + (days - 1) * 0.1
            
            # Пример расчета очков за текстовое сообщение (5 очков)
            base_points = 5
            total_points = int(base_points * coef)
            
            self.stdout.write(f'  {days:2d} дней: коэффициент {coef:3.1f} → {base_points} × {coef:3.1f} = {total_points} очков')
        
        self.stdout.write('\n' + '='*50)
        
        # Показываем реальные данные пользователей
        users_in_group = UserInGroup.objects.all().order_by('-rating')[:10]
        
        if users_in_group:
            self.stdout.write('\nТоп-10 пользователей по рейтингу:')
            for i, uig in enumerate(users_in_group, 1):
                try:
                    checkin = DailyCheckin.objects.get(user=uig.user, group=uig.group)
                    consecutive_days = checkin.consecutive_days
                    
                    if consecutive_days == 0:
                        coef = 0.5
                    elif consecutive_days == 1:
                        coef = 1.0
                    else:
                        coef = 1.0 + (consecutive_days - 1) * 0.1
                    
                    # Пример расчета для текстового сообщения
                    base_points = 5
                    example_points = int(base_points * coef)
                    
                    self.stdout.write(
                        f'{i:2d}. {uig.user.first_name:<15} '
                        f'Рейтинг: {uig.rating:>6} '
                        f'Сообщений: {uig.message_count:>4} '
                        f'Дней подряд: {consecutive_days:>2} '
                        f'Коэф: {coef:3.1f} '
                        f'Пример: {base_points}×{coef:3.1f}={example_points}'
                    )
                    
                except DailyCheckin.DoesNotExist:
                    self.stdout.write(
                        f'{i:2d}. {uig.user.first_name:<15} '
                        f'Рейтинг: {uig.rating:>6} '
                        f'Сообщений: {uig.message_count:>4} '
                        f'Дней подряд: НЕТ '
                        f'Коэф: 0.5 '
                        f'Пример: 5×0.5=2'
                    )
        else:
            self.stdout.write('Пользователи не найдены')
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('✅ Тест завершен!')

