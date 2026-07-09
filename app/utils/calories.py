from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CalorieEstimate:
    item: str
    calories_min: int
    calories_max: int
    note: str


# تقريب عملي عراقي، ليس بديلًا عن أخصائي تغذية.
FOOD_TABLE = {
    'تمن': (250, 420, 'صحن تمن متوسط'),
    'رز': (250, 420, 'صحن رز متوسط'),
    'دجاج': (160, 300, 'قطعة/نصف صدر دجاج حسب الحجم'),
    'صدر دجاج': (180, 280, 'صدر دجاج مشوي/مسلوق'),
    'تونة': (120, 220, 'علبة تونة حسب الزيت'),
    'بيض': (70, 90, 'بيضة واحدة'),
    'بيضة': (70, 90, 'بيضة واحدة'),
    'خبز': (120, 220, 'رغيف/صمون حسب الحجم'),
    'صمون': (150, 250, 'صمون واحد'),
    'موز': (90, 130, 'موزة متوسطة'),
    'تمر': (20, 30, 'تمرة واحدة'),
    'شاي': (0, 80, 'حسب السكر'),
    'قهوة': (0, 60, 'حسب السكر والحليب'),
    'لبن': (90, 180, 'كوب لبن'),
    'زبادي': (80, 160, 'علبة/كوب'),
    'فلافل': (55, 90, 'حبة فلافل'),
    'اندومي': (350, 500, 'كيس واحد'),
    'حلو': (150, 450, 'قطعة حلويات حسب النوع'),
    'حلويات': (150, 450, 'قطعة حلويات حسب النوع'),
    'زيتون': (5, 8, 'حبة زيتون واحدة'),
    'لحم': (180, 350, 'قطعة لحم متوسطة'),
    'سمك': (150, 280, 'قطعة سمك'),
    'بطاطا': (120, 350, 'مسلوقة/مقلية حسب التحضير'),
}

NUMBER_WORDS = {
    'نص': 0.5,
    'نصف': 0.5,
    'واحد': 1,
    'وحده': 1,
    'واحدة': 1,
    'اثنين': 2,
    'ثنين': 2,
    'ثلاث': 3,
    'ثلاثة': 3,
    'اربع': 4,
    'اربعة': 4,
    'خمس': 5,
    'خمسة': 5,
    'عشر': 10,
    'عشرة': 10,
}


def _quantity_near(text: str, key: str) -> float:
    pattern = rf'(\d+|نص|نصف|واحد|وحده|واحدة|اثنين|ثنين|ثلاث|ثلاثة|اربع|اربعة|خمس|خمسة|عشر|عشرة)\s+\S*\s*{re.escape(key)}'
    match = re.search(pattern, text)
    if not match:
        return 1.0
    token = match.group(1)
    if token.isdigit():
        return float(token)
    return float(NUMBER_WORDS.get(token, 1))


def estimate_food_calories(text: str) -> CalorieEstimate:
    original = text.strip()
    normalized = original.replace('ة', 'ه').replace('أ', 'ا').replace('إ', 'ا')
    total_min = 0
    total_max = 0
    found: list[str] = []

    for key, (cmin, cmax, note) in FOOD_TABLE.items():
        key_norm = key.replace('ة', 'ه')
        if key_norm in normalized:
            q = _quantity_near(normalized, key_norm)
            total_min += int(cmin * q)
            total_max += int(cmax * q)
            found.append(f'{key} x{q:g}')

    if not found:
        return CalorieEstimate(original, 0, 0, 'غير موجود بقاعدة الطعام. أدخل السعرات يدويًا أو أضف الطعام للجدول لاحقًا.')

    if total_max >= 700:
        note = 'وجبة ثقيلة نسبيًا. الجلسة القادمة يفضل تكون مراجعة/MCQ أو مشي 10 دقائق قبلها.'
    elif total_max <= 180:
        note = 'وجبة خفيفة. مناسبة لاستراحة قصيرة بين الجلسات.'
    else:
        note = 'وجبة متوسطة. راقب النعاس بعد الأكل.'

    return CalorieEstimate(', '.join(found), total_min, total_max, note)
