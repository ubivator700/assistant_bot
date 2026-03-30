"""Сервис работы с Claude API: роутинг намерений, парсинг сущностей, чат, OCR."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import anthropic

from config import ANTHROPIC_API_KEY, TIMEZONE
from services import db_service
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_TZ = ZoneInfo(TIMEZONE)

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-5"

INTENTS = [
    "ADD_EXPENSE",
    "ADD_TASK",
    "ADD_MEETING",
    "ADD_NOTE",
    "SET_REMINDER",
    "ADD_TO_GOAL",
    "QUERY_DATA",
    "GENERATE_REPORT",
    "FREE_CHAT",
]

EXPENSE_CATEGORIES = [
    "еда", "транспорт", "здоровье", "развлечения",
    "одежда", "дом", "работа", "путешествия", "другое",
]

# ─── Роутер намерений ─────────────────────────────────────────────────────────

_INTENT_SYSTEM = f"""Ты классификатор намерений для персонального ассистента.
Твоя задача — определить намерение пользователя из текста.

Возможные намерения (выбери ТОЛЬКО ОДНО):
- ADD_EXPENSE — пользователь тратил деньги, купил что-то, заплатил
- ADD_TASK — нужно что-то сделать, задача, напомни сделать (но не с конкретным временем)
- ADD_MEETING — встреча, созвон, событие в конкретное время и дату
- ADD_NOTE — заметка, идея, запись, информация на будущее
- SET_REMINDER — напоминание в конкретное время
- ADD_TO_GOAL — пополнить цель/накопление, добавить деньги к цели
- QUERY_DATA — вопрос о данных: сколько потратил, какие задачи, встречи
- GENERATE_REPORT — нужен отчёт, выгрузка, Excel
- FREE_CHAT — всё остальное: вопросы, разговор, советы

Ответь ТОЛЬКО JSON без markdown: {{"intent": "INTENT_NAME", "confidence": 0.95}}"""


async def detect_intent(text: str) -> str:
    """Определяет намерение пользователя. Возвращает строку из INTENTS."""
    try:
        resp = _client.messages.create(
            model=HAIKU,
            max_tokens=100,
            system=_INTENT_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        raw = resp.content[0].text.strip()
        # Убираем возможный markdown
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        data = json.loads(raw)
        intent = data.get("intent", "FREE_CHAT")
        if intent not in INTENTS:
            intent = "FREE_CHAT"
        return intent
    except Exception as e:
        logger.warning("detect_intent error: %s", e)
        return "FREE_CHAT"


# ─── Парсер сущностей ─────────────────────────────────────────────────────────

_now_str = lambda: datetime.now(_TZ).strftime("%Y-%m-%dT%H:%M:%S")

_PARSE_PROMPTS: Dict[str, str] = {
    "ADD_EXPENSE": f"""Извлеки данные о расходе из текста пользователя.
Сегодня: {{now}}. Валюта по умолчанию: EUR.
Категории: {', '.join(EXPENSE_CATEGORIES)}.
Ответь ТОЛЬКО JSON без markdown:
{{"amount": 85.0, "currency": "EUR", "category": "еда", "description": "краткое описание"}}
Если сумма не указана, используй null для amount.""",

    "ADD_TASK": """Извлеки задачу из текста пользователя.
Сегодня: {now}.
Приоритет: 1=высокий(срочно/важно), 2=средний, 3=низкий.
Дедлайн: ISO формат или null.
Ответь ТОЛЬКО JSON без markdown:
{"title": "название задачи", "description": "детали или null", "priority": 2, "deadline": "2024-05-25T15:00:00 или null"}""",

    "ADD_MEETING": """Извлеки встречу из текста пользователя.
Сегодня: {now}.
Ответь ТОЛЬКО JSON без markdown:
{"title": "название", "participants": ["Имя1"], "location": "место или null", "start_dt": "2024-05-25T10:00:00", "end_dt": "2024-05-25T11:00:00 или null", "notes": "заметки или null"}""",

    "ADD_NOTE": """Извлеки заметку из текста пользователя.
Ответь ТОЛЬКО JSON без markdown:
{"content": "текст заметки", "tags": ["тег1", "тег2"], "category": "категория или null"}""",

    "SET_REMINDER": """Извлеки напоминание из текста пользователя.
Сегодня: {now}.
Recurrence: null, "daily", "weekly", "monthly".
Ответь ТОЛЬКО JSON без markdown:
{"text": "текст напоминания", "trigger_at": "2024-05-25T15:00:00", "recurrence": null}""",

    "ADD_TO_GOAL": """Извлеки информацию о пополнении цели из текста.
