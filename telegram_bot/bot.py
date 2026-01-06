import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import Message, ChatType
import asyncpg
import aiohttp
from dotenv import load_dotenv
import pytz

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://django_app:8000/api/ingest/message/')
INGEST_TOKEN = os.getenv('INGEST_TOKEN')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN")

if not DATABASE_URL:
    logger.warning("DATABASE_URL не задан — бот работает в REST-режиме (без прямого доступа к БД)")
if not INGEST_TOKEN:
    raise ValueError("Не найден INGEST_TOKEN для доступа к Django API")

# Инициализация бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


async def get_db_connection():
    """Получает соединение с базой данных"""
    return await asyncpg.connect(DATABASE_URL)


async def get_or_create_user(message: Message):
    """Получает или создает пользователя в базе данных"""
    conn = await get_db_connection()
    try:
        # Проверяем существование пользователя
        user_row = await conn.fetchrow(
            "SELECT id FROM friend_bot_user WHERE telegram_id = $1",
            message.from_user.id
        )
        
        if user_row:
            user_id = user_row['id']
        else:
            # Создаем нового пользователя
            user_id = await conn.fetchval(
                """
                INSERT INTO friend_bot_user (telegram_id, first_name, last_name, username, is_active, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                message.from_user.id,
                message.from_user.first_name,
                message.from_user.last_name or '',
                message.from_user.username or '',
                True,
                datetime.now()
            )
        
        return user_id
    finally:
        await conn.close()


async def get_or_create_group(message: Message):
    """Получает или создает группу в базе данных"""
    conn = await get_db_connection()
    try:
        # Проверяем существование группы
        group_row = await conn.fetchrow(
            "SELECT id FROM friend_bot_telegramgroup WHERE telegram_id = $1",
            message.chat.id
        )
        
        if group_row:
            group_id = group_row['id']
        else:
            # Создаем новую группу
            group_id = await conn.fetchval(
                """
                INSERT INTO friend_bot_telegramgroup (telegram_id, title, is_active)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                message.chat.id,
                message.chat.title or f"Группа {message.chat.id}",
                True
            )
        
        return group_id
    finally:
        await conn.close()


async def ensure_user_in_group(user_id: int, group_id: int):
    """Убеждается, что пользователь находится в группе"""
    conn = await get_db_connection()
    try:
        # Проверяем существование связи
        existing = await conn.fetchrow(
            "SELECT id FROM friend_bot_useringroup WHERE user_id = $1 AND group_id = $2",
            user_id, group_id
        )
        
        if not existing:
            # Создаем связь
            await conn.execute(
                """
                INSERT INTO friend_bot_useringroup (user_id, group_id, joined_at, is_active)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, group_id, datetime.now(), True
            )
    finally:
        await conn.close()


async def save_message(message: Message, user_id: int, group_id: int):
    """Отправляет сообщение в Django REST API"""
    # Определяем тип сообщения
    message_type = 'text'
    text_content = ''

    if message.text:
        message_type = 'text'
        text_content = message.text
    elif message.voice:
        message_type = 'voice'
    elif message.photo:
        message_type = 'photo'
    elif message.video:
        message_type = 'video'
    elif message.sticker:
        message_type = 'sticker'
    elif message.document:
        message_type = 'document'
    elif message.audio:
        message_type = 'audio'
    elif message.video_note:
        message_type = 'video_note'
    elif message.forward_from:
        message_type = 'forward'
    else:
        message_type = 'other'

    payload = {
        'telegram_message_id': message.message_id,
        'date_iso': message.date.isoformat(),
        'user_telegram_id': message.from_user.id,
        'user_first_name': message.from_user.first_name or '',
        'user_last_name': message.from_user.last_name or '',
        'user_username': message.from_user.username or '',
        'chat_telegram_id': message.chat.id,
        'chat_title': getattr(message.chat, 'title', '') or '',
        'message_type': message_type,
        'text': text_content,
        'related_telegram_message_id': message.reply_to_message.message_id if getattr(message, 'reply_to_message', None) else None,
        'auth_token': INGEST_TOKEN,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(DJANGO_API_URL, json=payload, timeout=15) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error(f"Ingest error {resp.status}: {body}")
            else:
                logger.info("Сообщение отправлено в Django API")


async def update_user_rating(user_id: int, group_id: int, message_type: str):
    """Обновляет рейтинг пользователя"""
    conn = await get_db_connection()
    try:
        # Получаем или создаем рейтинг
        rating_row = await conn.fetchrow(
            "SELECT id, rating, coefficient FROM friend_bot_rating WHERE user_id = $1 AND group_id = $2",
            user_id, group_id
        )
        
        if rating_row:
            rating_id = rating_row['id']
            current_rating = rating_row['rating']
            coefficient = rating_row['coefficient']
        else:
            # Создаем новый рейтинг
            rating_id = await conn.fetchval(
                """
                INSERT INTO friend_bot_rating (user_id, group_id, rating, coefficient, last_updated)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_id, group_id, 0, 1, datetime.now()
            )
            current_rating = 0
            coefficient = 1
        
        # Вычисляем очки за сообщение (берем из БД таблицы friend_bot_messagetypepoints)
        base_points = await get_points_for_type(message_type)
        points = base_points * coefficient
        new_rating = current_rating + points
        
        # Обновляем рейтинг
        await conn.execute(
            "UPDATE friend_bot_rating SET rating = $1, last_updated = $2 WHERE id = $3",
            new_rating, datetime.now(), rating_id
        )
        
    finally:
        await conn.close()


