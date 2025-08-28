from django.core.management.base import BaseCommand
from django.db import transaction
from friend_bot.models import Rank, MessageTypePoints, UserInGroup


class Command(BaseCommand):
    help = 'Инициализирует базовые данные для системы (звания и баллы за типы сообщений)'

    def restore_user_ranks(self):
        """Восстанавливает звания для всех пользователей на основе их рейтинга"""
        self.stdout.write('  🔄 Восстанавливаю звания для существующих пользователей...')
        
        ranks_restored = 0
        users_processed = 0
        
        # Получаем все звания, отсортированные по возрастанию required_rating
        ranks = list(Rank.objects.all().order_by('required_rating'))
        
        if not ranks:
            self.stdout.write('  ❌ Нет званий для восстановления!')
            return
        
        # Обрабатываем всех пользователей во всех группах
        user_in_groups = UserInGroup.objects.select_related('user', 'group').all()
        
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
                    self.stdout.write(f'    ✓ {user_in_group.user.first_name} в группе {user_in_group.group.title}: {old_rank.name} → {new_rank.name}')
                else:
                    self.stdout.write(f'    ✓ {user_in_group.user.first_name} в группе {user_in_group.group.title}: получил звание {new_rank.name}')
        
        self.stdout.write(f'  ✅ Обработано пользователей: {users_processed}, восстановлено званий: {ranks_restored}')

    def handle(self, *args, **options):
        self.stdout.write('Начинаю инициализацию базовых данных...')
        
        with transaction.atomic():
            # Создаем полную систему званий (50 званий)
            ranks_created = 0
            ranks_data = [
                # Низшие звания (0-1000)
                {'sort_order': 1, 'name': 'чиркаш', 'required_rating': 0},
                {'sort_order': 2, 'name': 'шмыга', 'required_rating': 50},
                {'sort_order': 3, 'name': 'случайный прохожий', 'required_rating': 100},
                {'sort_order': 4, 'name': 'собачий хвост', 'required_rating': 200},
                {'sort_order': 5, 'name': 'мефедронщик', 'required_rating': 300},
                {'sort_order': 6, 'name': 'тухлый обитатель чата', 'required_rating': 400},
                {'sort_order': 7, 'name': 'консерва', 'required_rating': 500},
                {'sort_order': 8, 'name': 'обитатель чата', 'required_rating': 600},
                {'sort_order': 9, 'name': 'местный', 'required_rating': 700},
                {'sort_order': 10, 'name': 'шкурник', 'required_rating': 800},
                
                # Средние звания (1000-5000)
                {'sort_order': 11, 'name': 'кайфарь', 'required_rating': 1000},
                {'sort_order': 12, 'name': 'смотрящий', 'required_rating': 1500},
                {'sort_order': 13, 'name': 'уважаемый', 'required_rating': 2000},
                {'sort_order': 14, 'name': 'сладенький', 'required_rating': 2500},
                {'sort_order': 15, 'name': 'рулет с маком', 'required_rating': 3000},
                {'sort_order': 16, 'name': 'жирок', 'required_rating': 3500},
                {'sort_order': 17, 'name': 'собачий генерал', 'required_rating': 4000},
                {'sort_order': 18, 'name': 'шкурный властелин', 'required_rating': 4500},
                
                # Высшие звания (5000-15000)
                {'sort_order': 19, 'name': 'очколизун', 'required_rating': 5000},
                {'sort_order': 20, 'name': 'подшконарник', 'required_rating': 6000},
                {'sort_order': 21, 'name': 'милый блеваш', 'required_rating': 7000},
                {'sort_order': 22, 'name': 'знатный хачеглот', 'required_rating': 8000},
                {'sort_order': 23, 'name': 'знойный пивозавр', 'required_rating': 9000},
                {'sort_order': 24, 'name': 'местный кореш', 'required_rating': 10000},
                {'sort_order': 25, 'name': 'патлатый коммерс', 'required_rating': 11000},
                {'sort_order': 26, 'name': 'лютый кишкоблуд', 'required_rating': 12000},
                {'sort_order': 27, 'name': 'пацан с нетрадиционным вероисповеданием', 'required_rating': 13000},
                {'sort_order': 28, 'name': 'знойный пёс', 'required_rating': 14000},
                
                # Элитные звания (15000-30000)
                {'sort_order': 29, 'name': 'почетный участник клуба Любителей пощекотать очко', 'required_rating': 15000},
                {'sort_order': 30, 'name': 'кошачья сладость', 'required_rating': 17000},
                {'sort_order': 31, 'name': 'сочный макчикен', 'required_rating': 19000},
                {'sort_order': 32, 'name': 'уважаемый Ромой', 'required_rating': 21000},
                {'sort_order': 33, 'name': 'бородатый стриптизер', 'required_rating': 23000},
                {'sort_order': 34, 'name': 'шпротный магнат', 'required_rating': 25000},
                {'sort_order': 35, 'name': 'тепленький лосось', 'required_rating': 27000},
                
                # Легендарные звания (30000+)
                {'sort_order': 36, 'name': 'слюнявый потрох', 'required_rating': 30000},
                {'sort_order': 37, 'name': 'главный по подливе', 'required_rating': 32000},
                {'sort_order': 38, 'name': 'чехольчик для сраки', 'required_rating': 34000},
                {'sort_order': 39, 'name': 'священный заглотыш', 'required_rating': 36000},
                {'sort_order': 40, 'name': 'волосатый обмылок', 'required_rating': 38000},
                {'sort_order': 41, 'name': 'господин жопа', 'required_rating': 40000},
                {'sort_order': 42, 'name': 'сектант', 'required_rating': 42000},
                {'sort_order': 43, 'name': 'снюсоед', 'required_rating': 44000},
                {'sort_order': 44, 'name': 'говяжий вафел', 'required_rating': 46000},
                {'sort_order': 45, 'name': 'старший по пердежу', 'required_rating': 48000},
                {'sort_order': 46, 'name': 'пельмень судьбы', 'required_rating': 50000},
                {'sort_order': 47, 'name': 'разргретый мужичок', 'required_rating': 52000},
                {'sort_order': 48, 'name': 'вибрирующий гусь', 'required_rating': 54000},
                {'sort_order': 49, 'name': 'ночной рыгач', 'required_rating': 56000},
                {'sort_order': 50, 'name': 'БОГ ЧАТА', 'required_rating': 60000},
            ]
            
            # Удаляем старые звания и создаем новые
            Rank.objects.all().delete()
            self.stdout.write('  - Удалены старые звания')
            
            for rank_data in ranks_data:
                rank = Rank.objects.create(**rank_data)
                ranks_created += 1
                self.stdout.write(f'  ✓ Создано звание: {rank.name} (рейтинг: {rank.required_rating})')
            
            # Создаем баллы за типы сообщений
            points_created = 0
            points_data = [
                {'message_type': 'text', 'points': 2, 'description': 'Обычное текстовое сообщение'},
                {'message_type': 'voice', 'points': 1, 'description': 'Голосовое сообщение'},
                {'message_type': 'photo', 'points': 3, 'description': 'Фотография'},
                {'message_type': 'video', 'points': 3, 'description': 'Видео'},
                {'message_type': 'sticker', 'points': 1, 'description': 'Стикер'},
                {'message_type': 'document', 'points': 1, 'description': 'Документ'},
                {'message_type': 'audio', 'points': 2, 'description': 'Аудиофайл'},
                {'message_type': 'video_note', 'points': 3, 'description': 'Видеосообщение'},
                {'message_type': 'forward', 'points': 1, 'description': 'Пересланное сообщение'},
                {'message_type': 'other', 'points': 1, 'description': 'Другие типы сообщений'},
            ]
            
            # Удаляем старые баллы и создаем новые
            MessageTypePoints.objects.all().delete()
            self.stdout.write('  - Удалены старые баллы за типы сообщений')
            
            for point_data in points_data:
                point = MessageTypePoints.objects.create(**point_data)
                points_created += 1
                self.stdout.write(f'  ✓ Созданы баллы: {point.get_message_type_display()} - {point.points}')
            
            # Восстанавливаем звания для всех существующих пользователей
            self.restore_user_ranks()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Инициализация завершена!\n'
                f'   Создано званий: {ranks_created}\n'
                f'   Создано типов баллов: {points_created}'
            )
        )
