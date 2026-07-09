from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import fitz  # PyMuPDF

from app.config import settings


@dataclass
class LectureAnalysis:
    pages: int
    words: int
    tables_or_lists_score: int
    image_score: int
    density: str
    difficulty: str
    estimated_minutes: int
    strategy: str
    key_risks: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def heuristic_pdf_analysis(path: Path, student_level: str = 'متوسط', exam_type: str = 'MCQ + short essay') -> LectureAnalysis:
    doc = fitz.open(path)
    pages = len(doc)
    total_words = 0
    image_score = 0
    list_score = 0
    for page in doc:
        text = page.get_text('text') or ''
        words = len(text.split())
        total_words += words
        list_score += text.count('•') + text.count('- ') + text.count('1.') + text.count('2.')
        image_score += len(page.get_images(full=True))

    words_per_page = total_words / max(1, pages)
    if words_per_page < 120:
        density = 'خفيفة'
        base_per_page = 4
    elif words_per_page < 240:
        density = 'متوسطة'
        base_per_page = 6
    else:
        density = 'ثقيلة'
        base_per_page = 9

    difficulty_multiplier = {
        'ضعيف': 1.55,
        'متوسط': 1.25,
        'جيد': 1.0,
        'قوي': 0.75,
    }.get(student_level, 1.25)

    extra = 0
    if list_score > pages * 4:
        extra += pages * 2
    if image_score > 0:
        extra += min(30, image_score * 4)
    if 'short' in exam_type.lower() or 'essay' in exam_type.lower():
        extra += pages * 2

    estimated = int((pages * base_per_page + extra) * difficulty_multiplier)
    if estimated < 25:
        estimated = 25

    if estimated <= 60:
        difficulty = 'سهلة'
    elif estimated <= 150:
        difficulty = 'متوسطة'
    elif estimated <= 260:
        difficulty = 'صعبة'
    else:
        difficulty = 'قاتلة'

    risks = []
    if image_score:
        risks.append('توجد صور/رسومات: خصص وقت عملي أو visual recall.')
    if list_score > pages * 4:
        risks.append('توجد تعداديات كثيرة: محتملة MCQ/short essay.')
    if words_per_page > 240:
        risks.append('كثافة نص عالية: لا تقرأها دفعة واحدة.')

    strategy = (
        'قراءة عناوين أولًا، بعدها تعريفات ومقارنات، ثم MCQ. '
        'إذا التركيز نزل، حوّل الجلسة إلى أسئلة بدل قراءة جديدة.'
    )
    return LectureAnalysis(pages, total_words, list_score, image_score, density, difficulty, estimated, strategy, risks)


async def ai_enrich_analysis(text: str, student_level: str, exam_type: str) -> dict:
    """Optional deep analysis. Works only when OPENAI_API_KEY is configured."""
    if not settings.openai_api_key:
        return {}
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        clipped = text[:12000]
        prompt = f"""
You are a strict medical exam planner. Analyze this lecture for a student whose level is {student_level}.
Exam type: {exam_type}.
Return JSON only with: topics, high_yield_points, mcq_traps, short_essay_likely, study_strategy, estimated_minutes_adjustment.
Lecture text:
{clipped}
"""
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or '{}'
        return json.loads(content)
    except Exception as exc:  # pragma: no cover
        return {'ai_error': str(exc)}


def extract_pdf_text(path: Path, max_chars: int = 20000) -> str:
    doc = fitz.open(path)
    chunks = []
    for page in doc:
        chunks.append(page.get_text('text') or '')
        if sum(len(c) for c in chunks) >= max_chars:
            break
    return '\n'.join(chunks)[:max_chars]
