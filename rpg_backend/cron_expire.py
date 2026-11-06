"""
Крон-скрипт: деактивация просроченных подписок.
Запуск раз в час через cron: python /app/cron_expire.py
"""
import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "rpg.db"


async def main():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        # Деактивируем пользователей с истёкшей подпиской
        # (только если не через Boosty — у них subscription_expires пустое)
        cursor = await db.execute(
            """UPDATE users SET is_active = 0
               WHERE is_active = 1
                 AND subscription_expires != ''
                 AND datetime(subscription_expires) < datetime('now')"""
        )
        await db.commit()
        print(f"Deactivated {cursor.rowcount} expired subscriptions")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
