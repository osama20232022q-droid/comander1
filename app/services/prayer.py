from __future__ import annotations

from datetime import datetime, time

# Offline fallback for Iraq. The bot does NOT claim astronomical accuracy.
# Users can treat these as soft schedule reminders until a prayer API is connected.
IRAQ_SOFT_PRAYER_WINDOWS = {
    "fajr": time(4, 0),
    "dhuhr": time(12, 5),
    "asr": time(15, 45),
    "maghrib": time(18, 55),
    "isha": time(20, 20),
}


def next_soft_prayer(now: datetime) -> tuple[str, time] | None:
    current = now.time()
    for name, t in IRAQ_SOFT_PRAYER_WINDOWS.items():
        if current <= t:
            return name, t
    return "fajr", IRAQ_SOFT_PRAYER_WINDOWS["fajr"]


def prayer_hint(now: datetime) -> str | None:
    nxt = next_soft_prayer(now)
    if not nxt:
        return None
    name, t = nxt
    # soft hint only if within 25 minutes by simple minute calculation same day
    delta_minutes = (t.hour * 60 + t.minute) - (now.hour * 60 + now.minute)
    if 0 <= delta_minutes <= 25:
        return f"وقت صلاة {name} قريب. رتّب الاستراحة للصلاة ثم ارجع للجلسة."
    return None
