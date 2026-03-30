"""/report — генерация Excel-отчётов."""
from __future__ import annotations

import io
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from utils.keyboards import period_keyboard

router = Router()


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    await message.answer(
        "📊 <b>Генерация отчёта</b>\n\nВыбери период:",
        reply_markup=period_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("period:"))
async def cb_report_period(callback: CallbackQuery) -> None:
    period = callback.data.split(":")[1]
    now = datetime.now()
    user_id = callback.from_user.id

    if period == "week":
        date_from = now - timedelta(days=7)
        date_to = now
        label = "неделя"
    elif period == "month":
        date_from = now.replace(day=1, hour=0, minute=0, second=0)
        date_to = now
        label = "месяц"
    elif period == "last_month":
        first_this = now.replace(day=1, hour=0, minute=0, second=0)
        date_to = first_this - timedelta(seconds=1)
        date_from = date_to.replace(day=1, hour=0, minute=0, second=0)
        label = "прошлый месяц"
    else:
        date_from = now.replace(day=1)
        date_to = now
        label = "месяц"

    await callback.message.edit_text(f"⏳ Генерирую отчёт за {label}...", reply_markup=None)

    try:
        from services.report_service import generate_expense_report
        buf = await generate_expense_report(user_id, date_from, date_to)
        filename = f"report_{label}_{now.strftime('%Y%m%d')}.xlsx"
        await callback.message.answer_document(
            BufferedInputFile(buf.getvalue(), filename=filename),
            caption=f"📊 Отчёт по расходам за {label}",
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка генерации отчёта: {e}")

    await callback.answer()
