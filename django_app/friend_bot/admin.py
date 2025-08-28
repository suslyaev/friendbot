from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from .models import Rank, TelegramGroup, User, UserInGroup, Message, DailyCheckin, MessageTypePoints


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ['name', 'sort_order', 'required_rating']
    list_editable = ['sort_order', 'required_rating']
    list_display_links = ['name']
    ordering = ['sort_order']
    search_fields = ['name']


@admin.register(TelegramGroup)
class TelegramGroupAdmin(admin.ModelAdmin):
    list_display = ['title', 'telegram_id', 'is_active', 'user_count', 'summary_actions']
    list_filter = ['is_active']
    search_fields = ['title', 'telegram_id']
    
    def user_count(self, obj):
        return UserInGroup.objects.filter(group=obj, is_active=True).count()
    user_count.short_description = 'Активных пользователей'
    
    def summary_actions(self, obj):
        """Кнопки для работы с группой"""
        from django.utils.html import format_html
        
        summary_url = f'/group/{obj.id}/summary/'
        return format_html(
            '<a class="button" href="{}">📊 Резюмировать активность</a>',
            summary_url
        )
    summary_actions.short_description = 'Действия'
    summary_actions.allow_tags = True


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'username', 'telegram_id', 'total_rating', 'max_consecutive_days', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['first_name', 'last_name', 'username', 'telegram_id']
    readonly_fields = ['created_at', 'total_rating', 'max_consecutive_days']
    
    def total_rating(self, obj):
        """Показывает общий рейтинг пользователя по всем группам"""
        total = UserInGroup.objects.filter(user=obj).aggregate(total=models.Sum('rating'))['total'] or 0
        return total
    total_rating.short_description = 'Общий рейтинг'
    
    def max_consecutive_days(self, obj):
        """Показывает максимальное количество непрерывных дней среди всех групп"""
        max_days = DailyCheckin.objects.filter(user=obj).aggregate(max_days=models.Max('consecutive_days'))['max_days'] or 0
        return max_days
    max_consecutive_days.short_description = 'Макс. непрерывные дни'


@admin.register(UserInGroup)
class UserInGroupAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'rating', 'message_count', 'rank', 'coefficient', 'consecutive_days_display', 'last_activity', 'is_active']
    list_filter = ['is_active', 'joined_at', 'group', 'rank']
    search_fields = ['user__first_name', 'user__last_name', 'group__title']
    readonly_fields = ['rating', 'message_count', 'coefficient', 'last_activity', 'consecutive_days_display']
    ordering = ['-rating']
    
    def consecutive_days_display(self, obj):
        """Показывает непрерывные дни из DailyCheckin"""
        try:
            checkin = DailyCheckin.objects.get(user=obj.user, group=obj.group)
            return checkin.consecutive_days
        except DailyCheckin.DoesNotExist:
            return 0
    consecutive_days_display.short_description = 'Непрерывные дни'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'chat', 'message_type', 'date', 'text_preview']
    list_filter = ['message_type', 'date', 'chat']
    search_fields = ['user__first_name', 'user__last_name', 'text', 'chat__title']
    readonly_fields = ['telegram_id', 'date']
    date_hierarchy = 'date'
    
    def text_preview(self, obj):
        if obj.text:
            return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
        return '-'
    text_preview.short_description = 'Текст'


@admin.register(DailyCheckin)
class DailyCheckinAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'consecutive_days', 'last_checkin']
    list_filter = ['group', 'consecutive_days', 'last_checkin']
    search_fields = ['user__first_name', 'user__last_name', 'group__title']
    readonly_fields = ['last_checkin']
    ordering = ['-consecutive_days']


@admin.register(MessageTypePoints)
class MessageTypePointsAdmin(admin.ModelAdmin):
    list_display = ['message_type', 'points', 'description']
    list_editable = ['points']
    search_fields = ['message_type', 'description']
