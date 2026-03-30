"""/reminders — список и управление напоминаниями. /morning — утренний бриф."""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from services import db_service
from utils.keyboards import reminder_snooze_keyboard
from utils.formatters import fmt_reminder

router = Router()


@router.message(Command("reminders"))
async def cmd_reminders(message: Message) -> None:
    reminders = await db_service.get_user_reminders(message.from_user.id)
    if not reminders:
        await message.answer("⏰ Нет активных напоминаний.")
        return
    await message.answer("⏰ <b>Твои напоминания:</b>", parse_mode="HTML")
    for r in reminders:
        await message.answer(
            fmt_reminder(r),
            reply_markup=reminder_snooze_keyboard(r.id),
        )


@router.callback_query(F.data.startswith("snooze:"))
async def cb_snooze(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    period = parts[1]   # 1h или 1d
    reminder_id = int(parts[2])

    now = datetime.now()
    if period == "1h":
        new_trigger = now + timedelta(hours=1)
        label = "+1 час"
    else:
        new_trigger = now + timedelta(days=1)
        label = "+1 день"

    reminder = await db_service.snooze_reminder(reminder_id, new_trigger)
    if reminder:
        try:
            from services.reminder_service import schedule_reminder
            schedule_reminder(reminder, callback.bot)
        except Exception:
            pass
        await callback.message.edit_text(
            f"⏰ Отложено на {label}\n{new_trigger.strftime('%d.%m.%Y %H:%M')} — {reminder.text}",
            reply_markup=None,
        )
    await callback.answer(f"Отложено на {label}")


@router.callback_query(F.data.startswith("reminder_delete:"))
async def cb_reminder_delete(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":")[1])
    await db_service.delete_reminder(reminder_id)
    await callback.message.edit_text("🔕 Напоминание удалено.", reply_markup=None)
    await callback.answer("Удалено")


@router.message(Command("morning"))
async def cmd_morning(message: Message) -> None:
    await message.answer("🌅 Готовлю утренний бриф...")
    try:
        from services.reminder_service import send_morning_brief_to_user
        await send_morning_brief_to_user(message.bot, message.from_user.id)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
