"""Главный маршрутизатор всех сообщений через AI."""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, PhotoSize

from services import ai_service, db_service
from services.nlp_parser import parse_amount, parse_datetime, parse_priority
from utils.keyboards import confirm_keyboard
from utils.formatters import fmt_expense_confirm

logger = logging.getLogger(__name__)
router = Router()


# ─── FSM States ───────────────────────────────────────────────────────────────

class WaitingExpense(StatesGroup):
    waiting_amount = State()


class WaitingTask(StatesGroup):
    waiting_date = State()


class WaitingConfirmation(StatesGroup):
    confirming = State()


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        "Я твой персональный ассистент. Могу помочь:\n"
        "💶 Вести расходы — <i>«потратил 85 евро на продукты»</i>\n"
        "✅ Задачи — <i>«нужно позвонить клиенту»</i>\n"
        "📅 Встречи — <i>«созвон с командой в пятницу в 10»</i>\n"
        "📌 Заметки — <i>«запиши идею про...»</i>\n"
        "⏰ Напоминания — <i>«напомни завтра в 9 о встрече»</i>\n"
        "🎯 Цели — <i>«добавь 50 евро к накоплениям на отпуск»</i>\n\n"
        "Команды: /expenses /tasks /meetings /notes /goals /reminders /report /today /morning",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await cmd_start(message)


# ─── Обработка фото (OCR чека) ────────────────────────────────────────────────

