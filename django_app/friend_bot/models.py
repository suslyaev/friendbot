from django.db import models
from django.utils import timezone
from datetime import timedelta


class Rank(models.Model):
    """Модель званий пользователей"""
    id = models.AutoField(primary_key=True)
    sort_order = models.IntegerField(verbose_name="Порядок сортировки")
    name = models.CharField(max_length=100, verbose_name="Название звания")
    required_rating = models.IntegerField(verbose_name="Необходимый порог рейтинга")
    
    class Meta:
        ordering = ['sort_order']
        verbose_name = "Звание"
        verbose_name_plural = "Звания"
    
    def __str__(self):
        return f"{self.name} (рейтинг: {self.required_rating})"


class TelegramGroup(models.Model):
    """Модель группы в Telegram"""
    id = models.AutoField(primary_key=True)
    telegram_id = models.BigIntegerField(unique=True, verbose_name="ID группы в Telegram")
    title = models.CharField(max_length=255, verbose_name="Название группы")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    
    class Meta:
        verbose_name = "Группа Telegram"
        verbose_name_plural = "Группы Telegram"
    
    def __str__(self):
        return f"{self.title} (ID: {self.telegram_id})"


class User(models.Model):
    """Модель пользователя"""
    id = models.AutoField(primary_key=True)
    telegram_id = models.BigIntegerField(unique=True, verbose_name="ID в Telegram")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Фамилия")
    username = models.CharField(max_length=100, blank=True, verbose_name="Никнейм")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
    
    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} (@{self.username or 'без ника'})"


class UserInGroup(models.Model):
    """Связующая модель пользователя и группы с рейтингом и званием"""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    group = models.ForeignKey(TelegramGroup, on_delete=models.CASCADE, verbose_name="Группа")
    rating = models.IntegerField(default=0, verbose_name="Рейтинг в группе")
    message_count = models.IntegerField(default=0, verbose_name="Количество сообщений")
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Звание в группе")
    coefficient = models.FloatField(default=0.5, verbose_name="Коэффициент непрерывности")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата вступления")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")
    is_active = models.BooleanField(default=True, verbose_name="Активен в группе")
    
    class Meta:
        unique_together = ['user', 'group']
        verbose_name = "Пользователь в группе"
        verbose_name_plural = "Пользователи в группах"
        ordering = ['-rating']
    
    def __str__(self):
        return f"{self.user} в группе {self.group} (рейтинг: {self.rating})"
    
    def get_coefficient(self):
        """Вычисляет коэффициент непрерывности из DailyCheckin"""
        try:
            checkin = DailyCheckin.objects.get(user=self.user, group=self.group)
            if checkin.consecutive_days == 0:
                return 0.5
            elif checkin.consecutive_days == 1:
                return 1.0
            else:
                # Прогрессия: 2 дня = 1.1, 3 дня = 1.2, 4 дня = 1.3, и т.д.
                return 1.0 + (checkin.consecutive_days - 1) * 0.1
        except DailyCheckin.DoesNotExist:
            return 0.5
    
    def add_message_points(self, message_type):
        """Добавляет очки за сообщение с учетом коэффициента"""
        base_points = self.get_base_points(message_type)
        coefficient = self.get_coefficient()
        points = int(base_points * coefficient)  # Округляем в меньшую сторону
        
        old_rating = self.rating
        self.rating += points
        self.message_count += 1
        self.last_activity = timezone.now()
        self.save()
        
        # Проверяем, изменилось ли звание
        old_rank = self.rank
        self.update_rank()
        
        # Возвращаем информацию об изменении звания
        rank_changed = old_rank != self.rank
        return {
            'points': points,
            'old_rating': old_rating,
            'new_rating': self.rating,
            'rank_changed': rank_changed,
            'old_rank': old_rank,
            'new_rank': self.rank
        }
    
    def get_base_points(self, message_type):
        """Возвращает базовые очки за тип сообщения из БД (или 5 по умолчанию)"""
        record = MessageTypePoints.objects.filter(message_type=message_type).values_list('points', flat=True).first()
        return int(record) if record is not None else 5
    
    def update_rank(self):
        """Обновляет звание пользователя на основе рейтинга"""
        try:
            # Получаем все звания, отсортированные по возрастанию required_rating
            ranks = Rank.objects.all().order_by('required_rating')
            
            # Находим самое высокое звание, которое может получить пользователь
            new_rank = None
            for rank in ranks:
                if self.rating >= rank.required_rating:
                    new_rank = rank
                else:
                    break
            
            # Если нашли новое звание и оно отличается от текущего
            if new_rank and self.rank != new_rank:
                old_rank = self.rank
                self.rank = new_rank
                self.save()
                
                # Логируем изменение звания
                print(f"Пользователь {self.user} в группе {self.group} получил новое звание: {old_rank} -> {new_rank} (рейтинг: {self.rating})")
                
        except Exception as e:
            print(f"Ошибка при обновлении звания для пользователя {self.user} в группе {self.group}: {e}")


