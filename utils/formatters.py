"""Форматирование сообщений для Telegram."""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import List

from models.expense import Expense
from models.task import Task
from models.meeting import Meeting
from models.note import Note
from models.reminder import Reminder
from models.goal import Goal

PRIORITY_EMOJI = {1: "🔴", 2: "🟡", 3: "⚪"}
PRIORITY_LABEL = {1: "Высокий", 2: "Средний", 3: "Низкий"}
STATUS_EMOJI = {"pending": "⏳", "done": "✅", "cancelled": "❌"}


def fmt_expense(e: Expense) -> str:
    cat = f" [{e.category}]" if e.category else ""
    desc = f"\n   📝 {e.description}" if e.description else ""
    return f"💶 {float(e.amount):.2f} {e.currency}{cat} — {e.created_at.strftime('%d.%m.%Y')}{desc}"


def fmt_expense_confirm(amount: float, currency: str, category: str, description: str, date: str) -> str:
    return (
        f"✅ Сохранить расход?\n\n"
        f"💶 {amount:.2f} {currency} — {category or 'другое'}\n"
        f"📝 {description or '—'}\n"
        f"📅 {date}"
    )


def fmt_task(t: Task) -> str:
    priority = PRIORITY_EMOJI.get(t.priority, "⚪")
    deadline = f" | ⏰ {t.deadline.strftime('%d.%m.%Y %H:%M')}" if t.deadline else ""
    return f"{priority} {t.title}{deadline}"


def fmt_task_detail(t: Task) -> str:
    priority = PRIORITY_EMOJI.get(t.priority, "⚪")
    deadline = f"\n⏰ Дедлайн: {t.deadline.strftime('%d.%m.%Y %H:%M')}" if t.deadline else ""
    desc = f"\n📝 {t.description}" if t.description else ""
    return f"{priority} <b>{t.title}</b>{deadline}{desc}\n🆔 #{t.id}"


def fmt_tasks_list(tasks: List[Task]) -> str:
    if not tasks:
        return "✅ Нет активных задач!"
    by_priority: dict = {1: [], 2: [], 3: []}
    for t in tasks:
        by_priority.setdefault(t.priority, []).append(t)
    lines = ["📋 <b>Твои задачи:</b>\n"]
    for p in [1, 2, 3]:
        group = by_priority.get(p, [])
        if group:
            lines.append(f"{PRIORITY_EMOJI[p]} <b>{PRIORITY_LABEL[p]}:</b>")
            for t in group:
                deadline = f" · ⏰ {t.deadline.strftime('%d.%m')}" if t.deadline else ""
                lines.append(f"  • {t.title}{deadline} [#{t.id}]")
            lines.append("")
    return "\n".join(lines)


def fmt_meeting(m: Meeting) -> str:
    time_str = m.start_dt.strftime("%d.%m %H:%M")
    end_str = f"–{m.end_dt.strftime('%H:%M')}" if m.end_dt else ""
    loc = f" 📍 {m.location}" if m.location else ""
    parts_raw = m.participants
    parts = ""
    if parts_raw:
        try:
            p_list = json.loads(parts_raw)
            parts = f"\n   👥 {', '.join(p_list)}" if p_list else ""
        except Exception:
            parts = f"\n   👥 {parts_raw}"
    return f"🗓 {time_str}{end_str} — <b>{m.title}</b>{loc}{parts}"


def fmt_meetings_list(meetings: List[Meeting]) -> str:
    if not meetings:
        return "📅 Встреч не найдено."
    lines = ["📅 <b>Встречи:</b>\n"]
    lines.extend(fmt_meeting(m) for m in meetings)
    return "\n".join(lines)


def fmt_note(n: Note) -> str:
    tags = ""
    if n.tags:
        try:
            t_list = n.tags if isinstance(n.tags, list) else json.loads(n.tags)
            tags = "  " + " ".join(f"#{t}" for t in t_list)
        except Exception:
            pass
    date_str = n.created_at.strftime("%d.%m.%Y")
    short = n.content[:100] + ("…" if len(n.content) > 100 else "")
    return f"📌 {short}{tags}\n   <i>{date_str}</i> [#{n.id}]"


def fmt_reminder(r: Reminder) -> str:
    rec = f" 🔄 {r.recurrence}" if r.recurrence else ""
    return f"⏰ {r.trigger_at.strftime('%d.%m.%Y %H:%M')} — {r.text}{rec}"


def fmt_goal(g: Goal) -> str:
    target = float(g.target_amount)
    current = float(g.current_amount)
    pct = int(current / target * 100) if target > 0 else 0
    filled = int(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    deadline = f" · до {g.deadline.strftime('%d.%m.%Y')}" if g.deadline else ""
    return (
        f"🎯 <b>{g.name}</b>{deadline}\n"
        f"   [{bar}] {pct}% ({current:.0f}/{target:.0f} EUR)\n"
        f"   🆔 #{g.id}"
    )


def fmt_expense_summary(expenses: List[Expense]) -> str:
    if not expenses:
        return "💸 Расходов нет."
    total = sum(float(e.amount) for e in expenses)
    by_cat: dict = {}
    for e in expenses:
        cat = e.category or "другое"
        by_cat[cat] = by_cat.get(cat, 0) + float(e.amount)

    lines = [f"💸 <b>Расходы: {total:.2f} EUR</b>\n", "<b>По категориям:</b>"]
    for cat, amount in sorted(by_cat.items(), key=lambda x: -x[1]):
        pct = int(amount / total * 100) if total > 0 else 0
        lines.append(f"  • {cat}: {amount:.2f} EUR ({pct}%)")

    top3 = sorted(expenses, key=lambda e: -float(e.amount))[:3]
    lines.append("\n<b>Топ-3 трат:</b>")
    for e in top3:
        desc = e.description or e.category or "—"
        lines.append(f"  • {float(e.amount):.2f} {e.currency} — {desc}")

    return "\n".join(lines)
