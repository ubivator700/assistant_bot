"""Скрипт регистрации webhook URL в Telegram."""
import asyncio
import sys

from aiogram import Bot

from config import TELEGRAM_TOKEN, WEBHOOK_URL, BOT_MODE


async def setup() -> None:
    if BOT_MODE != "webhook":
        print("BOT_MODE не webhook. Установи BOT_MODE=webhook в .env")
        sys.exit(1)
    if not WEBHOOK_URL:
        print("WEBHOOK_URL не задан в .env")
        sys.exit(1)

    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.set_webhook(WEBHOOK_URL)
    info = await bot.get_webhook_info()
    print(f"✅ Webhook установлен: {info.url}")
    print(f"   Pending updates: {info.pending_update_count}")
    await bot.session.close()


async def remove() -> None:
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.delete_webhook()
    print("✅ Webhook удалён.")
    await bot.session.close()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if action == "remove":
        asyncio.run(remove())
    else:
        asyncio.run(setup())
