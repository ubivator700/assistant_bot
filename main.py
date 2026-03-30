"""Точка входа бота."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import TELEGRAM_TOKEN, BOT_MODE, WEBHOOK_URL, ADMIN_CHAT_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Инициализация при старте бота."""
    from services.reminder_service import load_and_schedule_all
    await load_and_schedule_all(bot)
    logger.info("Reminders loaded and scheduled.")

    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(ADMIN_CHAT_ID, "✅ Бот запущен.")
        except Exception:
            pass


async def on_shutdown(bot: Bot) -> None:
    """Завершение работы."""
    from services.reminder_service import scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(ADMIN_CHAT_ID, "🛑 Бот остановлен.")
        except Exception:
            pass
    await bot.session.close()


async def main() -> None:
    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Регистрация роутеров
    from bot.handlers import ai_chat, expenses, tasks, meetings, notes, goals, reminders, reports
    dp.include_router(ai_chat.router)
    dp.include_router(expenses.router)
    dp.include_router(tasks.router)
    dp.include_router(meetings.router)
    dp.include_router(notes.router)
    dp.include_router(goals.router)
    dp.include_router(reminders.router)
    dp.include_router(reports.router)

    # Middleware для обработки ошибок
    from bot.middleware import ErrorMiddleware
    dp.message.middleware(ErrorMiddleware(bot))

    dp.startup.register(lambda: on_startup(bot))
    dp.shutdown.register(lambda: on_shutdown(bot))

    logger.info("Bot starting in %s mode", BOT_MODE)

    if BOT_MODE == "webhook":
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from bot.healthcheck import create_health_app

        app = create_health_app()

        async def _startup(_app):
            await on_startup(bot)
            await bot.set_webhook(WEBHOOK_URL)
            logger.info("Webhook set: %s", WEBHOOK_URL)

        async def _shutdown(_app):
            await on_shutdown(bot)
            await bot.delete_webhook()

        app.on_startup.append(_startup)
        app.on_shutdown.append(_shutdown)

        webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

        web.run_app(app, host="0.0.0.0", port=8080)
    else:
        await on_startup(bot)
        try:
            await dp.start_polling(bot)
        finally:
            await on_shutdown(bot)


if __name__ == "__main__":
    asyncio.run(main())
