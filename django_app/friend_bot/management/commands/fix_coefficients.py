from django.core.management.base import BaseCommand
from friend_bot.models import UserInGroup, DailyCheckin


class Command(BaseCommand):
    help = 'Исправляет коэффициенты для существующих пользователей'

    def handle(self, *args, **options):
        self.stdout.write('Исправляю коэффициенты для существующих пользователей...\n')
        
        users = UserInGroup.objects.all()
        fixed_count = 0
        
        for uig in users:
            try:
                checkin = DailyCheckin.objects.get(user=uig.user, group=uig.group)
                
                # Рассчитываем правильный коэффициент
                if checkin.consecutive_days == 0:
                    new_coefficient = 0.5
                elif checkin.consecutive_days == 1:
                    new_coefficient = 1.0
                else:
                    new_coefficient = 1.0 + (checkin.consecutive_days - 1) * 0.1
                
                # Обновляем только если коэффициент изменился
                if abs(uig.coefficient - new_coefficient) > 0.01:
                    old_coefficient = uig.coefficient
                    uig.coefficient = new_coefficient
                    uig.save()
                    self.stdout.write(
                        f'  {uig.user.first_name}: {checkin.consecutive_days} дней '
                        f'→ коэффициент {old_coefficient:.1f} → {new_coefficient:.1f}'
                    )
                    fixed_count += 1
                else:
                    self.stdout.write(
                        f'  {uig.user.first_name}: {checkin.consecutive_days} дней '
                        f'→ коэффициент {uig.coefficient:.1f} (уже правильный)'
                    )
                    
            except DailyCheckin.DoesNotExist:
                # Если чекина нет, устанавливаем коэффициент 0.5
                if abs(uig.coefficient - 0.5) > 0.01:
                    old_coefficient = uig.coefficient
                    uig.coefficient = 0.5
                    uig.save()
                    self.stdout.write(
                        f'  {uig.user.first_name}: нет чекина '
                        f'→ коэффициент {old_coefficient:.1f} → 0.5'
                    )
                    fixed_count += 1
                else:
                    self.stdout.write(
                        f'  {uig.user.first_name}: нет чекина '
                        f'→ коэффициент {uig.coefficient:.1f} (уже правильный)'
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Исправлено коэффициентов: {fixed_count}')
        )

