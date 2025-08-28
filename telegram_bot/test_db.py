import asyncio
import asyncpg

async def test_db_connection():
    try:
        conn = await asyncpg.connect('postgresql://friend_bot_user:friend_bot_password@postgres:5432/friend_bot')
        print("✅ Подключение к базе данных успешно!")
        
        # Проверяем таблицы
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        print(f"📋 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        await conn.close()
        print("✅ Соединение закрыто")
        
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_db_connection())
