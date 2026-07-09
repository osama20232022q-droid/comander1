from __future__ import annotations

# زر حفزني أصبح قرآنيًا فقط: كل الرسائل تأتي من بنك الآيات/الرسائل القرآنية
# المستخدم رفع ملف "رسائل من القرآن" كمصدر تحفيزي، والرسائل هنا قصيرة ومناسبة للبوت.
from app.services.prayer import motivation_quote


def quote_for_user(recent_keys: list[str] | None = None) -> dict:
    return motivation_quote(recent_keys)
