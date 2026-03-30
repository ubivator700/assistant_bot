"""Локальный NLP-парсер дат, сумм и приоритетов без внешних зависимостей."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from config import TIMEZONE

_TZ = ZoneInfo(TIMEZONE)

# ─── Приоритеты ───────────────────────────────────────────────────────────────

_HIGH_WORDS = re.compile(
    r"\b(срочно|срочная|критично|критическ|важно|важная|asap|high|высок)\b",
    re.IGNORECASE,
)
_LOW_WORDS = re.compile(
    r"\b(когда-нибудь|не срочно|когда будет время|low|низк|потом|некогда)\b",
    re.IGNORECASE,
)


def parse_priority(text: str) -> int:
    """Возвращает 1=высокий, 2=средний, 3=низкий."""
    if _HIGH_WORDS.search(text):
        return 1
    if _LOW_WORDS.search(text):
        return 3
    return 2


# ─── Суммы ────────────────────────────────────────────────────────────────────

_CURRENCY_MAP = {
    "евро": "EUR", "euro": "EUR", "eur": "EUR", "€": "EUR",
    "доллар": "USD", "dollar": "USD", "usd": "USD", "$": "USD",
    "рубл": "RUB", "руб": "RUB", "rub": "RUB", "₽": "RUB",
    "крон": "CZK", "kč": "CZK", "czk": "CZK", "kc": "CZK",
    "фунт": "GBP", "pound": "GBP", "gbp": "GBP", "£": "GBP",
}

_WORD_NUMBERS = {
    "один": 1, "одну": 1, "одна": 1,
    "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
    "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
    "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40,
    "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
    "восемьдесят": 80, "девяносто": 90, "сто": 100,
    "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700,
    "восемьсот": 800, "девятьсот": 900, "тысяча": 1000,
}

_AMOUNT_PATTERN = re.compile(
    r"(\d[\d\s,\.]*)"
    r"\s*"
    r"(евро|euro|eur|€|доллар[а-яё]*|dollar[s]?|usd|\$|рубл[а-яё]*|руб|rub|₽"
    r"|крон[а-яё]*|kč|czk|kc|фунт[а-яё]*|pound[s]?|gbp|£)",
    re.IGNORECASE,
)

_AMOUNT_PREFIX_PATTERN = re.compile(
    r"(€|\$|₽|£)\s*(\d[\d\s,\.]*)",
    re.IGNORECASE,
)


def parse_amount(text: str) -> Tuple[Optional[float], str]:
    """
    Парсит сумму из текста.
    Возвращает (float | None, currency_code).
    """
    # Пробуем паттерн: «число валюта»
    m = _AMOUNT_PATTERN.search(text)
    if m:
        raw_num = m.group(1).replace(" ", "").replace(",", ".")
        try:
            amount = float(raw_num)
        except ValueError:
            amount = None
        cur_raw = m.group(2).lower().rstrip("аеёийоуыьъяюёс")
        currency = "EUR"
        for key, val in _CURRENCY_MAP.items():
            if cur_raw.startswith(key):
                currency = val
                break
        return amount, currency

    # Пробуем паттерн: «валюта-символ число»
    m = _AMOUNT_PREFIX_PATTERN.search(text)
    if m:
        sym = m.group(1)
        raw_num = m.group(2).replace(" ", "").replace(",", ".")
        try:
            amount = float(raw_num)
        except ValueError:
            amount = None
        currency = _CURRENCY_MAP.get(sym, "EUR")
        return amount, currency

    # Пробуем словесные числа
    lower = text.lower()
    for word, num in sorted(_WORD_NUMBERS.items(), key=lambda x: -x[1]):
        if word in lower:
            for key, val in _CURRENCY_MAP.items():
                if key in lower:
                    return float(num), val
            return float(num), "EUR"

    return None, "EUR"


# ─── Даты ─────────────────────────────────────────────────────────────────────

_WEEKDAYS_RU = {
    "понедельник": 0, "вторник": 1, "среду": 2, "среда": 2,
    "четверг": 3, "пятницу": 4, "пятница": 4, "субботу": 5,
    "суббота": 5, "воскресенье": 6, "воскресенье": 6,
}
_WEEKDAYS_EN = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    "январе": 1, "феврале": 2, "марте": 3, "апреле": 4,
    "июне": 6, "июле": 7, "августе": 8,
    "сентябре": 9, "октябре": 10, "ноябре": 11, "декабре": 12,
}


def _now() -> datetime:
    return datetime.now(_TZ)


def _strip_tz(dt: datetime) -> datetime:
    """Убрать tzinfo перед сохранением в БД (храним UTC или local — без tz)."""
    return dt.replace(tzinfo=None)


def parse_datetime(text: str, tz: Optional[ZoneInfo] = None) -> Optional[datetime]:
    """
    Парсит дату/время из произвольного текста на русском и английском.
    Возвращает datetime без tzinfo (для хранения в БД как local-time).
    """
    tz = tz or _TZ
    lower = text.lower()
    now = datetime.now(tz)

    # время по умолчанию если не указано
    default_hour = 9
    default_minute = 0

    # Извлечь время «в 15:00» / «в 9:30» / «at 15:00»
    time_match = re.search(r"(?:в|at)\s+(\d{1,2})[:\.](\d{2})", lower)
    if time_match:
        default_hour = int(time_match.group(1))
        default_minute = int(time_match.group(2))
    else:
        # «в 9» / «at 9»
        time_match2 = re.search(r"(?:в|at)\s+(\d{1,2})\b", lower)
        if time_match2:
            default_hour = int(time_match2.group(1))
        # «утром» → 9, «днём» → 13, «вечером» → 19
        elif "утром" in lower or "morning" in lower:
            default_hour = 9
        elif "днём" in lower or "днем" in lower or "afternoon" in lower:
            default_hour = 13
        elif "вечером" in lower or "evening" in lower or "night" in lower:
            default_hour = 19

    def make_dt(base: datetime) -> datetime:
        return _strip_tz(base.replace(hour=default_hour, minute=default_minute, second=0, microsecond=0))

    # Относительные
    if "сейчас" in lower or "now" in lower:
        return _strip_tz(now)
    if "через час" in lower or "in an hour" in lower or "in 1 hour" in lower:
        return _strip_tz(now + timedelta(hours=1))
    if m := re.search(r"через\s+(\d+)\s*час", lower):
        return _strip_tz(now + timedelta(hours=int(m.group(1))))
    if m := re.search(r"через\s+(\d+)\s*мин", lower):
        return _strip_tz(now + timedelta(minutes=int(m.group(1))))
    if m := re.search(r"через\s+(\d+)\s*д[еня]", lower):
        return make_dt(now + timedelta(days=int(m.group(1))))
    if "завтра" in lower or "tomorrow" in lower:
        return make_dt(now + timedelta(days=1))
    if "послезавтра" in lower or "day after tomorrow" in lower:
        return make_dt(now + timedelta(days=2))
    if "сегодня" in lower or "today" in lower:
        return make_dt(now)
    if "следующей неделе" in lower or "next week" in lower:
        return make_dt(now + timedelta(weeks=1))

    # День недели
    for name, wd in {**_WEEKDAYS_RU, **_WEEKDAYS_EN}.items():
        if name in lower:
            days_ahead = wd - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return make_dt(now + timedelta(days=days_ahead))

    # «25 мая», «25.05», «25/05/2024», «2024-05-25»
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", lower):
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                          default_hour, default_minute, tzinfo=tz)
            return _strip_tz(dt)
        except ValueError:
            pass

    if m := re.search(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", lower):
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        if year < 100:
            year += 2000
        try:
            dt = datetime(year, month, day, default_hour, default_minute, tzinfo=tz)
            return _strip_tz(dt)
        except ValueError:
            pass

    if m := re.search(r"(\d{1,2})\s+(" + "|".join(_MONTHS_RU.keys()) + r")", lower):
        day = int(m.group(1))
        month = _MONTHS_RU[m.group(2)]
        year = now.year
        dt = datetime(year, month, day, default_hour, default_minute, tzinfo=tz)
        if dt < now:
            dt = dt.replace(year=year + 1)
        return _strip_tz(dt)

    return None
