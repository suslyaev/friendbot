from django.core.management.base import BaseCommand
from friend_bot.models import TelegramGroup


class Command(BaseCommand):
    help = 'Тестирует поиск группы'

    def handle(self, *args, **options):
        self.stdout.write('Тестирую поиск группы...')
        
        try:
            group = TelegramGroup.objects.get(telegram_id=-1001553030965)
            self.stdout.write(f'✓ Найдена группа: {group.title} (ID: {group.telegram_id})')
        except TelegramGroup.DoesNotExist:
            self.stdout.write('❌ Группа не найдена!')
        
        # Показываем все группы
        groups = TelegramGroup.objects.all()
        self.stdout.write(f'\nВсего групп: {groups.count()}')
        for g in groups:
            self.stdout.write(f'  - {g.title} (ID: {g.telegram_id})')

