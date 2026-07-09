from __future__ import annotations

from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

from app.config import settings


def now() -> datetime:
    return datetime.now(settings.timezone)


def today() -> date:
    return now().date()


def parse_hhmm(value: str) -> time:
    hour, minute = value.strip().split(':')[:2]
    return time(int(hour), int(minute))


def combine_today(hhmm: str, tz: ZoneInfo | None = None) -> datetime:
    tz = tz or settings.timezone
    return datetime.combine(today(), parse_hhmm(hhmm), tzinfo=tz)


def minutes_between(start_iso: str, end_iso: str | None = None) -> int:
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso) if end_iso else now()
    return max(0, int((end - start).total_seconds() // 60))


def week_bounds(target: date | None = None) -> tuple[date, date]:
    target = target or today()
    start = target - timedelta(days=target.weekday())
    end = start + timedelta(days=6)
    return start, end


def human_minutes(minutes: int) -> str:
    h, m = divmod(max(0, minutes), 60)
    if h and m:
        return f'{h}س {m}د'
    if h:
        return f'{h}س'
    return f'{m}د'
