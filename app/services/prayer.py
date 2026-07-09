from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select

from app.config import settings
from app.db import get_session
from app.models import PrayerTimeCache

BAGHDAD_TZ = ZoneInfo(settings.timezone or "Asia/Baghdad")

# Coordinates are central-city approximations for each Iraqi governorate.
IRAQ_GOVERNORATES: dict[str, tuple[float, float]] = {
    "بغداد": (33.3152, 44.3661),
    "البصرة": (30.5085, 47.7804),
    "نينوى / الموصل": (36.3456, 43.1570),
    "أربيل": (36.1911, 44.0092),
    "السليمانية": (35.5613, 45.4351),
    "دهوك": (36.8662, 42.9876),
    "كركوك": (35.4681, 44.3922),
    "صلاح الدين / تكريت": (34.6071, 43.6782),
    "ديالى / بعقوبة": (33.7500, 44.6411),
    "الأنبار / الرمادي": (33.4206, 43.3078),
    "واسط / الكوت": (32.5128, 45.8182),
    "بابل / الحلة": (32.4682, 44.5502),
    "كربلاء": (32.6160, 44.0249),
    "النجف": (32.0000, 44.3333),
    "القادسية / الديوانية": (31.9870, 44.9250),
    "المثنى / السماوة": (31.3139, 45.2803),
    "ذي قار / الناصرية": (31.0520, 46.2610),
    "ميسان / العمارة": (31.8356, 47.1440),
}

FALLBACK_TIMES = {
    "fajr": "04:00",
    "dhuhr": "12:05",
    "maghrib": "18:55",
}

PRAYER_LABELS = {
    "fajr": "صلاة الصبح",
    "dhuhr_asr": "صلاة الظهر والعصر",
    "maghrib_isha": "صلاة المغرب والعشاء",
}

# Short Quranic excerpts and study-focused reminders. Keep them short and rotate by date/prayer.
# The motivation button also uses this same bank so all motivation stays Quran-centered.
QURAN_STUDY_MESSAGES = [
    {"key":"q001","ayah":"﴿وَاسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ﴾","note":"الصلاة تقطع الفوضى وتعيد تركيزك؛ ارجع بعدها لجولة صغيرة صادقة."},
    {"key":"q002","ayah":"﴿إِنَّ مَعَ الْعُسْرِ يُسْرًا﴾","note":"لا تجعل صعوبة المادة توقفك؛ خذ صفحة واحدة ثم أكمل."},
    {"key":"q003","ayah":"﴿وَقُل رَّبِّ زِدْنِي عِلْمًا﴾","note":"النية الصافية تجعل الدراسة أهدأ وأقوى."},
    {"key":"q004","ayah":"﴿لَا يُكَلِّفُ اللَّهُ نَفْسًا إِلَّا وُسْعَهَا﴾","note":"نفّذ ما تقدر عليه الآن، ولا تترك اليوم يضيع بالكامل."},
    {"key":"q005","ayah":"﴿فَإِذَا عَزَمْتَ فَتَوَكَّلْ عَلَى اللَّهِ﴾","note":"بعد الصلاة لا تفاوض نفسك؛ ابدأ أول مهمة مباشرة."},
    {"key":"q006","ayah":"﴿وَاصْبِرْ وَمَا صَبْرُكَ إِلَّا بِاللَّهِ﴾","note":"الصبر الدراسي يعني ترجع للجلسة حتى لو مزاجك ضعيف."},
    {"key":"q007","ayah":"﴿إِنَّ اللَّهَ مَعَ الصَّابِرِينَ﴾","note":"الجولات الصغيرة المتكررة تبني نجاحك أكثر من الحماس المؤقت."},
    {"key":"q008","ayah":"﴿وَمَا تَوْفِيقِي إِلَّا بِاللَّهِ﴾","note":"خذ بالأسباب: صلاة، ماء، جلسة، سؤال، مراجعة."},
    {"key":"q009","ayah":"﴿فَاذْكُرُونِي أَذْكُرْكُمْ﴾","note":"اذكر الله ثم ارجع بنية أوضح وذهن أهدأ."},
    {"key":"q010","ayah":"﴿إِنَّ اللَّهَ يُحِبُّ الْمُتَوَكِّلِينَ﴾","note":"التوكل ليس ترك الدراسة؛ التوكل تنفيذ الخطة بلا هلع."},
    {"key":"q011","ayah":"﴿وَاللَّهُ مَعَكُمْ﴾","note":"لا تبدأ الجلسة وكأنك وحدك؛ رتّب قلبك ثم رتّب وقتك."},
    {"key":"q012","ayah":"﴿سَيَجْعَلُ اللَّهُ بَعْدَ عُسْرٍ يُسْرًا﴾","note":"المادة التي تخيفك اليوم تصير أسهل بالتكرار."},
    {"key":"q013","ayah":"﴿رَبِّ اشْرَحْ لِي صَدْرِي﴾","note":"إذا ضاق صدرك، لا تترك؛ صغّر المهمة وابدأ."},
    {"key":"q014","ayah":"﴿وَتَوَكَّلْ عَلَى الْحَيِّ الَّذِي لَا يَمُوتُ﴾","note":"لا تربط قوتك بالمزاج؛ اربطها بالواجب."},
    {"key":"q015","ayah":"﴿وَاصْبِرْ لِحُكْمِ رَبِّكَ﴾","note":"التأخير لا يُصلح بالذعر؛ يُصلح بجلسة الآن."},
    {"key":"q016","ayah":"﴿إِنَّ رَبِّي قَرِيبٌ مُّجِيبٌ﴾","note":"ادعُ، ثم افتح الملزمة، فالعمل باب الإجابة."},
    {"key":"q017","ayah":"﴿وَمَن يَتَّقِ اللَّهَ يَجْعَل لَّهُ مَخْرَجًا﴾","note":"اجعل الصلاة بوابة ترتيب لا بوابة تسويف."},
    {"key":"q018","ayah":"﴿وَمَن يَتَوَكَّلْ عَلَى اللَّهِ فَهُوَ حَسْبُهُ﴾","note":"ابدأ بما عليك، واترك ثقل النتيجة."},
    {"key":"q019","ayah":"﴿إِنَّ اللَّهَ لَا يُضِيعُ أَجْرَ الْمُحْسِنِينَ﴾","note":"كل جلسة صادقة محفوظة، حتى لو كانت قصيرة."},
    {"key":"q020","ayah":"﴿فَاصْبِرْ صَبْرًا جَمِيلًا﴾","note":"الصبر الجميل اليوم: جلسة بلا هاتف بعد الصلاة."},
    {"key":"q021","ayah":"﴿رَبِّ زِدْنِي عِلْمًا﴾","note":"كررها قبل الجلسة، ثم اسأل نفسك: ما السؤال الذي سأجيب عنه؟"},
    {"key":"q022","ayah":"﴿إِنَّ مَعِيَ رَبِّي سَيَهْدِينِ﴾","note":"إذا شعرت بالضياع، ارجع للخطوة التالية فقط."},
    {"key":"q023","ayah":"﴿وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ﴾","note":"لا تحكم على نفسك من يوم ضعيف؛ أصلح الساعة القادمة."},
    {"key":"q024","ayah":"﴿قُلْ عَسَىٰ أَن يَهْدِيَنِ رَبِّي لِأَقْرَبَ مِنْ هَٰذَا رَشَدًا﴾","note":"اطلب الرشد في اختيار ماذا تدرس الآن، لا كل شيء دفعة واحدة."},
]


