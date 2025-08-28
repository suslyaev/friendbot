from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
import os
import json
from .models import TelegramGroup, Message, User, UserInGroup, DailyCheckin
from django.db import models


@staff_member_required
def group_summary_view(request, group_id):
    """Страница для создания резюме по группе"""
    group = get_object_or_404(TelegramGroup, id=group_id)
    
    if request.method == 'POST':
        start_datetime_str = request.POST.get('start_datetime')
        end_datetime_str = request.POST.get('end_datetime')
        custom_prompt = request.POST.get('custom_prompt')
        
        if start_datetime_str and end_datetime_str:
            try:
                start_datetime = datetime.strptime(start_datetime_str, '%Y-%m-%dT%H:%M')
                end_datetime = datetime.strptime(end_datetime_str, '%Y-%m-%dT%H:%M')
                
                # Получаем сообщения за указанный период
                messages = Message.objects.filter(
                    chat=group,
                    date__gte=start_datetime,
                    date__lte=end_datetime
                ).order_by('date')
                
                if messages.exists():
                    # Создаем резюме с помощью OpenAI
                    summary = create_chat_summary(messages, group, start_datetime, end_datetime, custom_prompt)
                    
                    # Отладочная информация
                    try:
                        secret_key = settings.SECRET_KEY
                        print(f"🔍 SECRET_KEY получен: {secret_key[:20] if secret_key else 'None'}...")
                    except Exception as e:
                        print(f"❌ Ошибка получения SECRET_KEY: {e}")
                        secret_key = "default_secret_key"
                    
                    print(f"🔍 Передаем auth_token в шаблон: {secret_key[:20] if secret_key else 'None'}...")
                    
                    return render(request, 'friend_bot/summary_result.html', {
                        'group': group,
                        'summary': summary,
                        'start_datetime': start_datetime_str,
                        'end_datetime': end_datetime_str,
                        'message_count': messages.count(),
                        'auth_token': secret_key
                    })
                else:
                    messages.error(request, 'За указанный период сообщений не найдено')
            except ValueError:
                messages.error(request, 'Неверный формат даты и времени')
    
    return render(request, 'friend_bot/group_summary.html', {
        'group': group,
        'auth_token': settings.SECRET_KEY
    })