class Message(models.Model):
    """Модель сообщения"""
    MESSAGE_TYPES = [
        ('text', 'Текст'),
        ('voice', 'Голосовое'),
        ('photo', 'Фото'),
        ('video', 'Видео'),
        ('sticker', 'Стикер'),
        ('document', 'Документ'),
        ('audio', 'Аудио'),
        ('video_note', 'Кружок'),
        ('forward', 'Пересланное'),
        ('other', 'Другое'),
    ]
    
    id = models.AutoField(primary_key=True)
    telegram_id = models.BigIntegerField(verbose_name="ID сообщения в Telegram")
    date = models.DateTimeField(verbose_name="Дата и время")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    chat = models.ForeignKey(TelegramGroup, on_delete=models.CASCADE, verbose_name="Чат")
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, verbose_name="Тип сообщения")
    text = models.TextField(blank=True, verbose_name="Текст сообщения")
    related_message = models.BigIntegerField(null=True, blank=True, verbose_name="ID связанного сообщения в Telegram")
    
    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        indexes = [
            models.Index(fields=['chat', 'date']),
            models.Index(fields=['user', 'date']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.get_message_type_display()} в {self.chat} ({self.date})"


class MessageTypePoints(models.Model):
    """Настраиваемые баллы за тип сообщения"""
    MESSAGE_TYPES = Message.MESSAGE_TYPES
    id = models.AutoField(primary_key=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, unique=True, verbose_name="Тип сообщения")
    points = models.IntegerField(default=5, verbose_name="Баллы за сообщение")
    description = models.CharField(max_length=255, blank=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Баллы за тип сообщения"
        verbose_name_plural = "Баллы за типы сообщений"
        ordering = ["message_type"]

    def __str__(self):
        return f"{self.get_message_type_display()}: {self.points}"


class DailyCheckin(models.Model):
    """Модель ежедневного чекина"""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    group = models.ForeignKey(TelegramGroup, on_delete=models.CASCADE, verbose_name="Группа")
    consecutive_days = models.IntegerField(default=0, verbose_name="Дней непрерывных чекинов")
    last_checkin = models.DateTimeField(verbose_name="Дата последнего чекина")
    
    class Meta:
        unique_together = ['user', 'group']
        verbose_name = "Ежедневный чекин"
        verbose_name_plural = "Ежедневные чекины"
    
    def __str__(self):
        return f"{self.user} в {self.group}: {self.consecutive_days} дней подряд"
    
    def update_checkin(self):
        """Обновляет чекин и считает непрерывные дни"""
        now = timezone.now()
        today = now.date()
        
        if self.last_checkin:
            last_date = self.last_checkin.date()
            days_diff = (today - last_date).days
            
            if days_diff == 1:
                # Следующий день - увеличиваем счетчик
                self.consecutive_days += 1
            elif days_diff > 1:
                # Прошло больше дня - сбрасываем счетчик
                self.consecutive_days = 0
            # Если days_diff == 0, то уже чекинились сегодня
        
        self.last_checkin = now
        self.save()
        
        # Обновляем коэффициент в UserInGroup (используем новую логику)
        try:
            user_in_group = UserInGroup.objects.get(user=self.user, group=self.group)
            if self.consecutive_days == 0:
                user_in_group.coefficient = 0.5
            elif self.consecutive_days == 1:
                user_in_group.coefficient = 1.0
            else:
                # Прогрессия: 2 дня = 1.1, 3 дня = 1.2, 4 дня = 1.3, и т.д.
                user_in_group.coefficient = 1.0 + (self.consecutive_days - 1) * 0.1
            user_in_group.save()
        except UserInGroup.DoesNotExist:
            pass