def governorate_buttons() -> list[list[str]]:
    names = list(IRAQ_GOVERNORATES.keys())
    rows: list[list[str]] = []
    for i in range(0, len(names), 2):
        rows.append(names[i:i+2])
    rows.append(["❌ إلغاء تفعيل أذكار الصلاة", "🏠 القائمة الرئيسية"])
    return rows


def normalize_time(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"(\d{1,2})[:٫.](\d{2})", str(value))
    if not m:
        return None
    h = int(m.group(1)); minute = int(m.group(2))
    if not (0 <= h <= 23 and 0 <= minute <= 59):
        return None
    return f"{h:02d}:{minute:02d}"


def _extract_times(payload: object) -> dict[str, str] | None:
    """Robustly extract fajr/dhuhr/maghrib from Haqibat al-Mu'min style JSON."""
    candidates: list[dict] = []
    if isinstance(payload, dict):
        candidates.append(payload)
        for k in ["times", "data", "prayerTimes", "result"]:
            if isinstance(payload.get(k), dict):
                candidates.append(payload[k])
        # recursive shallow list/dict scan
        for v in payload.values():
            if isinstance(v, dict):
                candidates.append(v)
            elif isinstance(v, list):
                candidates.extend([x for x in v if isinstance(x, dict)])
    for d in candidates:
        lower = {str(k).lower(): v for k, v in d.items()}
        fajr = lower.get("fajr") or lower.get("الفجر") or lower.get("soboh") or lower.get("subuh")
        dhuhr = lower.get("dhuhr") or lower.get("duhr") or lower.get("zuhr") or lower.get("الظهر") or lower.get("noon")
        maghrib = lower.get("maghrib") or lower.get("المغرب") or lower.get("sunset")
        out = {
            "fajr": normalize_time(str(fajr)) if fajr is not None else None,
            "dhuhr": normalize_time(str(dhuhr)) if dhuhr is not None else None,
            "maghrib": normalize_time(str(maghrib)) if maghrib is not None else None,
        }
        if all(out.values()):
            return out  # type: ignore
    return None


def fetch_hq_times(governorate: str) -> tuple[dict[str, str], str, str | None]:
    lat, lon = IRAQ_GOVERNORATES.get(governorate, IRAQ_GOVERNORATES["بغداد"])
    params = urllib.parse.urlencode({
        "v": "jsonPrayerTimes",
        "timezone": settings.timezone or "Asia/Baghdad",
        "long": str(lon),
        "lati": str(lat),
    })
    url = f"https://hq.alkafeel.net/Api/init/init.php?{params}"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            raw = r.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        times = _extract_times(payload)
        if times:
            return times, "hq.alkafeel.net", raw[:4000]
    except Exception:
        pass
    return dict(FALLBACK_TIMES), "fallback", None


