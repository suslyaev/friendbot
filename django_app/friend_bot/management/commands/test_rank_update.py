from django.core.management.base import BaseCommand
from friend_bot.models import UserInGroup, Rank


class Command(BaseCommand):
    help = 'Тестирует автоматическое обновление званий при добавлении очков'

    def handle(self, *args, **options):
        self.stdout.write('Тестирую автоматическое обновление званий...\n')
        
        # Находим пользователя для тестирования
        try:
            user_in_group = UserInGroup.objects.first()
            if not user_in_group:
                self.stdout.write('❌ Пользователи не найдены')
                return
            
            self.stdout.write(f'Тестирую на пользователе: {user_in_group.user.first_name}')
            self.stdout.write(f'Текущий рейтинг: {user_in_group.rating}')
            self.stdout.write(f'Текущее звание: {user_in_group.rank.name if user_in_group.rank else "Нет"}')
            
            # Показываем ближайшие звания
            ranks = Rank.objects.all().order_by('required_rating')
            next_ranks = [r for r in ranks if r.required_rating > user_in_group.rating][:3]
            
            if next_ranks:
                self.stdout.write(f'\nБлижайшие звания:')
                for rank in next_ranks:
                    points_needed = rank.required_rating - user_in_group.rating
                    self.stdout.write(f'  {rank.name} (рейтинг: {rank.required_rating}) - нужно еще {points_needed} очков')
            
            # Симулируем добавление очков
            self.stdout.write(f'\nСимулирую добавление 100 очков...')
            
            old_rating = user_in_group.rating
            old_rank = user_in_group.rank
            
            # Добавляем очки
            user_in_group.rating += 100
            user_in_group.save()
            
            # Обновляем звание
            user_in_group.update_rank()
            
            new_rating = user_in_group.rating
            new_rank = user_in_group.rank
            
            self.stdout.write(f'Результат:')
            self.stdout.write(f'  Рейтинг: {old_rating} → {new_rating}')
            self.stdout.write(f'  Звание: {old_rank.name if old_rank else "Нет"} → {new_rank.name if new_rank else "Нет"}')
            
            if old_rank != new_rank:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Звание изменилось!'))
            else:
                self.stdout.write(f'  ℹ️ Звание не изменилось')
            
            # Возвращаем исходное состояние
            user_in_group.rating = old_rating
            user_in_group.rank = old_rank
            user_in_group.save()
            self.stdout.write(f'\nИсходное состояние восстановлено')
            
        except Exception as e:
            self.stdout.write(f'❌ Ошибка: {e}')
        
        self.stdout.write('\n✅ Тест завершен!')

