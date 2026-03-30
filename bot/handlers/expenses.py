"""/expenses — просмотр и управление расходами."""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from services import db_service
from utils.keyboards import expense_period_keyboard, expense_keyboard
from utils.formatters import fmt_expense_summary, fmt_expense

router = Router()


@router.message(Command("expenses"))
async def cmd_expenses(message: Message) -> None:
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    expenses = await db_service.get_expenses(message.from_user.id, since=month_start)
    text = fmt_expense_summary(expenses)
    await message.answer(
        text + "\n\n📆 Выбери период:",
        reply_markup=expense_period_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("exp_period:"))
async def cb_expense_period(callback: CallbackQuery) -> None:
    period = callback.data.split(":")[1]
    now = datetime.now()
    user_id = callback.from_user.id

    if period == "week":
        since = now - timedelta(days=7)
        label = "неделю"
    elif period == "month":
        since = now.replace(day=1, hour=0, minute=0, second=0)
        label = "месяц"
    elif period == "year":
        since = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        label = "год"
    else:
        since = now.replace(day=1)
        label = "месяц"

    expenses = await db_service.get_expenses(user_id, since=since)
    text = f"<b>Расходы за {label}:</b>\n\n" + fmt_expense_summary(expenses)
    await callback.message.edit_text(text, reply_markup=expense_period_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("expense_delete:"))
async def cb_expense_delete(callback: CallbackQuery) -> None:
    expense_id = int(callback.data.split(":")[1])
    await db_service.delete_expense(expense_id)
    await callback.message.edit_text("🗑 Расход удалён.", reply_markup=None)
    await callback.answer("Удалено")
