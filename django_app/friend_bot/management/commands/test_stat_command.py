from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from friend_bot.models import User, TelegramGroup, UserInGroup, DailyCheckin, Message


class Command(BaseCommand):
    help = 'Создает тестовые данные для проверки команды stat в боте'

    def handle(self, *args, **options):
        self.stdout.write('📊 Создаю тестовые данные для команды stat...\n')
        
        # Создаем тестовую группу
        group, created = TelegramGroup.objects.get_or_create(
            telegram_id=-1001234567890,
            defaults={'title': 'Тестовая группа', 'is_active': True}
        )
        
        if created:
            self.stdout.write(f'✓ Создана группа: {group.title}')
        else:
            self.stdout.write(f'- Используется группа: {group.title}')
        
        # Создаем тестовых пользователей
        test_users = [
            {'name': 'Алиса', 'username': 'alice', 'messages': 10, 'consecutive_days': 0},
            {'name': 'Боб', 'username': 'bob', 'messages': 25, 'consecutive_days': 1},
            {'name': 'Вася', 'username': 'vasya', 'messages': 50, 'consecutive_days': 2},
            {'name': 'Галя', 'username': 'galya', 'messages': 100, 'consecutive_days': 3},
            {'name': 'Дима', 'username': 'dima', 'messages': 200, 'consecutive_days': 5},
        ]
        
        users_created = 0
        
        for i, user_data in enumerate(test_users):
            # Создаем пользователя
            user, created = User.objects.get_or_create(
                telegram_id=100000000 + i,
                defaults={
                    'first_name': user_data['name'],
                    'username': user_data['username'],
                    'is_active': True
                }
            )
            
            if created:
                users_created += 1
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
            
            # Устанавливаем рейтинг и количество сообщений
            user_in_group.rating = user_data['messages'] * 5  # 5 очков за сообщение
            user_in_group.message_count = user_data['messages']
            user_in_group.save()
            
            # Обновляем звание
            user_in_group.update_rank()
            
            # Создаем DailyCheckin
            checkin_date = timezone.now() - timedelta(days=user_data['consecutive_days'])
            checkin, created = DailyCheckin.objects.get_or_create(
                user=user,
                group=group,
                defaults={
                    'consecutive_days': user_data['consecutive_days'],
                    'last_checkin': checkin_date
                }
            )
            
            if not created:
                checkin.consecutive_days = user_data['consecutive_days']
                checkin.last_checkin = checkin_date
                checkin.save()
            
            # Обновляем коэффициент
            if user_data['consecutive_days'] == 0:
                user_in_group.coefficient = 0.5
            elif user_data['consecutive_days'] == 1:
                user_in_group.coefficient = 1.0
            else:
                user_in_group.coefficient = 1.0 + (user_data['consecutive_days'] - 1) * 0.1
            
            user_in_group.save()
            
            self.stdout.write(f'  → Рейтинг: {user_in_group.rating}, Звание: {user_in_group.rank.name if user_in_group.rank else "Нет"}, Коэф: {user_in_group.coefficient:.1f}')
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Создано пользователей: {users_created}')
        )
        
        self.stdout.write(f'\n📊 Теперь можно протестировать команду /stat в боте!')
        self.stdout.write(f'📱 Добавьте бота в группу с ID: {group.telegram_id}')
        self.stdout.write(f'💬 Отправьте команду: /stat')

