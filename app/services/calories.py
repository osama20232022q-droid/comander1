from __future__ import annotations

FOOD_CALORIES = {
    "تمن": (250, 350),
    "رز": (250, 350),
    "rice": (250, 350),
    "دجاج": (160, 300),
    "صدر": (160, 260),
    "chicken": (160, 300),
    "تونة": (120, 220),
    "tuna": (120, 220),
    "بيض": (70, 160),
    "egg": (70, 160),
    "خبز": (120, 250),
    "صمون": (180, 300),
    "bread": (120, 250),
    "لبن": (80, 180),
    "زبادي": (80, 180),
    "yogurt": (80, 180),
    "موز": (90, 130),
    "banana": (90, 130),
    "تمر": (25, 80),
    "date": (25, 80),
    "شاي": (0, 80),
    "tea": (0, 80),
    "قهوة": (0, 80),
    "coffee": (0, 80),
    "حلويات": (250, 600),
    "sweet": (250, 600),
    "اندومي": (350, 550),
    "noodle": (350, 550),
    "فلافل": (250, 700),
    "falafel": (250, 700),
    "كباب": (300, 700),
    "kebab": (300, 700),
    "مرق": (100, 300),
    "بامية": (100, 250),
    "ماء": (0, 0),
    "water": (0, 0),
}


def estimate_calories(text: str) -> tuple[int | None, int | None, list[str]]:
    t = (text or "").lower()
    matches: list[str] = []
    low = high = 0
    for key, (mn, mx) in FOOD_CALORIES.items():
        if key in t:
            matches.append(key)
            low += mn
            high += mx
    if not matches:
        return None, None, []
    return low, high, matches
