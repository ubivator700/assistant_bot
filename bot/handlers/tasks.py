"""/tasks — список и управление задачами + FSM добавления."""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from services import db_service
from services.nlp_parser import parse_datetime, parse_priority
from utils.keyboards import task_keyboard
from utils.formatters import fmt_tasks_list, fmt_task_detail

logger = logging.getLogger(__name__)
router = Router()


class AddTaskFSM(StatesGroup):
    title = State()
    deadline = State()
    priority = State()


# ─── /tasks ───────────────────────────────────────────────────────────────────

@router.message(Command("tasks"))
async def cmd_tasks(message: Message) -> None:
    tasks = await db_service.get_tasks(message.from_user.id, status="pending")
    text = fmt_tasks_list(tasks)
    await message.answer(text, parse_mode="HTML")

    # Показываем кнопки для каждой задачи (последние 5)
    for task in tasks[:5]:
        await message.answer(
            fmt_task_detail(task),
            reply_markup=task_keyboard(task.id),
            parse_mode="HTML",
        )


# ─── /add_task FSM ────────────────────────────────────────────────────────────

@router.message(Command("add_task"))
async def cmd_add_task(message: Message, state: FSMContext) -> None:
    await state.set_state(AddTaskFSM.title)
    await message.answer("📝 <b>Новая задача</b>\n\nШаг 1/3: Введи название задачи:", parse_mode="HTML")


@router.message(AddTaskFSM.title)
async def fsm_task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddTaskFSM.deadline)
    await message.answer(
        "⏰ Шаг 2/3: Укажи дедлайн (например: <i>завтра в 15:00</i>, <i>25 мая</i>, <i>-</i> если нет):",
        parse_mode="HTML",
    )


@router.message(AddTaskFSM.deadline)
async def fsm_task_deadline(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    deadline = None
    if text not in ("-", "нет", "no", "—"):
        deadline = parse_datetime(text)
        if not deadline:
            await message.answer("❌ Не понял дату. Попробуй ещё раз или введи <code>-</code>", parse_mode="HTML")
            return
    await state.update_data(deadline=deadline)
    await state.set_state(AddTaskFSM.priority)
    await message.answer(
        "🔴 Шаг 3/3: Приоритет?\n<code>1</code> — высокий 🔴\n<code>2</code> — средний 🟡\n<code>3</code> — низкий ⚪",
        parse_mode="HTML",
    )


@router.message(AddTaskFSM.priority)
async def fsm_task_priority(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    try:
        priority = int(text)
        if priority not in (1, 2, 3):
            raise ValueError
    except ValueError:
        priority = parse_priority(text)

    data = await state.get_data()
    await state.clear()

    task = await db_service.add_task(
        user_id=message.from_user.id,
        title=data["title"],
        priority=priority,
        deadline=data.get("deadline"),
    )
    prio_emoji = {1: "🔴", 2: "🟡", 3: "⚪"}.get(priority, "🟡")
    dl_str = f"\n⏰ {task.deadline.strftime('%d.%m.%Y %H:%M')}" if task.deadline else ""
    await message.answer(
        f"✅ Задача создана!\n\n{prio_emoji} <b>{task.title}</b>{dl_str}",
        parse_mode="HTML",
    )


# ─── Callbacks ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(callback: CallbackQuery) -> None:
    task_id = int(callback.data.split(":")[1])
    task = await db_service.update_task_status(task_id, "done")
    if task:
        await callback.message.edit_text(f"✅ Выполнено: <b>{task.title}</b>", reply_markup=None, parse_mode="HTML")
    await callback.answer("Отмечено как выполненное!")


@router.callback_query(F.data.startswith("task_delete:"))
async def cb_task_delete(callback: CallbackQuery) -> None:
    task_id = int(callback.data.split(":")[1])
    await db_service.delete_task(task_id)
    await callback.message.edit_text("🗑 Задача удалена.", reply_markup=None)
    await callback.answer("Удалено")
