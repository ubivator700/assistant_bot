"""/goals — цели с прогрессбарами."""
from __future__ import annotations

import logging
from datetime import date

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from services import db_service
from utils.keyboards import goals_keyboard
from utils.formatters import fmt_goal

logger = logging.getLogger(__name__)
router = Router()


class AddGoalFSM(StatesGroup):
    name = State()
    target = State()
    deadline = State()


@router.message(Command("goals"))
async def cmd_goals(message: Message) -> None:
    goals = await db_service.get_goals(message.from_user.id)
    if not goals:
        await message.answer(
            "🎯 Целей пока нет.\n\nНажми кнопку ниже или напиши: <i>«добавь цель — отпуск 1000 евро»</i>",
            reply_markup=goals_keyboard(),
            parse_mode="HTML",
        )
        return
    lines = ["🎯 <b>Твои цели:</b>\n"]
    lines.extend(fmt_goal(g) for g in goals)
    await message.answer("\n\n".join(lines), reply_markup=goals_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "goal_add")
async def cb_goal_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddGoalFSM.name)
    await callback.message.answer("🎯 Введи название цели:")
    await callback.answer()


@router.message(AddGoalFSM.name)
async def fsm_goal_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AddGoalFSM.target)
    await message.answer("💰 Сколько нужно накопить? (введи сумму в EUR):")


@router.message(AddGoalFSM.target)
async def fsm_goal_target(message: Message, state: FSMContext) -> None:
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число, например: 1500")
        return
    await state.update_data(target=amount)
    await state.set_state(AddGoalFSM.deadline)
    await message.answer("📅 Дедлайн? (например: <i>31.12.2025</i> или <code>-</code> если нет)", parse_mode="HTML")


@router.message(AddGoalFSM.deadline)
async def fsm_goal_deadline(message: Message, state: FSMContext) -> None:
    from services.nlp_parser import parse_datetime
    text = message.text.strip()
    deadline = None
    if text not in ("-", "нет", "no", "—"):
        dt = parse_datetime(text)
        if dt:
            deadline = dt.date()
        else:
            await message.answer("❌ Не понял дату. Попробуй ещё раз или введи <code>-</code>", parse_mode="HTML")
            return

    data = await state.get_data()
    await state.clear()

    goal = await db_service.add_goal(
        user_id=message.from_user.id,
        name=data["name"],
        target_amount=data["target"],
        deadline=deadline,
    )
    await message.answer(
        f"🎯 Цель создана!\n\n{fmt_goal(goal)}",
        parse_mode="HTML",
    )
