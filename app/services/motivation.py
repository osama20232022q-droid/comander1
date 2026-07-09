from __future__ import annotations

import json
import random
from pathlib import Path

_QUOTES_PATH = Path(__file__).resolve().parents[2] / "assets" / "motivation" / "quotes.json"

# مجموعة أكبر حتى لا تتكرر بسرعة. العبارات قصيرة ومصممة للاستراحة والتحفيز.
_DEFAULT_QUOTES = [
    {"key":"discipline_01","text":"الانضباط ليس شعورًا؛ الانضباط أمر يبدأ في وقته."},
    {"key":"discipline_02","text":"لا تفاوض نفسك أثناء الجلسة. تفاوض قبلها أو بعدها فقط."},
    {"key":"discipline_03","text":"جلسة واحدة صادقة أقوى من ثلاث ساعات مفتوحة بلا ناتج."},
    {"key":"discipline_04","text":"كل يوم بلا صفر. حتى لو كان الحد الأدنى نصف ساعة."},
    {"key":"discipline_05","text":"الطالب الذي يرجع بعد التعثر أخطر من الطالب المتحمس فقط."},
    {"key":"student_01","text":"اقرأ لتطلع بناتج: تعريف، مقارنة، رقم، سؤال."},
    {"key":"student_02","text":"حوّل الخوف إلى سؤال محلول. هذا هو الطريق الأقصر للدرجة."},
    {"key":"student_03","text":"لا تدرس كل المادة الآن. نفّذ المهمة التالية فقط."},
    {"key":"student_04","text":"المادة الثقيلة تُكسر إلى دورات. لا تُهاجمها دفعة واحدة."},
    {"key":"student_05","text":"إذا ضاع وقت، لا تكمل الضياع. ارجع فورًا لأول مهمة صغيرة."},
    {"key":"faith_01","text":"ابدأ باسم الله، وخذ بالأسباب، واترك نتيجة الجهد لله."},
    {"key":"faith_02","text":"الصبر ليس انتظارًا فقط؛ الصبر أن تعمل وأنت متعب."},
    {"key":"faith_03","text":"كل خطوة علم نافعة عبادة إذا صلحت النية واستقام العمل."},
    {"key":"faith_04","text":"إذا ضاق صدرك، صغّر المهمة ولا تترك الطريق."},
    {"key":"faith_05","text":"استعن بالله ثم ابدأ. البداية نصف الانتصار على التسويف."},
    {"key":"quran_msg_01","text":"رسالة قرآنية: لا تقيس الطريق بطوله، قِسه بالخطوة التي تقدر عليها الآن."},
    {"key":"quran_msg_02","text":"رسالة قرآنية: بعد الضيق سعة، وبعد الصبر فتح؛ أكمل جولة واحدة."},
    {"key":"quran_msg_03","text":"رسالة قرآنية: لا تجعل الخوف يوقف العمل؛ اجعل الخوف سببًا للترتيب."},
    {"key":"quran_msg_04","text":"رسالة قرآنية: خذ بالأسباب بهدوء، فالنتائج لا تأتي من القلق."},
    {"key":"quran_msg_05","text":"رسالة قرآنية: قم من مكانك، توضأ إن احتجت، وارجع لجولة أنظف."},
    {"key":"medical_01","text":"طالب الطب ينتصر بالتكرار لا بالاندفاع. راجع، اختبر، صحح."},
    {"key":"medical_02","text":"احفظ المصطلح كما هو، وافهم الفكرة بلغتك. هذا أسرع طريق."},
    {"key":"medical_03","text":"العملي لا يؤجل. الصور والسلايدات تحتاج عينًا متكررة."},
    {"key":"medical_04","text":"كل ملزمة: تعريفات، فروقات، أرقام، فخاخ MCQ. ابدأ بها."},
    {"key":"medical_05","text":"لا تقرأ لتشعر بالراحة؛ اقرأ لتجيب سؤالًا."},
]


def load_quotes() -> list[dict]:
    if _QUOTES_PATH.exists():
        try:
            data = json.loads(_QUOTES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) >= 20:
                return data
        except Exception:
            pass
    return _DEFAULT_QUOTES


def quote_for_user(recent_keys: list[str] | None = None) -> dict:
    quotes = load_quotes()
    recent = set(recent_keys or [])
    pool = [q for q in quotes if q.get("key") not in recent]
    if len(pool) < 5:
        pool = quotes[:]
    return random.choice(pool)