@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    await message.answer("🔍 Распознаю чек...")
    photo: PhotoSize = message.photo[-1]  # берём максимальное качество
    file = await message.bot.get_file(photo.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    image_data = file_bytes.read()

    result = await ai_service.parse_receipt_photo(image_data)
    if not result or not result.get("amount"):
        await message.answer("❌ Не удалось распознать чек. Введи сумму вручную.")
        return

    amount = result.get("amount", 0)
    currency = result.get("currency", "EUR")
    merchant = result.get("merchant", "")
    items = result.get("items", [])
    description = merchant or (", ".join(items[:3]) if items else "")
    date_str = result.get("date", datetime.now().strftime("%Y-%m-%d"))

    # Сохраняем данные в state для подтверждения
    await state.update_data(
        pending_expense={
            "amount": amount,
            "currency": currency,
            "category": "еда",
            "description": description,
        }
    )

    text = fmt_expense_confirm(amount, currency, "еда", description, date_str)
    await message.answer(text, reply_markup=confirm_keyboard("expense_pending", 0), parse_mode="HTML")


# ─── Главный обработчик текстовых сообщений ──────────────────────────────────

@router.message(F.text)
async def handle_text(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    text = message.text.strip()

    # Пропускаем команды
    if text.startswith("/"):
        return

    # Проверяем текущий FSM state
    current_state = await state.get_state()
    if current_state:
        return  # FSM обрабатывается отдельными хендлерами

    await message.bot.send_chat_action(message.chat.id, "typing")

    intent = await ai_service.detect_intent(text)
    logger.info("user=%d intent=%s text=%r", user_id, intent, text[:50])

    if intent == "ADD_EXPENSE":
        await _handle_add_expense(message, state, text, user_id)
    elif intent == "ADD_TASK":
        await _handle_add_task(message, state, text, user_id)
    elif intent == "ADD_MEETING":
        await _handle_add_meeting(message, state, text, user_id)
    elif intent == "ADD_NOTE":
        await _handle_add_note(message, text, user_id)
    elif intent == "SET_REMINDER":
        await _handle_set_reminder(message, state, text, user_id)
    elif intent == "ADD_TO_GOAL":
        await _handle_add_to_goal(message, text, user_id)
    elif intent == "QUERY_DATA":
        await _handle_query(message, text, user_id)
    elif intent == "GENERATE_REPORT":
        await message.answer("📊 Генерирую отчёт... Используй /report для выбора периода.")
    else:
        reply = await ai_service.chat(user_id, text)
        await message.answer(reply, parse_mode="HTML")


# ─── ADD_EXPENSE ──────────────────────────────────────────────────────────────

async def _handle_add_expense(message: Message, state: FSMContext, text: str, user_id: int) -> None:
    entity = await ai_service.parse_entity(text, "ADD_EXPENSE")
    amount = entity.get("amount")
    currency = entity.get("currency", "EUR")
    category = entity.get("category", "другое")
    description = entity.get("description", "")
    date_str = datetime.now().strftime("%d.%m.%Y")

    if amount is None:
        await state.update_data(pending_intent="ADD_EXPENSE", pending_entity=entity)
        await state.set_state(WaitingExpense.waiting_amount)
        await message.answer("💶 Не удалось определить сумму. Введи сумму:")
        return

    # Сохраняем в state для подтверждения
    await state.update_data(
        pending_expense={
            "amount": float(amount),
            "currency": currency,
            "category": category,
            "description": description,
        }
    )
    confirm_text = fmt_expense_confirm(float(amount), currency, category, description, date_str)
    await message.answer(confirm_text, reply_markup=confirm_keyboard("expense_pending", 0), parse_mode="HTML")


@router.message(WaitingExpense.waiting_amount)
async def fsm_expense_amount(message: Message, state: FSMContext) -> None:
    amount, currency = parse_amount(message.text)
    if amount is None:
        try:
            amount = float(message.text.replace(",", "."))
        except ValueError:
            await message.answer("❌ Не понял сумму. Введи число, например: 85.50")
            return

    data = await state.get_data()
    entity = data.get("pending_entity", {})
    entity["amount"] = amount
    entity["currency"] = currency

    await state.update_data(pending_expense=entity)
    await state.clear()

    date_str = datetime.now().strftime("%d.%m.%Y")
    confirm_text = fmt_expense_confirm(
        float(amount), currency, entity.get("category", "другое"),
        entity.get("description", ""), date_str,
    )
    await message.answer(confirm_text, reply_markup=confirm_keyboard("expense_pending", 0), parse_mode="HTML")


# ─── ADD_TASK ─────────────────────────────────────────────────────────────────

async def _handle_add_task(message: Message, state: FSMContext, text: str, user_id: int) -> None:
    entity = await ai_service.parse_entity(text, "ADD_TASK")
    title = entity.get("title", text[:100])
    description = entity.get("description")
    priority = entity.get("priority", parse_priority(text))
    deadline_str = entity.get("deadline")
    deadline = None
    if deadline_str:
        try:
            deadline = datetime.fromisoformat(deadline_str)
        except Exception:
            deadline = parse_datetime(deadline_str)

    task = await db_service.add_task(user_id, title, description, priority, deadline)
    prio_emoji = {1: "🔴", 2: "🟡", 3: "⚪"}.get(priority, "🟡")
    dl_str = f"\n⏰ Дедлайн: {deadline.strftime('%d.%m.%Y %H:%M')}" if deadline else ""
    await message.answer(
        f"✅ Задача добавлена!\n\n{prio_emoji} <b>{title}</b>{dl_str}",
        parse_mode="HTML",
    )


# ─── ADD_MEETING ──────────────────────────────────────────────────────────────

async def _handle_add_meeting(message: Message, state: FSMContext, text: str, user_id: int) -> None:
    entity = await ai_service.parse_entity(text, "ADD_MEETING")
    title = entity.get("title", text[:100])
    participants = entity.get("participants", [])
    location = entity.get("location")
    notes = entity.get("notes")
    start_str = entity.get("start_dt")
    end_str = entity.get("end_dt")

    start_dt = None
    if start_str:
        try:
            start_dt = datetime.fromisoformat(start_str)
        except Exception:
            start_dt = parse_datetime(start_str)

    if not start_dt:
        await message.answer("📅 Не удалось определить время встречи. Укажи дату и время.")
        return

    end_dt = None
    if end_str:
        try:
            end_dt = datetime.fromisoformat(end_str)
        except Exception:
            pass

    meeting = await db_service.add_meeting(
        user_id, title, participants, location, start_dt, end_dt, notes
    )
    parts_str = f"\n👥 {', '.join(participants)}" if participants else ""
    loc_str = f"\n📍 {location}" if location else ""
    await message.answer(
        f"✅ Встреча добавлена!\n\n📅 <b>{title}</b>\n"
        f"🕐 {start_dt.strftime('%d.%m.%Y %H:%M')}{parts_str}{loc_str}",
        parse_mode="HTML",
    )


# ─── ADD_NOTE ─────────────────────────────────────────────────────────────────

async def _handle_add_note(message: Message, text: str, user_id: int) -> None:
    entity = await ai_service.parse_entity(text, "ADD_NOTE")
    content = entity.get("content", text)
    tags = entity.get("tags", [])
    category = entity.get("category")
    await db_service.add_note(user_id, content, tags, category)
    tags_str = " " + " ".join(f"#{t}" for t in tags) if tags else ""
    await message.answer(f"📌 Заметка сохранена!{tags_str}")


# ─── SET_REMINDER ─────────────────────────────────────────────────────────────

async def _handle_set_reminder(message: Message, state: FSMContext, text: str, user_id: int) -> None:
    entity = await ai_service.parse_entity(text, "SET_REMINDER")
    reminder_text = entity.get("text", text)
    trigger_str = entity.get("trigger_at")
    recurrence = entity.get("recurrence")

    trigger_at = None
    if trigger_str:
        try:
            trigger_at = datetime.fromisoformat(trigger_str)
        except Exception:
            trigger_at = parse_datetime(trigger_str)

    if not trigger_at:
        await message.answer("⏰ Не удалось определить время напоминания. Укажи точное время.")
        return

    reminder = await db_service.add_reminder(user_id, reminder_text, trigger_at, recurrence)

    # Планируем напоминание
    try:
        from services.reminder_service import schedule_reminder
        schedule_reminder(reminder, message.bot)
    except Exception as e:
        logger.warning("schedule_reminder error: %s", e)

    rec_str = f" 🔄 {recurrence}" if recurrence else ""
    await message.answer(
        f"⏰ Напоминание установлено!\n\n"
        f"📝 {reminder_text}\n"
        f"🕐 {trigger_at.strftime('%d.%m.%Y %H:%M')}{rec_str}",
        parse_mode="HTML",
    )


# ─── ADD_TO_GOAL ──────────────────────────────────────────────────────────────

async def _handle_add_to_goal(message: Message, text: str, user_id: int) -> None:
    entity = await ai_service.parse_entity(text, "ADD_TO_GOAL")
    goal_name = entity.get("goal_name", "")
    amount = entity.get("amount", 0)

    goals = await db_service.get_goals(user_id)
    if not goals:
        await message.answer("🎯 Нет активных целей. Создай цель через /goals")
        return

    # Ищем цель по имени (нечёткий поиск)
    goal = None
    if goal_name:
        goal_name_lower = goal_name.lower()
        for g in goals:
            if goal_name_lower in g.name.lower() or g.name.lower() in goal_name_lower:
                goal = g
                break
    if not goal:
        goal = goals[0]  # берём первую

    updated = await db_service.update_goal_amount(goal.id, float(amount))
    if updated:
        current = float(updated.current_amount)
        target = float(updated.target_amount)
        pct = int(current / target * 100) if target > 0 else 0
        await message.answer(
            f"🎯 Пополнено!\n\n<b>{updated.name}</b>\n"
            f"+{amount:.2f} EUR · Всего: {current:.2f}/{target:.2f} EUR ({pct}%)",
            parse_mode="HTML",
        )


# ─── QUERY_DATA ───────────────────────────────────────────────────────────────

async def _handle_query(message: Message, text: str, user_id: int) -> None:
    from datetime import timedelta
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    expenses = await db_service.get_expenses(user_id, since=month_start)
    tasks = await db_service.get_tasks(user_id, status="pending")
    meetings = await db_service.get_meetings(user_id, since=now)

    prio_label = {1: "высокий", 2: "средний", 3: "низкий"}
    data_context = (
        f"Расходы за месяц ({len(expenses)} шт., итого {sum(float(e.amount) for e in expenses):.2f} EUR):\n"
        + "\n".join(f"  {float(e.amount):.2f} {e.currency} — {e.category} — {e.description}" for e in expenses[:10])
        + f"\n\nЗадачи в работе ({len(tasks)} шт.):\n"
        + "\n".join(f"  [{prio_label.get(t.priority, '?')}] {t.title}" for t in tasks[:10])
        + f"\n\nБудущие встречи ({len(meetings)} шт.):\n"
        + "\n".join(f"  {m.start_dt.strftime('%d.%m.%Y %H:%M')} — {m.title}" for m in meetings[:10])
    )

    reply = await ai_service.answer_data_query(user_id, text, data_context)
    await message.answer(reply, parse_mode="HTML")


# ─── Callback: подтверждение расхода ─────────────────────────────────────────

@router.callback_query(F.data.startswith("confirm:expense_pending"))
async def cb_confirm_expense(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    expense_data = data.get("pending_expense", {})
    user_id = callback.from_user.id

    if expense_data:
        await db_service.add_expense(
            user_id=user_id,
            amount=expense_data.get("amount", 0),
            currency=expense_data.get("currency", "EUR"),
            category=expense_data.get("category"),
            description=expense_data.get("description"),
        )
        await state.clear()
        await callback.message.edit_text("✅ Расход сохранён!", reply_markup=None)
    else:
        await callback.message.edit_text("❌ Данные не найдены.", reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Отменено.", reply_markup=None)
    await callback.answer()