def get_prayer_times(governorate: str, now: datetime | None = None) -> dict[str, str]:
    now = now or datetime.now(BAGHDAD_TZ)
    date_key = now.strftime("%Y-%m-%d")
    with get_session() as db:
        row = db.scalar(select(PrayerTimeCache).where(PrayerTimeCache.governorate == governorate, PrayerTimeCache.date_key == date_key))
        if row:
            return {"fajr": row.fajr, "dhuhr": row.dhuhr, "maghrib": row.maghrib}
        times, source, raw = fetch_hq_times(governorate)
        row = PrayerTimeCache(
            governorate=governorate,
            date_key=date_key,
            fajr=times["fajr"],
            dhuhr=times["dhuhr"],
            maghrib=times["maghrib"],
            source=source,
            raw_json=raw,
        )
        db.add(row)
        db.commit()
        return times


def parse_hhmm(date: datetime, hhmm: str) -> datetime:
    h, m = [int(x) for x in hhmm.split(":")[:2]]
    return date.replace(hour=h, minute=m, second=0, microsecond=0)


def prayer_events_for_day(governorate: str, now: datetime | None = None) -> list[tuple[str, datetime]]:
    now = now or datetime.now(BAGHDAD_TZ)
    times = get_prayer_times(governorate, now)
    return [
        ("fajr", parse_hhmm(now, times["fajr"])),
        ("dhuhr_asr", parse_hhmm(now, times["dhuhr"])),
        ("maghrib_isha", parse_hhmm(now, times["maghrib"])),
    ]


def upcoming_prayer(governorate: str, now: datetime | None = None) -> tuple[str, datetime] | None:
    now = now or datetime.now(BAGHDAD_TZ)
    for key, dt in prayer_events_for_day(governorate, now):
        if dt >= now:
            return key, dt
    # tomorrow fajr
    tomorrow = now + timedelta(days=1)
    times = get_prayer_times(governorate, tomorrow)
    return "fajr", parse_hhmm(tomorrow, times["fajr"])


def seconds_until_next_prayer(governorate: str, now: datetime | None = None) -> tuple[str, int] | None:
    now = now or datetime.now(BAGHDAD_TZ)
    nxt = upcoming_prayer(governorate, now)
    if not nxt:
        return None
    key, dt = nxt
    return key, int((dt - now).total_seconds())


def quran_message_for(prayer_key: str, date_key: str) -> dict:
    # Deterministic: different by day and prayer, stable across users.
    offset = {"fajr": 0, "dhuhr_asr": 7, "maghrib_isha": 14}.get(prayer_key, 0)
    n = sum(ord(ch) for ch in date_key) + offset
    return QURAN_STUDY_MESSAGES[n % len(QURAN_STUDY_MESSAGES)]


def build_prayer_text(governorate: str, prayer_key: str, when_dt: datetime | None = None) -> str:
    when_dt = when_dt or datetime.now(BAGHDAD_TZ)
    date_key = when_dt.strftime("%Y-%m-%d")
    q = quran_message_for(prayer_key, date_key)
    label = PRAYER_LABELS.get(prayer_key, prayer_key)
    clock = when_dt.strftime("%H:%M")
    return (
        f"🕌 {label} — {governorate}\n\n"
        f"حان وقت {label} حسب توقيت {governorate} ({clock}).\n"
        f"أوقف الدراسة، صلِّ، ثم ارجع بخطة أصغر وأقوى.\n\n"
        f"{q['ayah']}\n"
        f"{q['note']}"
    )


def motivation_quote(recent_keys: list[str] | None = None) -> dict:
    recent = set(recent_keys or [])
    pool = [q for q in QURAN_STUDY_MESSAGES if q["key"] not in recent]
    if len(pool) < 5:
        pool = QURAN_STUDY_MESSAGES[:]
    import random
    q = random.choice(pool)
    return {"key": q["key"], "text": f"{q['ayah']}\n\n{q['note']}"}


def prayer_hint(now: datetime | None = None, governorate: str = "بغداد", window_minutes: int = 15) -> str | None:
    """Small backward-compatible helper used by break_engine.

    Returns a short prayer hint if a prayer is close. Defaults to Baghdad when the
    caller does not know the student's governorate, so older break logic keeps
    working instead of crashing.
    """
    now = now or datetime.now(BAGHDAD_TZ)
    try:
        nxt = seconds_until_next_prayer(governorate, now)
        if not nxt:
            return None
        key, seconds = nxt
        if 0 <= seconds <= window_minutes * 60:
            label = PRAYER_LABELS.get(key, key)
            minutes = max(0, seconds // 60)
            if minutes <= 1:
                return f"{label} قريبة جدًا. اجعل الاستراحة للصلاة ثم ارجع للدراسة."
            return f"باقي تقريبًا {minutes} دقيقة على {label}. رتّب جلستك حتى لا تتجاوز وقت الصلاة."
    except Exception:
        return None
    return None
