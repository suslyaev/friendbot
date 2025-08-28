from django.core.management.base import BaseCommand
from django.db import transaction
from friend_bot.models import Rank, UserInGroup


class Command(BaseCommand):
    help = 'Восстанавливает звания для всех пользователей на основе их рейтинга'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Начинаю восстановление званий для пользователей...')
        
        with transaction.atomic():
            # Получаем все звания, отсортированные по возрастанию required_rating
            ranks = list(Rank.objects.all().order_by('required_rating'))
            
            if not ranks:
                self.stdout.write(self.style.ERROR('❌ Нет званий в базе данных! Сначала запустите init_data'))
                return
            
            self.stdout.write(f'  📋 Найдено званий: {len(ranks)}')
            
            # Обрабатываем всех пользователей во всех группах
            user_in_groups = UserInGroup.objects.select_related('user', 'group', 'rank').all()
            
            if not user_in_groups:
                self.stdout.write('  ℹ️ Нет пользователей в группах для восстановления званий')
                return
            
            self.stdout.write(f'  👥 Найдено пользователей в группах: {user_in_groups.count()}')
            
            ranks_restored = 0
            users_processed = 0
            
            for user_in_group in user_in_groups:
                users_processed += 1
                
                # Находим самое высокое звание, которое может получить пользователь
                new_rank = None
                for rank in ranks:
                    if user_in_group.rating >= rank.required_rating:
                        new_rank = rank
                    else:
                        break
                
                # Если нашли звание и оно отличается от текущего
                if new_rank and user_in_group.rank != new_rank:
                    old_rank = user_in_group.rank
                    user_in_group.rank = new_rank
                    user_in_group.save()
                    ranks_restored += 1
                    
                    if old_rank:
                        self.stdout.write(f'    ✓ {user_in_group.user.first_name} в группе {user_in_group.group.title}: {old_rank.name} → {new_rank.name} (рейтинг: {user_in_group.rating})')
                    else:
                        self.stdout.write(f'    ✓ {user_in_group.user.first_name} в группе {user_in_group.group.title}: получил звание {new_rank.name} (рейтинг: {user_in_group.rating})')
                else:
                    # Показываем текущее звание пользователя
                    current_rank = user_in_group.rank.name if user_in_group.rank else "Нет звания"
                    self.stdout.write(f'    ℹ️ {user_in_group.user.first_name} в группе {user_in_group.group.title}: {current_rank} (рейтинг: {user_in_group.rating})')
            
            self.stdout.write(f'\n📊 Результаты восстановления:')
            self.stdout.write(f'  👥 Обработано пользователей: {users_processed}')
            self.stdout.write(f'  🔄 Восстановлено званий: {ranks_restored}')
            
            if ranks_restored > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'\n✅ Восстановление званий завершено! Восстановлено {ranks_restored} званий.')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'\n⚠️ Все звания уже актуальны! Восстановление не требуется.')
                )