Ответь ТОЛЬКО JSON без markdown:
{"goal_name": "название цели", "amount": 100.0, "currency": "EUR"}""",
}


async def parse_entity(text: str, intent: str) -> Dict[str, Any]:
    """Парсит сущность по намерению. Возвращает dict с полями."""
    prompt_template = _PARSE_PROMPTS.get(intent)
    if not prompt_template:
        return {}

    system = prompt_template.format(now=_now_str())
    try:
        resp = _client.messages.create(
            model=HAIKU,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        raw = resp.content[0].text.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("parse_entity(%s) error: %s", intent, e)
        return {}


# ─── Контекст беседы ──────────────────────────────────────────────────────────

def _count_tokens_approx(messages: List[dict]) -> int:
    """Грубая оценка токенов (~4 символа = 1 токен)."""
    total = sum(len(str(m.get("content", ""))) for m in messages)
    return total // 4


async def load_context(user_id: int) -> List[dict]:
    raw = await db_service.get_ai_context(user_id)
    try:
        return json.loads(raw)
    except Exception:
        return []


async def save_context(user_id: int, messages: List[dict]) -> None:
    """Сохраняет историю, сжимает если > 3000 токенов."""
    if _count_tokens_approx(messages) > 3000:
        messages = await _compress_context(messages)
    await db_service.save_ai_context(user_id, json.dumps(messages, ensure_ascii=False))


async def _compress_context(messages: List[dict]) -> List[dict]:
    """Сжимает историю через Claude до 500 слов."""
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )
    try:
        resp = _client.messages.create(
            model=HAIKU,
            max_tokens=600,
            system="Summarize this conversation history in 500 words in Russian. Keep key facts, decisions, and context.",
            messages=[{"role": "user", "content": history_text}],
        )
        summary = resp.content[0].text.strip()
        return [{"role": "assistant", "content": f"[История беседы сжата]\n{summary}"}]
    except Exception as e:
        logger.warning("_compress_context error: %s", e)
        # Если не получилось — берём последние 10 сообщений
        return messages[-10:]


# ─── Динамический системный промпт ───────────────────────────────────────────

async def build_system_prompt(user_id: int) -> str:
    now = datetime.now(_TZ)
    try:
        monthly_expenses = await db_service.get_monthly_expense_total(
            user_id, now.year, now.month
        )
        pending_tasks = await db_service.get_pending_task_count(user_id)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59)
        meetings_today = await db_service.get_today_meetings(
            user_id,
            today_start.replace(tzinfo=None),
            today_end.replace(tzinfo=None),
        )
        meetings_str = ", ".join(
            f"{m.start_dt.strftime('%H:%M')} — {m.title}" for m in meetings_today
        ) or "нет"
    except Exception:
        monthly_expenses = 0
        pending_tasks = 0
        meetings_str = "нет"

    return f"""Ты персональный ИИ-ассистент. Отвечай на русском, кратко и по делу.
Часовой пояс пользователя: {TIMEZONE}. Сейчас: {now.strftime('%d.%m.%Y %H:%M')}.

Контекст пользователя:
- Расходы за текущий месяц: {monthly_expenses:.2f} EUR
- Задач в работе: {pending_tasks}
- Встречи сегодня: {meetings_str}

Ты помогаешь вести расходы, задачи, встречи, заметки, напоминания и цели.
При добавлении данных — подтверди что сохранено. При вопросах — давай точные ответы."""


# ─── Свободный чат ────────────────────────────────────────────────────────────

async def chat(user_id: int, text: str) -> str:
    """Свободный чат с сохранением контекста."""
    history = await load_context(user_id)
    system = await build_system_prompt(user_id)

    history.append({"role": "user", "content": text})

    try:
        resp = _client.messages.create(
            model=SONNET,
            max_tokens=1000,
            system=system,
            messages=history,
        )
        reply = resp.content[0].text.strip()
    except Exception as e:
        logger.error("chat error: %s", e)
        reply = "Извини, произошла ошибка. Попробуй ещё раз."

    history.append({"role": "assistant", "content": reply})
    await save_context(user_id, history)
    return reply


# ─── Ответ на запрос данных ───────────────────────────────────────────────────

async def answer_data_query(user_id: int, text: str, data_context: str) -> str:
    """Генерирует ответ на вопрос о данных пользователя."""
    system = await build_system_prompt(user_id)
    try:
        resp = _client.messages.create(
            model=SONNET,
            max_tokens=800,
            system=system,
            messages=[{
                "role": "user",
                "content": f"Данные из базы:\n{data_context}\n\nВопрос пользователя: {text}",
            }],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.error("answer_data_query error: %s", e)
        return "Не удалось получить ответ."


# ─── OCR чека ─────────────────────────────────────────────────────────────────

async def parse_receipt_photo(image_bytes: bytes) -> Dict[str, Any]:
    """Распознаёт чек из фото через Claude Vision."""
    import base64
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    try:
        resp = _client.messages.create(
            model=SONNET,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Это фото чека. Извлеки: магазин, итоговую сумму, валюту, дату, список товаров.\n"
                            "Ответь ТОЛЬКО JSON без markdown:\n"
                            '{"merchant": "...", "amount": 0.0, "currency": "EUR", "date": "YYYY-MM-DD", "items": ["товар 1", "товар 2"]}'
                        ),
                    },
                ],
            }],
        )
        raw = resp.content[0].text.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        return json.loads(raw)
    except Exception as e:
        logger.error("parse_receipt_photo error: %s", e)
        return {}


# ─── Мотивационная фраза для утреннего брифа ─────────────────────────────────

async def generate_morning_motivation(user_id: int) -> str:
    try:
        goals = await db_service.get_goals(user_id)
        goals_text = ""
        if goals:
            goals_text = "Цели пользователя: " + ", ".join(
                f"{g.name} ({float(g.current_amount):.0f}/{float(g.target_amount):.0f})"
                for g in goals
            )
        resp = _client.messages.create(
            model=HAIKU,
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"Напиши короткую мотивирующую фразу (1-2 предложения) на русском для утреннего приветствия. {goals_text}",
            }],
        )
        return resp.content[0].text.strip()
    except Exception:
        return "Удачного дня! Ты справишься со всеми задачами 💪"
