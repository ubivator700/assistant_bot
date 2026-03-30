"""Middleware для перехвата и логирования ошибок."""
from __future__ import annotations

import logging
import traceback
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message

from config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            user_id = getattr(event.from_user, "id", "?")
            text = getattr(event, "text", "?")
            tb = traceback.format_exc()
            logger.error("Unhandled error for user=%s text=%r:\n%s", user_id, text, tb)

            if ADMIN_CHAT_ID:
                try:
                    error_msg = (
                        f"⚠️ <b>Ошибка бота</b>\n"
                        f"👤 Пользователь: <code>{user_id}</code>\n"
                        f"💬 Сообщение: <code>{str(text)[:200]}</code>\n"
                        f"❌ Ошибка: <code>{str(exc)[:300]}</code>"
                    )
                    await self.bot.send_message(ADMIN_CHAT_ID, error_msg, parse_mode="HTML")
                except Exception:
                    pass

            try:
                await event.answer("❌ Произошла ошибка. Попробуй ещё раз.")
            except Exception:
                pass