def create_chat_summary(messages, group, start_datetime, end_datetime, custom_prompt=None):
    """Создает резюме чата с помощью OpenAI API"""
    try:
        from openai import OpenAI
        import requests
        
        # Настройки для обхода блокировки
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        
        # Создаем клиент с возможностью кастомного base_url
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # Формируем контекст для анализа
        period_duration = end_datetime - start_datetime
        days = period_duration.days
        hours = period_duration.seconds // 3600
        
        if days > 0:
            period_text = f"{days} {'день' if days == 1 else 'дня' if days < 5 else 'дней'}"
        elif hours > 0:
            period_text = f"{hours} {'час' if hours == 1 else 'часа' if hours < 5 else 'часов'}"
        else:
            period_text = "несколько минут"
        
        # Формируем сообщения с ссылками
        messages_with_links = []
        for msg in messages:
            # Убираем -100 из chat_id для ссылки
            chat_id_clean = str(group.telegram_id).replace('-100', '')
            message_link = f"https://t.me/c/{chat_id_clean}/{msg.telegram_id}"
            
            user_info = f"@{msg.user.username}" if msg.user.username else f"{msg.user.first_name}"
            message_text = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
            
            messages_with_links.append(f"[{user_info}: {message_text}]({message_link})")
        
        messages_text = "\n".join(messages_with_links)
        
        # Используем кастомный промпт или стандартный
        if custom_prompt:
            context = custom_prompt
        else:
            context = f"""
            Ты - друг, который следил за чатом в группе "{group.title}" и теперь рассказывает другому другу, что он пропустил за {period_text} (с {start_datetime.strftime('%d.%m %H:%M')} по {end_datetime.strftime('%d.%m %H:%M')}).
            
            Твой стиль - это дружеская беседа за пивом, живая, эмоциональная, с шутками и личными комментариями.
            
            Статистика для справки:
            - Сообщений за период: {messages.count()}
            - Активных участников: {UserInGroup.objects.filter(group=group, is_active=True).count()}
            
            Создай живое резюме в HTML-разметке, которое включает:
            1. Основные темы обсуждений (2-3 главные темы с эмоциями)
            2. Самые активные участники (с личными комментариями)
            3. Интересные моменты или цитаты (если есть)
            4. Эмоциональное завершение
            
            Правила стиля:
            - НЕ НАЧИНАЙ с приветствия - сразу переходи к делу
            - Обращайся к участникам во множественном числе: "ребятки", "братишки", "сестренки", "ребятушки", "друзья", "товарищи"
            - Пиши как друг рассказывает другу: "блин, здарова", "так, ребятки", "ну это никуда не годится"
            - Используй разговорную речь, междометия, эмоции
            - Комментируй активность: "обсусситесь", "запасайтесь попкорном", "плачущий ребенок и никаких сплетен??"
            - Используй только базовые HTML-теги: <b>, <i>, <u>
            - НЕ используй сложные теги: <pre>, <ul>, <li>, <code>
            - Простая разметка для лучшей совместимости с Telegram
            - При поздравлениях обращайся через ники (@username)
            - При повествовании используй имена (Иван, Мария)
            - Цифры упоминай только если они выдающиеся/интересные
            - БЕЗ лишних отступов и пустых строк - пиши компактно
            - Добавляй <tg-spoiler></tg-spoiler> для интересных фактов
            - Обязательно используй ссылки на сообщения когда рассказываешь о темах или цитатах в формате специальном телеграммном, ссылки оформляй тегом <a href="https://t.me/c/ЧАТ_АЙДИ/СООБЩЕНИЕ_АЙДИ">ссылка</a>
            
            ОГРАНИЧЕНИЯ:
            - Максимальная длина сообщения: 3500 символов (для Telegram)
            - Избегай длинных абзацев - разбивай на короткие
            - Без лишних HTML-тегов - только необходимые
            - Компактный формат без пустых строк
            """
        
        # Добавляем сообщения с ссылками в контекст
        if messages_with_links:
            context += f"\n\nСообщения для анализа:\n" + "\n".join(messages_with_links[:30])
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты - друг, который следил за чатом и теперь рассказывает другому другу, что тот пропустил. Твой стиль - живая дружеская беседа за пивом, эмоциональная, с шутками и личными комментариями. Используй ТОЛЬКО простые HTML-теги: <b>, <i>, <u>. НЕ используй <pre>, <ul>, <li>, <code>. НЕ НАЧИНАЙ с приветствия, обращайся к участникам во множественном числе (ребятки, братишки, сестренки, друзья). Пиши компактно без лишних отступов. Добавляй <tg-spoiler></tg-spoiler> для интересных фактов. Обязательно используй ссылки на сообщения когда рассказываешь о темах или цитатах в формате специальном телеграммном, ссылки оформляй тегом <a href='https://t.me/c/{chat_id_clean}/{msg.telegram_id}'>ссылка</a>."},
                {"role": "user", "content": context}
            ],
            max_tokens=1200,
            temperature=0.9
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"<b>Ошибка при создании резюме:</b> {str(e)}"


@staff_member_required
def group_statistics_view(request, group_id):
    """Страница со статистикой по группе"""
    group = get_object_or_404(TelegramGroup, id=group_id)
    
    # Статистика по пользователям
    users_stats = []
    for user_in_group in group.useringroup_set.filter(is_active=True):
        user = user_in_group.user
        message_count = Message.objects.filter(user=user, chat=group).count()
        checkin = DailyCheckin.objects.filter(user=user, group=group).first()
        
        users_stats.append({
            'user': user,
            'message_count': message_count,
            'rating': user_in_group.rating,
            'coefficient': user_in_group.coefficient,
            'consecutive_days': checkin.consecutive_days if checkin else 0,
        })
    
    # Сортируем по рейтингу
    users_stats.sort(key=lambda x: x['rating'], reverse=True)
    
    # Статистика по типам сообщений
    message_types = Message.objects.filter(chat=group).values('message_type').annotate(
        count=models.Count('id')
    ).order_by('-count')
    
    context = {
        'group': group,
        'users_stats': users_stats,
        'message_types': message_types,
        'total_messages': Message.objects.filter(chat=group).count(),
        'total_users': len(users_stats),
    }
    
    return render(request, 'friend_bot/group_statistics.html', context)


@staff_member_required
def dashboard_view(request):
    """Главная страница админки"""
    groups = TelegramGroup.objects.filter(is_active=True)
    
    # Общая статистика
    total_users = User.objects.filter(is_active=True).count()
    total_messages = Message.objects.count()
    total_groups = groups.count()
    
    # Топ пользователей по рейтингу
    top_users = UserInGroup.objects.select_related('user', 'group').order_by('-rating')[:10]
    
    context = {
        'groups': groups,
        'total_users': total_users,
        'total_messages': total_messages,
        'total_groups': total_groups,
        'top_users': top_users,
    }
    
    return render(request, 'friend_bot/dashboard.html', context)
