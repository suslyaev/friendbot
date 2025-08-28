from django.core.management.base import BaseCommand
from django.utils import timezone
from friend_bot.models import User, TelegramGroup, UserInGroup, DailyCheckin, Message, Rank


class Command(BaseCommand):
    help = 'Тестирует работу уведомлений о смене звания'

    def handle(self, *args, **options):
        self.stdout.write('🔔 Тестирую уведомления о смене звания...\n')
        
        # Создаем тестовую группу
        group, created = TelegramGroup.objects.get_or_create(
            telegram_id=-1001234567890,
            defaults={'title': 'Тестовая группа для уведомлений', 'is_active': True}
        )
        
        if created:
            self.stdout.write(f'✓ Создана группа: {group.title}')
        else:
            self.stdout.write(f'- Используется группа: {group.title}')
        
        # Создаем тестового пользователя
        user, created = User.objects.get_or_create(
            telegram_id=999999999,
            defaults={
                'first_name': 'Тест',
                'username': 'testuser',
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'✓ Создан пользователь: {user.first_name}')
        else:
            self.stdout.write(f'- Используется пользователь: {user.first_name}')
        
        # Создаем связь с группой
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
        
        self.stdout.write(f'📊 Текущий рейтинг: {user_in_group.rating}')
        self.stdout.write(f'🏆 Текущее звание: {user_in_group.rank.name if user_in_group.rank else "Нет"}')
        
        # Проверяем, есть ли звания в базе
        ranks = Rank.objects.all().order_by('required_rating')
        if not ranks.exists():
            self.stdout.write('❌ В базе нет званий! Сначала запустите init_data')
            return
        
        self.stdout.write(f'📋 Доступные звания:')
        for rank in ranks:
            self.stdout.write(f'  - {rank.name} (требует {rank.required_rating} очков)')
        
        # Симулируем добавление очков до следующего звания
        if user_in_group.rank:
            next_rank = ranks.filter(required_rating__gt=user_in_group.rating).first()
            if next_rank:
                points_needed = next_rank.required_rating - user_in_group.rating
                self.stdout.write(f'🎯 Для получения звания "{next_rank.name}" нужно {points_needed} очков')
                
                # Добавляем очки
                old_rating = user_in_group.rating
                user_in_group.rating = next_rank.required_rating
                user_in_group.message_count += points_needed // 5  # Примерно
                user_in_group.save()
                
                self.stdout.write(f'📈 Рейтинг изменен: {old_rating} → {user_in_group.rating}')
                
                # Обновляем звание
                old_rank = user_in_group.rank
                user_in_group.update_rank()
                
                if user_in_group.rank != old_rank:
                    self.stdout.write(f'🎉 Звание изменено: {old_rank.name if old_rank else "Нет"} → {user_in_group.rank.name}')
                    self.stdout.write(f'🔔 Должно отправиться уведомление в чат {group.telegram_id}')
                else:
                    self.stdout.write(f'❌ Звание не изменилось')
            else:
                self.stdout.write(f'🏆 Пользователь уже имеет максимальное звание: {user_in_group.rank.name}')
        else:
            # У пользователя нет звания, даем первое
            first_rank = ranks.first()
            if first_rank:
                points_needed = first_rank.required_rating
                self.stdout.write(f'🎯 Для получения первого звания "{first_rank.name}" нужно {points_needed} очков')
                
                # Добавляем очки
                user_in_group.rating = points_needed
                user_in_group.message_count += points_needed // 5
                user_in_group.save()
                
                self.stdout.write(f'📈 Рейтинг установлен: {user_in_group.rating}')
                
                # Обновляем звание
                user_in_group.update_rank()
                
                if user_in_group.rank:
                    self.stdout.write(f'🎉 Получено первое звание: {user_in_group.rank.name}')
                    self.stdout.write(f'🔔 Должно отправиться уведомление в чат {group.telegram_id}')
                else:
                    self.stdout.write(f'❌ Звание не назначено')
        
        self.stdout.write(f'\n✅ Тест завершен!')
        self.stdout.write(f'📱 Проверьте, пришло ли уведомление в группу {group.telegram_id}')
