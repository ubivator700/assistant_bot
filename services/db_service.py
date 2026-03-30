"""Async CRUD operations for all models."""
from __future__ import annotations

import json
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import AsyncSessionLocal
from models.expense import Expense
from models.task import Task
from models.meeting import Meeting
from models.note import Note
from models.reminder import Reminder
from models.goal import Goal
from models.ai_context import AIContext


# ─── Expenses ────────────────────────────────────────────────────────────────

async def add_expense(
    user_id: int,
    amount: float,
    currency: str = "EUR",
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> Expense:
    async with AsyncSessionLocal() as session:
        expense = Expense(
            user_id=user_id,
            amount=Decimal(str(amount)),
            currency=currency,
            category=category,
            description=description,
        )
        session.add(expense)
        await session.commit()
        await session.refresh(expense)
        return expense


async def get_expenses(
    user_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> List[Expense]:
    async with AsyncSessionLocal() as session:
        q = select(Expense).where(Expense.user_id == user_id)
        if since:
            q = q.where(Expense.created_at >= since)
        if until:
            q = q.where(Expense.created_at <= until)
        q = q.order_by(Expense.created_at.desc())
        result = await session.execute(q)
        return list(result.scalars().all())


async def delete_expense(expense_id: int) -> None:
    async with AsyncSessionLocal() as session:
        expense = await session.get(Expense, expense_id)
        if expense:
            await session.delete(expense)
            await session.commit()


# ─── Tasks ────────────────────────────────────────────────────────────────────

async def add_task(
    user_id: int,
    title: str,
    description: Optional[str] = None,
    priority: int = 2,
    deadline: Optional[datetime] = None,
) -> Task:
    async with AsyncSessionLocal() as session:
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            deadline=deadline,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def get_tasks(
    user_id: int,
    status: Optional[str] = "pending",
) -> List[Task]:
    async with AsyncSessionLocal() as session:
        q = select(Task).where(Task.user_id == user_id)
        if status:
            q = q.where(Task.status == status)
        q = q.order_by(Task.priority.asc(), Task.created_at.desc())
        result = await session.execute(q)
        return list(result.scalars().all())


async def get_task(task_id: int) -> Optional[Task]:
    async with AsyncSessionLocal() as session:
        return await session.get(Task, task_id)


async def update_task_status(task_id: int, status: str) -> Optional[Task]:
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        if task:
            task.status = status
            await session.commit()
            await session.refresh(task)
        return task


async def delete_task(task_id: int) -> None:
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        if task:
            await session.delete(task)
            await session.commit()


# ─── Meetings ─────────────────────────────────────────────────────────────────

async def add_meeting(
    user_id: int,
    title: str,
    participants: Optional[list] = None,
    location: Optional[str] = None,
    start_dt: datetime = None,
    end_dt: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Meeting:
    async with AsyncSessionLocal() as session:
        meeting = Meeting(
            user_id=user_id,
            title=title,
            participants=json.dumps(participants, ensure_ascii=False) if participants else None,
            location=location,
            start_dt=start_dt,
            end_dt=end_dt,
            notes=notes,
        )
        session.add(meeting)
        await session.commit()
        await session.refresh(meeting)
        return meeting


async def get_meetings(
    user_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> List[Meeting]:
    async with AsyncSessionLocal() as session:
        q = select(Meeting).where(Meeting.user_id == user_id)
        if since:
            q = q.where(Meeting.start_dt >= since)
        if until:
            q = q.where(Meeting.start_dt <= until)
        q = q.order_by(Meeting.start_dt.asc())
        result = await session.execute(q)
        return list(result.scalars().all())


async def delete_meeting(meeting_id: int) -> None:
    async with AsyncSessionLocal() as session:
        meeting = await session.get(Meeting, meeting_id)
        if meeting:
            await session.delete(meeting)
            await session.commit()


# ─── Notes ────────────────────────────────────────────────────────────────────

async def add_note(
    user_id: int,
    content: str,
    tags: Optional[list] = None,
    category: Optional[str] = None,
) -> Note:
    async with AsyncSessionLocal() as session:
        note = Note(
            user_id=user_id,
            content=content,
            tags=tags,
            category=category,
        )
        session.add(note)
        await session.commit()
        await session.refresh(note)
        return note


async def get_notes(user_id: int, limit: int = 10) -> List[Note]:
    async with AsyncSessionLocal() as session:
        q = (
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return list(result.scalars().all())


async def search_notes(user_id: int, query: str) -> List[Note]:
    async with AsyncSessionLocal() as session:
        q = (
            select(Note)
            .where(
                and_(
                    Note.user_id == user_id,
                    or_(
                        Note.content.ilike(f"%{query}%"),
                        Note.category.ilike(f"%{query}%"),
                    ),
                )
            )
            .order_by(Note.created_at.desc())
            .limit(20)
        )
        result = await session.execute(q)
        return list(result.scalars().all())


async def delete_note(note_id: int) -> None:
    async with AsyncSessionLocal() as session:
        note = await session.get(Note, note_id)
        if note:
            await session.delete(note)
            await session.commit()


# ─── Reminders ────────────────────────────────────────────────────────────────

async def add_reminder(
    user_id: int,
    text: str,
    trigger_at: datetime,
    recurrence: Optional[str] = None,
) -> Reminder:
    async with AsyncSessionLocal() as session:
        reminder = Reminder(
            user_id=user_id,
            text=text,
            trigger_at=trigger_at,
            recurrence=recurrence,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder


async def get_pending_reminders() -> List[Reminder]:
    async with AsyncSessionLocal() as session:
        q = select(Reminder).where(Reminder.is_sent == False).order_by(Reminder.trigger_at.asc())
        result = await session.execute(q)
        return list(result.scalars().all())


async def get_user_reminders(user_id: int) -> List[Reminder]:
    async with AsyncSessionLocal() as session:
        q = (
            select(Reminder)
            .where(and_(Reminder.user_id == user_id, Reminder.is_sent == False))
            .order_by(Reminder.trigger_at.asc())
        )
        result = await session.execute(q)
        return list(result.scalars().all())


async def mark_reminder_sent(reminder_id: int) -> None:
    async with AsyncSessionLocal() as session:
        reminder = await session.get(Reminder, reminder_id)
        if reminder:
            reminder.is_sent = True
            await session.commit()


async def delete_reminder(reminder_id: int) -> None:
    async with AsyncSessionLocal() as session:
        reminder = await session.get(Reminder, reminder_id)
        if reminder:
            await session.delete(reminder)
            await session.commit()


async def snooze_reminder(reminder_id: int, new_trigger: datetime) -> Optional[Reminder]:
    async with AsyncSessionLocal() as session:
        reminder = await session.get(Reminder, reminder_id)
        if reminder:
            reminder.trigger_at = new_trigger
            reminder.is_sent = False
            await session.commit()
            await session.refresh(reminder)
        return reminder


# ─── Goals ────────────────────────────────────────────────────────────────────

async def add_goal(
    user_id: int,
    name: str,
    target_amount: float,
    deadline: Optional[date] = None,
) -> Goal:
    async with AsyncSessionLocal() as session:
        goal = Goal(
            user_id=user_id,
            name=name,
            target_amount=Decimal(str(target_amount)),
            deadline=deadline,
        )
        session.add(goal)
        await session.commit()
        await session.refresh(goal)
        return goal


async def get_goals(user_id: int) -> List[Goal]:
    async with AsyncSessionLocal() as session:
        q = select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at.asc())
        result = await session.execute(q)
        return list(result.scalars().all())


async def update_goal_amount(goal_id: int, amount: float) -> Optional[Goal]:
    async with AsyncSessionLocal() as session:
        goal = await session.get(Goal, goal_id)
        if goal:
            goal.current_amount = Decimal(str(float(goal.current_amount) + amount))
            await session.commit()
            await session.refresh(goal)
        return goal


async def delete_goal(goal_id: int) -> None:
    async with AsyncSessionLocal() as session:
        goal = await session.get(Goal, goal_id)
        if goal:
            await session.delete(goal)
            await session.commit()


# ─── AI Context ───────────────────────────────────────────────────────────────

async def get_ai_context(user_id: int) -> str:
    async with AsyncSessionLocal() as session:
        ctx = await session.get(AIContext, user_id)
        return ctx.context_json if ctx and ctx.context_json else "[]"


async def save_ai_context(user_id: int, context_json: str) -> None:
    async with AsyncSessionLocal() as session:
        ctx = await session.get(AIContext, user_id)
        if ctx:
            ctx.context_json = context_json
        else:
            ctx = AIContext(user_id=user_id, context_json=context_json)
            session.add(ctx)
        await session.commit()


# ─── Dashboard stats ──────────────────────────────────────────────────────────

async def get_monthly_expense_total(user_id: int, year: int, month: int) -> float:
    async with AsyncSessionLocal() as session:
        q = select(func.sum(Expense.amount)).where(
            and_(
                Expense.user_id == user_id,
                func.year(Expense.created_at) == year,
                func.month(Expense.created_at) == month,
            )
        )
        result = await session.execute(q)
        total = result.scalar()
        return float(total) if total else 0.0


async def get_pending_task_count(user_id: int) -> int:
    async with AsyncSessionLocal() as session:
        q = select(func.count(Task.id)).where(
            and_(Task.user_id == user_id, Task.status == "pending")
        )
        result = await session.execute(q)
        return result.scalar() or 0


async def get_today_meetings(user_id: int, today_start: datetime, today_end: datetime) -> List[Meeting]:
    async with AsyncSessionLocal() as session:
        q = (
            select(Meeting)
            .where(
                and_(
                    Meeting.user_id == user_id,
                    Meeting.start_dt >= today_start,
                    Meeting.start_dt <= today_end,
                )
            )
            .order_by(Meeting.start_dt.asc())
        )
        result = await session.execute(q)
        return list(result.scalars().all())
