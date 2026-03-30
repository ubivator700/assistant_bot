"""/notes, /search — заметки."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services import db_service, ai_service
from utils.formatters import fmt_note

router = Router()


@router.message(Command("notes"))
async def cmd_notes(message: Message) -> None:
    notes = await db_service.get_notes(message.from_user.id, limit=10)
    if not notes:
        await message.answer("📌 Заметок пока нет.\n\nПросто напиши мне что-нибудь для сохранения!")
        return
    lines = ["📌 <b>Последние заметки:</b>\n"]
    lines.extend(fmt_note(n) for n in notes)
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    # Извлекаем запрос после команды
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("🔍 Использование: <code>/search запрос</code>", parse_mode="HTML")
        return

    query = parts[1].strip()
    user_id = message.from_user.id

    # Сначала ищем в БД
    notes = await db_service.search_notes(user_id, query)

    if notes:
        lines = [f"🔍 <b>Найдено по запросу «{query}»:</b>\n"]
        lines.extend(fmt_note(n) for n in notes)
        await message.answer("\n\n".join(lines), parse_mode="HTML")
    else:
        # Если ничего не найдено — спрашиваем Claude
        all_notes = await db_service.get_notes(user_id, limit=50)
        if all_notes:
            notes_text = "\n".join(f"#{n.id}: {n.content[:100]}" for n in all_notes)
            reply = await ai_service.answer_data_query(
                user_id,
                f"Найди в заметках: {query}",
                f"Заметки пользователя:\n{notes_text}",
            )
            await message.answer(reply, parse_mode="HTML")
        else:
            await message.answer(f"🔍 По запросу «{query}» ничего не найдено.")
