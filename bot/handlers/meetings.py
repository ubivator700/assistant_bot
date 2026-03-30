"""/meetings, /today — встречи."""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services import db_service
from utils.formatters import fmt_meetings_list

router = Router()


@router.message(Command("meetings"))
async def cmd_meetings(message: Message) -> None:
    now = datetime.now()
    until = now + timedelta(days=7)
    meetings = await db_service.get_meetings(message.from_user.id, since=now, until=until)
    text = fmt_meetings_list(meetings)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59)
    meetings = await db_service.get_today_meetings(
        message.from_user.id, today_start, today_end
    )
    if not meetings:
        await message.answer("📅 Сегодня встреч нет. Свободный день! 🎉")
        return
    text = fmt_meetings_list(meetings)
    await message.answer(f"📅 <b>Сегодня, {now.strftime('%d.%m.%Y')}:</b>\n\n" + text, parse_mode="HTML")
