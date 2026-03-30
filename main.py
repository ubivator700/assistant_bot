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


async def wait_for_db(retries: int = 10, delay: float = 3.0) -> bool:
    """Ждёт доступности БД перед стартом."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from config import DATABASE_URL

    for attempt in range(1, retries + 1):
        try:
            engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            logger.info("DB connection OK (attempt %d)", attempt)
            return True
        except Exception as e:
            logger.warning("DB not ready (attempt %d/%d): %s", attempt, retries, e)
            await asyncio.sleep(delay)
    return False


async def on_startup(bot: Bot) -> None:
    """Инициализация при старте бота."""
    # Напоминания загружаем без падения — если БД недоступна, просто пропускаем
    try:
        from services.reminder_service import load_and_schedule_all
        await load_and_schedule_all(bot)
        logger.info("Reminders loaded and scheduled.")
    except Exception as e:
        logger.error("Could not load reminders: %s", e)

    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(ADMIN_CHAT_ID, "✅ Бот запущен.")
        except Exception:
            pass


async def on_shutdown(bot: Bot) -> None:
    """Завершение работы."""
    try:
        from services.reminder_service import scheduler
        if scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception:
        pass

    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(ADMIN_CHAT_ID, "🛑 Бот остановлен.")
        except Exception:
            pass

    await bot.session.close()


async def main() -> None:
    # Ждём БД перед стартом (до 30 секунд)
    db_ready = await wait_for_db(retries=10, delay=3.0)
    if not db_ready:
        logger.error("Cannot connect to DB after 10 attempts. Exiting.")
        raise SystemExit(1)

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
