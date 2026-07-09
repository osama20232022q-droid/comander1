from __future__ import annotations

from app.utils import local_now
from app.services.prayer import prayer_hint


def build_break_recommendation(cycle_number: int, break_minutes: int, focus_score: int | None = None) -> str:
    now = local_now()
    hints: list[str] = []
    p = prayer_hint(now)
    if p:
        hints.append(f"🕌 {p}")
    if cycle_number % 2 == 0:
        hints.append("🚶 امشِ 5-7 دقائق. ممنوع السرير وممنوع السوشال.")
    else:
        hints.append("💧 اشرب ماء، قوم من الكرسي، حرّك رقبتك وظهرك.")
    if focus_score is not None and focus_score <= 2:
        hints.append("🧠 تركيزك منخفض: الجلسة القادمة خليها MCQ أو مراجعة خفيفة بدل قراءة ثقيلة.")
    if break_minutes >= 10 and cycle_number >= 3:
        hints.append("🍽️ إذا صارلك أكثر من 4 ساعات بلا أكل، خذ وجبة خفيفة واكتبها بعد الاستراحة.")
    if now.hour >= 22:
        hints.append("🌙 الوقت متأخر: لا تبدأ موضوع جديد ثقيل. راجع أو نام إذا اكتملت مهمتك الأساسية.")
    return "\n".join(hints)
