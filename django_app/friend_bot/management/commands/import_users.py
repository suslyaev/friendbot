from django.core.management.base import BaseCommand
from django.db import transaction
from friend_bot.models import User, TelegramGroup, UserInGroup, Rank
from datetime import datetime


class Command(BaseCommand):
    help = 'Импортирует существующих пользователей с их статистикой'

    def handle(self, *args, **options):
        self.stdout.write('Начинаю импорт пользователей...')
        
        # Данные из статистики (имя, telegram_id, username, количество сообщений)
        users_data = [
            {'name': 'Ks', 'telegram_id': 690151574, 'username': 'suslyaeva', 'messages': 1525},
            {'name': 'Elina Plakunova', 'telegram_id': 461741385, 'username': 'elinaplakunova', 'messages': 1518},
            {'name': 'Vladislav', 'telegram_id': 164845563, 'username': 'vlrupk', 'messages': 1124},
            {'name': 'Лера Победа', 'telegram_id': 771770344, 'username': 'pobedalera', 'messages': 1016},
            {'name': 'Alexey', 'telegram_id': 148709509, 'username': 'suslyaev', 'messages': 988},
            {'name': 'Maria Habirova', 'telegram_id': 609917539, 'username': 'mariahabirova', 'messages': 914},
            {'name': 'esmeralda', 'telegram_id': 932304738, 'username': 'merallebed', 'messages': 793},
            {'name': 'David Pobedintsev', 'telegram_id': 409372150, 'username': 'davidpob', 'messages': 601},
            {'name': 'Кристина Шим', 'telegram_id': 1052843231, 'username': 'kristinashim', 'messages': 540},
            {'name': 'Иван Плакунов', 'telegram_id': 465344529, 'username': 'iplakunov', 'messages': 471},
            {'name': 'Roman', 'telegram_id': 534698837, 'username': 'roman_khabirov93', 'messages': 355},
            {'name': 'Daniil Lebedev', 'telegram_id': 868343634, 'username': 'daniil_lebedev', 'messages': 271},
            {'name': 'Ivan', 'telegram_id': 637504191, 'username': 'yvanuss', 'messages': 261},
            {'name': 'Az', 'telegram_id': 809224485, 'username': 'iksanov_az', 'messages': 117},
            {'name': 'Denis Koteev', 'telegram_id': 986193746, 'username': 'deniskoteev', 'messages': 90},
            {'name': 'Айназ 🌖', 'telegram_id': 691254803, 'username': 'senoritaainaz', 'messages': 27},
            {'name': 'Jhanna Sabynin', 'telegram_id': 747005955, 'username': '', 'messages': 4},
        ]
        
        with transaction.atomic():
            # Используем существующую группу
            try:
                group = TelegramGroup.objects.get(telegram_id=-1001553030965)
                self.stdout.write(f'  - Используется группа: {group.title}')
            except TelegramGroup.DoesNotExist:
                self.stdout.write(self.style.ERROR('  ❌ Группа не найдена! Создайте группу в админке.'))
                return
            
            users_created = 0
            users_in_group_created = 0
            
            for user_data in users_data:
                # Создаем пользователя
                user, created = User.objects.get_or_create(
                    telegram_id=user_data['telegram_id'],
                    defaults={
                        'first_name': user_data['name'].split()[0],
                        'last_name': ' '.join(user_data['name'].split()[1:]) if len(user_data['name'].split()) > 1 else '',
                        'username': user_data['username'] if user_data['username'] else '',
                        'is_active': True
                    }
                )
                
                if created:
                    users_created += 1
                    self.stdout.write(f'  ✓ Создан пользователь: {user_data["name"]}')
                else:
                    self.stdout.write(f'  - Пользователь уже существует: {user_data["name"]}')
                
                # Создаем связь пользователя с группой
                user_in_group, created = UserInGroup.objects.get_or_create(
                    user=user,
                    group=group,
                    defaults={
                        'rating': user_data['messages'] * 5,  # Базовые 5 очков за сообщение
                        'message_count': user_data['messages'],
                        'coefficient': 1,
                        'is_active': True
                    }
                )
                
                if created:
                    users_in_group_created += 1
                    self.stdout.write(f'    ✓ Добавлен в группу с рейтингом: {user_in_group.rating}')
                else:
                    # Обновляем существующую запись
                    user_in_group.rating = user_data['messages'] * 5
                    user_in_group.message_count = user_data['messages']
                    user_in_group.save()
                    self.stdout.write(f'    - Обновлен в группе с рейтингом: {user_in_group.rating}')
                
                # Обновляем звание пользователя
                user_in_group.update_rank()
                if user_in_group.rank:
                    self.stdout.write(f'      → Звание: {user_in_group.rank.name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Импорт завершен!\n'
                f'   Создано пользователей: {users_created}\n'
                f'   Добавлено в группу: {users_in_group_created}\n'
                f'   Группа: {group.title} (ID: {group.telegram_id})'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                f'\n⚠️  ВАЖНО: Замените ID группы {group.telegram_id} на реальный ID вашей группы!'
            )
        )
