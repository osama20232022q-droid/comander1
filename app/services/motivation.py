from __future__ import annotations

import json
import random
from pathlib import Path

_QUOTES_PATH = Path(__file__).resolve().parents[2] / "assets" / "motivation" / "quotes.json"

_DEFAULT_QUOTES = [
    {"key": "discipline_1", "text": "الانضباط ليس شعورًا؛ هو قرار يتكرر حتى يصير عادة."},
    {"key": "quran_meaning_1", "text": "تذكير: مع العسر يفتح الله أبواب اليسر. قم للخطوة القادمة فقط."},
    {"key": "student_1", "text": "لا تحتاج أن تُنهي الجبل اليوم. المطلوب أن لا تترك المعسكر."},
    {"key": "faith_1", "text": "ابدأ باسم الله، وخذ بالأسباب، ولا تفاوض نفسك وقت التنفيذ."},
    {"key": "medical_1", "text": "طالب الطب لا ينتصر بالحماس؛ ينتصر بالتكرار اليومي الهادئ."},
]


def load_quotes() -> list[dict]:
    if _QUOTES_PATH.exists():
        try:
            return json.loads(_QUOTES_PATH.read_text(encoding="utf-8"))
        except Exception:
            return _DEFAULT_QUOTES
    return _DEFAULT_QUOTES


def random_quote() -> dict:
    return random.choice(load_quotes())
