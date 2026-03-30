"""Все InlineKeyboardMarkup фабрики."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def confirm_keyboard(entity_type: str, entity_id: int) -> InlineKeyboardMarkup:
    """✓ Сохранить / ✗ Отмена"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✓ Сохранить", callback_data=f"confirm:{entity_type}:{entity_id}")
    builder.button(text="✗ Отмена", callback_data=f"cancel:{entity_type}:{entity_id}")
    builder.adjust(2)
    return builder.as_markup()


def task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """✓ Выполнено | ✏️ Изменить | 🗑 Удалить"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✓ Выполнено", callback_data=f"task_done:{task_id}")
    builder.button(text="🗑 Удалить", callback_data=f"task_delete:{task_id}")
    builder.adjust(2)
    return builder.as_markup()


def expense_keyboard(expense_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить", callback_data=f"expense_delete:{expense_id}")
    builder.adjust(1)
    return builder.as_markup()


def period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Эта неделя", callback_data="period:week")
    builder.button(text="Этот месяц", callback_data="period:month")
    builder.button(text="Прошлый месяц", callback_data="period:last_month")
    builder.adjust(2, 1)
    return builder.as_markup()


def expense_period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Неделя", callback_data="exp_period:week")
    builder.button(text="Месяц", callback_data="exp_period:month")
    builder.button(text="Год", callback_data="exp_period:year")
    builder.adjust(3)
    return builder.as_markup()


def reminder_snooze_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """⏰ +1ч / +1д / 🔕 Удалить"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏰ +1 час", callback_data=f"snooze:1h:{reminder_id}")
    builder.button(text="⏰ +1 день", callback_data=f"snooze:1d:{reminder_id}")
    builder.button(text="🔕 Удалить", callback_data=f"reminder_delete:{reminder_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


def goals_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Новая цель", callback_data="goal_add")
    builder.adjust(1)
    return builder.as_markup()