async def update_daily_checkin(user_id: int, group_id: int):
    """Обновляет ежедневный чекин пользователя"""
    conn = await get_db_connection()
    try:
        # Получаем или создаем чекин
        checkin_row = await conn.fetchrow(
            "SELECT id, consecutive_days, last_checkin FROM friend_bot_dailycheckin WHERE user_id = $1 AND group_id = $2",
            user_id, group_id
        )
        
        # Используем московское время для соответствия Django
        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(moscow_tz)
        today = now.date()
        
        if checkin_row:
            checkin_id = checkin_row['id']
            consecutive_days = checkin_row['consecutive_days']
            last_checkin = checkin_row['last_checkin']
            
            if last_checkin:
                last_date = last_checkin.date()
                days_diff = (today - last_date).days
                
                if days_diff == 1:
                    # Следующий день - увеличиваем счетчик
                    consecutive_days += 1
                elif days_diff > 1:
                    # Прошло больше дня - сбрасываем счетчик
                    consecutive_days = 0
            
            # Обновляем чекин
            await conn.execute(
                "UPDATE friend_bot_dailycheckin SET consecutive_days = $1, last_checkin = $2 WHERE id = $3",
                consecutive_days, now, checkin_id
            )
        else:
            # Создаем новый чекин
            await conn.execute(
                """
                INSERT INTO friend_bot_dailycheckin (user_id, group_id, consecutive_days, last_checkin)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, group_id, 1, now
            )
        
        # Обновляем коэффициент в рейтинге
        await conn.execute(
            """
            UPDATE friend_bot_rating 
            SET coefficient = GREATEST(1, (SELECT consecutive_days FROM friend_bot_dailycheckin WHERE user_id = $1 AND group_id = $2) / 7 + 1)
            WHERE user_id = $1 AND group_id = $2
            """,
            user_id, group_id
        )
        
    finally:
        await conn.close()


async def get_points_for_type(message_type: str) -> int:
    """Возвращает базовые очки за тип сообщения из таблицы friend_bot_messagetypepoints (по умолчанию 5)."""
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT points FROM friend_bot_messagetypepoints WHERE message_type = $1",
            message_type
        )
        if row and row.get('points') is not None:
            return int(row['points'])
        return 5
    finally:
        await conn.close()


@dp.message_handler(commands=['start'])
async def start_command(message: Message):
    """Обработчик команды /start"""
    await message.reply("Привет! Я бот для отслеживания активности в группах. Просто отправляй сообщения, и я буду их записывать!")


@dp.message_handler(commands=['stat'])
async def stat_command(message: Message):
    """Обработчик команды /stat - показывает статистику пользователей в группе"""
    try:
        logger.info(f"Получена команда stat от {message.from_user.first_name} в чате {message.chat.title} (тип: {message.chat.type})")
        
        # Проверяем, что команда вызвана в группе
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            logger.info(f"Команда stat вызвана не в группе: {message.chat.type}")
            await message.reply("Эта команда работает только в группах!")
            return
        
        logger.info(f"Команда stat вызвана в группе, продолжаем обработку")
        
        # Получаем статистику через Django API
        try:
            import aiohttp
            
            # URL для получения статистики (нужно создать соответствующий endpoint в Django)
            api_url = DJANGO_API_URL.replace('/api/ingest/message/', '/api/statistics/')
            
            logger.info(f"Запрос к Django API: {api_url}")
            
            # Данные для запроса
            data = {
                'chat_id': message.chat.id,
                'auth_token': INGEST_TOKEN
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('success'):
                            stat_text = result.get('statistics', 'Статистика недоступна')
                            await message.reply(stat_text, parse_mode='HTML')
                            logger.info(f"Статистика успешно отправлена")
                        else:
                            await message.reply("❌ Ошибка при получении статистики")
                            logger.error(f"API вернул ошибку: {result}")
                    else:
                        await message.reply("❌ Не удалось получить статистику")
                        logger.error(f"API вернул статус {response.status}")
                        
        except Exception as e:
            logger.error(f"Ошибка при запросе к Django API: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback: пытаемся получить статистику напрямую из БД
            logger.info("Пробуем получить статистику напрямую из БД...")
            try:
                conn = await get_db_connection()
                try:
                    logger.info(f"Подключение к БД установлено, ищем группу с telegram_id: {message.chat.id}")
                    
                    # Получаем всех пользователей по рейтингу
                    rows = await conn.fetch("""
                        SELECT 
                            u.first_name,
                            u.username,
                            uig.rating,
                            uig.message_count,
                            uig.coefficient,
                            uig.last_activity,
                            r.name as rank_name,
                            COALESCE(dc.consecutive_days, 0) as consecutive_days
                        FROM friend_bot_useringroup uig
                        JOIN friend_bot_user u ON uig.user_id = u.id
                        LEFT JOIN friend_bot_rank r ON uig.rank_id = r.id
                        LEFT JOIN friend_bot_dailycheckin dc ON dc.user_id = u.id AND dc.group_id = uig.group_id
                        WHERE uig.group_id = (
                            SELECT id FROM friend_bot_telegramgroup WHERE telegram_id = $1
                        )
                        AND uig.is_active = true
                        ORDER BY uig.rating DESC
                    """, message.chat.id)
                    
                    logger.info(f"Найдено пользователей в группе: {len(rows)}")
                    
                    if not rows:
                        await message.reply("В этой группе пока нет статистики.")
                        return
                    
                    # Формируем сообщение со статистикой
                    stat_text = "📊 <b>Статистика пользователей в группе:</b>\n\n"
                    
                    moscow_tz = pytz.timezone('Europe/Moscow')
                    
                    for i, row in enumerate(rows, 1):
                        username = f"@{row['username']}" if row['username'] else row['first_name']
                        rank_name = row['rank_name'] if row['rank_name'] else "Нет звания"
                        coefficient = f"{row['coefficient']:.1f}x"
                        consecutive_days = row['consecutive_days'] or 0
                        last_activity = row['last_activity']

                        # Форматируем дату последней активности (московское время)
                        if last_activity:
                            try:
                                # asyncpg возвращает datetime объекты, которые могут быть naive или aware
                                if isinstance(last_activity, datetime):
                                    # Если дата без timezone, предполагаем что это UTC (стандарт для PostgreSQL)
                                    if last_activity.tzinfo is None:
                                        utc_tz = pytz.UTC
                                        last_activity = utc_tz.localize(last_activity)
                                    
                                    # Конвертируем в московское время
                                    last_activity_local = last_activity.astimezone(moscow_tz)
                                    last_activity_str = last_activity_local.strftime('%d.%m.%Y %H:%M')
                                else:
                                    # Если это не datetime объект, просто преобразуем в строку
                                    last_activity_str = str(last_activity)
                            except Exception as e:
                                logger.error(f"Ошибка форматирования даты для пользователя {username}: {e}, raw: {last_activity}, type: {type(last_activity)}")
                                last_activity_str = str(last_activity) if last_activity else "нет данных"
                        else:
                            last_activity_str = "нет данных"
                        
                        # Логируем для отладки (можно убрать после проверки)
                        logger.debug(f"Пользователь {username}: last_activity={last_activity}, formatted={last_activity_str}")
                        
                        stat_text += (
                            f"{i}. <b>{username}</b>\n"
                            f"   🏆 {rank_name}\n"
                            f"   📈 Рейтинг: {row['rating']}\n"
                            f"   💬 Сообщений: {row['message_count']}\n"
                            f"   ⚡ Коэффициент: {coefficient}\n"
                            f"   🔥 Непрерывных дней: {consecutive_days}\n"
                            f"   ⏰ Последняя активность: {last_activity_str}\n\n"
                        )
                    
                    # Добавляем общую статистику группы
                    group_stats = await conn.fetchrow("""
                        SELECT 
                            COUNT(DISTINCT uig.user_id) as total_users,
                            SUM(uig.message_count) as total_messages,
                            AVG(uig.rating) as avg_rating
                        FROM friend_bot_useringroup uig
                        WHERE uig.group_id = (
                            SELECT id FROM friend_bot_telegramgroup WHERE telegram_id = $1
                        )
                    """, message.chat.id)
                    
                    if group_stats:
                        stat_text += (
                            f"📈 <b>Общая статистика группы:</b>\n"
                            f"👥 Пользователей: {group_stats['total_users']}\n"
                            f"💬 Всего сообщений: {group_stats['total_messages']}\n"
                            f"📊 Средний рейтинг: {int(group_stats['avg_rating'] or 0)}"
                        )
                    
                    logger.info(f"Статистика сформирована, отправляем сообщение длиной {len(stat_text)} символов")
                    
                    # Отправляем статистику
                    await message.reply(stat_text, parse_mode='HTML')
                    logger.info(f"Статистика успешно отправлена")
                    
                finally:
                    await conn.close()
                    
            except Exception as db_error:
                logger.error(f"Ошибка при получении статистики из БД: {db_error}")
                await message.reply("❌ Произошла ошибка при получении статистики.")
            
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        import traceback
        traceback.print_exc()
        await message.reply("❌ Произошла ошибка при получении статистики.")


# Общий обработчик сообщений - должен быть в конце, чтобы не перехватывать команды
@dp.message_handler(content_types=types.ContentTypes.ANY)
async def handle_all_messages(message: Message):
    """Обрабатывает все входящие сообщения"""
    try:
        # Обрабатываем только сообщения из групп
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return
        
        # В REST-режиме не требуются локальные id; отправляем прямо в Django
        await save_message(message, user_id=0, group_id=0)
        
        logger.info(f"Обработано сообщение от {message.from_user.first_name} в группе {message.chat.title}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")


async def main():
    """Главная функция"""
    logger.info("Запуск Telegram бота...")
    
    try:
        # Запускаем бота
        await dp.start_polling()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
