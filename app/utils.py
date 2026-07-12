from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings

AR_EN_NAME_RE = re.compile(r"^[\u0600-\u06FFa-zA-Z][\u0600-\u06FFa-zA-Z'\-\.]*$")


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


def normalize_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def validate_triple_name(text: str) -> tuple[bool, str]:
    text = normalize_text(text)
    parts = [p for p in text.split(" ") if p]
    if len(parts) < 3:
        return False, "لازم الاسم يكون ثلاثي على الأقل. مثال: أحمد علي حسن"
    if len(parts) > 6:
        return False, "الاسم طويل جدًا. اكتب الاسم الثلاثي أو الرباعي فقط."
    for p in parts:
        if len(p) < 2 or not AR_EN_NAME_RE.match(p):
            return False, "الاسم يحتوي رموز أو كلمات غير واضحة. اكتب اسم عربي أو إنكليزي حقيقي."
    return True, text


def classify_college(college: str) -> tuple[str, str]:
    c = college.lower()
    if any(w in c for w in ["طب", "medicine", "medical", "كلية الطب"]):
        return "medicine", "طب بشري: كثافة عالية، نظري وعملي، حفظ وفهم ومراجعة صور."
    if any(w in c for w in ["اسنان", "أسنان", "dent"]):
        return "dentistry", "طب أسنان: مواد طبية + عملي وصور وتشريح وتطبيق."
    if any(w in c for w in ["صيد", "pharm"]):
        return "pharmacy", "صيدلة: حفظ وفهم، كيمياء، أدوية، أسماء، وتداخلات."
    if any(w in c for w in ["هند", "engineer"]):
        return "engineering", "هندسة: مسائل، تطبيق، مشاريع، وفهم خطوات."
    if any(w in c for w in ["تمريض", "nurs"]):
        return "nursing", "تمريض: عملي، مهارات، حالات سريرية، ونظري."
    if any(w in c for w in ["علوم", "science"]):
        return "science", "علوم: فهم نظري، مختبر، تصنيف ومصطلحات."
    return "general", "تخصص عام: سيتم بناء الخطة حسب المواد والملفات المرفوعة."


def parse_health(text: str) -> tuple[int | None, float | None, float | None]:
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if len(nums) < 3:
        return None, None, None
    age = int(float(nums[0]))
    height = float(nums[1])
    weight = float(nums[2])
    if not (8 <= age <= 80):
        age = None
    if not (80 <= height <= 230):
        height = None
    if not (20 <= weight <= 250):
        weight = None
    return age, height, weight


def html_escape(s: str | None) -> str:
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
