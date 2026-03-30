"""APScheduler: напоминания + утренний бриф."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from config import TIMEZONE, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=TIMEZONE)


# ─── Запуск планировщика ──────────────────────────────────────────────────────

async def load_and_schedule_all(bot) -> None:
    """Загрузить все pending напоминания из БД и запланировать."""
    from services import db_service

    if not scheduler.running:
        scheduler.start()

    reminders = await db_service.get_pending_reminders()
    now = datetime.now()
    for reminder in reminders:
        if reminder.trigger_at > now:
            schedule_reminder(reminder, bot)
        else:
            # Просроченные — отправляем сразу
            scheduler.add_job(
                fire_reminder,
                trigger=DateTrigger(run_date=datetime.now()),
                args=[reminder.id, bot],
                id=f"reminder_{reminder.id}",
                replace_existing=True,
            )

    # Утренний бриф в 08:00 каждый день
    scheduler.add_job(
        send_morning_brief,
        trigger=CronTrigger(hour=8, minute=0, timezone=TIMEZONE),
        args=[bot],
        id="morning_brief",
        replace_existing=True,
    )
    logger.info("Scheduled %d reminders + morning brief", len(reminders))


def schedule_reminder(reminder, bot) -> None:
    """Добавить одно напоминание в scheduler."""
    if not scheduler.running:
        scheduler.start()

    job_id = f"reminder_{reminder.id}"
    scheduler.add_job(
        fire_reminder,
        trigger=DateTrigger(run_date=reminder.trigger_at),
        args=[reminder.id, bot],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.debug("Scheduled reminder %s at %s", reminder.id, reminder.trigger_at)


# ─── Срабатывание напоминания ─────────────────────────────────────────────────

async def fire_reminder(reminder_id: int, bot) -> None:
    """Отправить напоминание пользователю."""
    from services import db_service

    try:
        # Получаем напоминание из БД
        reminders = await db_service.get_pending_reminders()
        reminder = next((r for r in reminders if r.id == reminder_id), None)
        if not reminder:
            return  # уже отправлено или удалено

        from utils.keyboards import reminder_snooze_keyboard
        await bot.send_message(
            reminder.user_id,
            f"⏰ <b>Напоминание!</b>\n\n{reminder.text}",
            parse_mode="HTML",
            reply_markup=reminder_snooze_keyboard(reminder.id),
        )

        await db_service.mark_reminder_sent(reminder.id)

        # Если повторяющееся — создать следующее
        if reminder.recurrence:
            await _schedule_next_recurrence(reminder, bot)

    except Exception as e:
        logger.error("fire_reminder(%s) error: %s", reminder_id, e)


async def _schedule_next_recurrence(reminder, bot) -> None:
    """Создать следующее повторение напоминания."""
    from services import db_service

    trigger_at = reminder.trigger_at
    recurrence = reminder.recurrence

    if recurrence == "daily":
        next_dt = trigger_at + timedelta(days=1)
    elif recurrence == "weekly":
        next_dt = trigger_at + timedelta(weeks=1)
    elif recurrence == "monthly":
        month = trigger_at.month + 1
        year = trigger_at.year
        if month > 12:
            month = 1
            year += 1
        try:
            next_dt = trigger_at.replace(year=year, month=month)
        except ValueError:
            next_dt = trigger_at + timedelta(days=30)
    else:
        return

    new_reminder = await db_service.add_reminder(
        user_id=reminder.user_id,
        text=reminder.text,
        trigger_at=next_dt,
        recurrence=recurrence,
    )
    schedule_reminder(new_reminder, bot)
    logger.info("Scheduled next recurrence reminder %s at %s", new_reminder.id, next_dt)


# ─── Утренний бриф ────────────────────────────────────────────────────────────

async def send_morning_brief(bot) -> None:
    """Отправить утренний бриф всем пользователям с активными данными."""
    from services import db_service
    from services.ai_service import generate_morning_motivation

    # Получаем всех пользователей с задачами (через ai_context)
    try:
        from models.base import AsyncSessionLocal
        from models.ai_context import AIContext
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AIContext.user_id))
            user_ids = [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error("send_morning_brief: get users error: %s", e)
        return

    for user_id in user_ids:
        try:
            await _send_brief_to_user(bot, user_id)
        except Exception as e:
            logger.error("morning brief for user %s: %s", user_id, e)


async def _send_brief_to_user(bot, user_id: int) -> None:
    from datetime import timedelta
    from services import db_service
    from services.ai_service import generate_morning_motivation

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59)
    yesterday_start = today_start - timedelta(days=1)

    # Встречи сегодня
    meetings = await db_service.get_today_meetings(user_id, today_start, today_end)

    # Топ задачи (pending, high+medium priority)
    tasks = await db_service.get_tasks(user_id, status="pending")
    top_tasks = sorted(tasks, key=lambda t: t.priority)[:5]

    # Вчерашние расходы
    yesterday_expenses = await db_service.get_expenses(user_id, since=yesterday_start, until=today_start)
    yesterday_total = sum(float(e.amount) for e in yesterday_expenses)

    # Среднее в день за месяц
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    month_expenses = await db_service.get_expenses(user_id, since=month_start)
    month_total = sum(float(e.amount) for e in month_expenses)
    days_passed = max((now - month_start).days, 1)
    daily_avg = month_total / days_passed

    # Мотивация от Claude
    motivation = await generate_morning_motivation(user_id)

    # Формируем сообщение
    lines = [f"🌅 <b>Доброе утро!</b> Вот твой день ({now.strftime('%d.%m.%Y')}):\n"]

    if meetings:
        lines.append("📅 <b>Встречи сегодня:</b>")
        for m in meetings:
            loc = f" ({m.location})" if m.location else ""
            lines.append(f"• {m.start_dt.strftime('%H:%M')} — {m.title}{loc}")
    else:
        lines.append("📅 Встреч сегодня нет.")

    lines.append("")

    if top_tasks:
        lines.append("✅ <b>Топ задачи:</b>")
        prio_emoji = {1: "🔴", 2: "🟡", 3: "⚪"}
        for t in top_tasks:
            emoji = prio_emoji.get(t.priority, "🟡")
            deadline = ""
            if t.deadline:
                if t.deadline.date() == now.date():
                    deadline = " (дедлайн сегодня!)"
                elif t.deadline < now:
                    deadline = " ⚠️ просрочено"
            lines.append(f"{emoji} {t.title}{deadline}")
    else:
        lines.append("✅ Нет активных задач. Отличный день!")

    lines.append("")

    if yesterday_total > 0:
        lines.append(
            f"💸 Вчера потрачено: <b>{yesterday_total:.2f} EUR</b> "
            f"(среднее/день: {daily_avg:.2f} EUR)"
        )
    else:
        lines.append("💸 Вчера расходов не было.")

    lines.append("")
    lines.append(f"💬 {motivation}")

    text = "\n".join(lines)
    await bot.send_message(user_id, text, parse_mode="HTML")
    logger.info("Morning brief sent to user %s", user_id)


# ─── /morning команда ─────────────────────────────────────────────────────────

async def send_morning_brief_to_user(bot, user_id: int) -> None:
    """Вызов брифа вручную для конкретного пользователя."""
    await _send_brief_to_user(bot, user_id)
