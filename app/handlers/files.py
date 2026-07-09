from __future__ import annotations

import json
from pathlib import Path

from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import settings
from app.keyboards import back_keyboard, subjects_keyboard
from app.services.subject_service import add_lecture, list_subjects
from app.services.user_service import get_user_profile, upsert_user
from app.states import FileStates
from app.utils.lecture_analyzer import ai_enrich_analysis, extract_pdf_text, heuristic_pdf_analysis

router = Router()


@router.message(F.text == '📎 رفع ملزمة PDF')
async def upload_pdf_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(FileStates.waiting_pdf_subject)
    user = await upsert_user(message.from_user)
    subjects = await list_subjects(user['id'])
    if not subjects:
        await state.clear()
        await message.answer('أضف مادة أولًا قبل رفع الملزمة.', reply_markup=subjects_keyboard())
        return
    await message.answer(
        'اكتب رقم المادة، ثم أرسل ملف PDF بعدها.\n' + '\n'.join(f'{s["id"]}. {s["name"]}' for s in subjects),
        reply_markup=back_keyboard(),
    )


@router.message(FileStates.waiting_pdf_subject)
async def receive_pdf_subject(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer('اكتب رقم المادة فقط.')
        return
    await state.update_data(subject_id=int(message.text.strip()))
    await message.answer('الآن أرسل ملف PDF للملزمة.')


@router.message(F.document)
async def receive_document(message: Message, bot: Bot, state: FSMContext) -> None:
    if not message.document.file_name.lower().endswith('.pdf'):
        await message.answer('حاليًا التحليل يدعم PDF فقط.')
        return
    user = await upsert_user(message.from_user)
    data = await state.get_data()
    subject_id = data.get('subject_id')
    if not subject_id:
        subjects = await list_subjects(user['id'])
        if not subjects:
            await message.answer('أضف مادة أولًا، ثم ارفع PDF.')
            return
        subject_id = subjects[0]['id']
    file = await bot.get_file(message.document.file_id)
    safe_name = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in message.document.file_name)
    path = settings.uploads_dir / f'{user["id"]}_{safe_name}'
    await bot.download_file(file.file_path, destination=path)

    profile = await get_user_profile(user['id'])
    level = profile.get('study_level') or 'متوسط'
    analysis = heuristic_pdf_analysis(Path(path), student_level=level, exam_type='MCQ + short essay + practical')
    payload = json.loads(analysis.to_json())
    text = extract_pdf_text(Path(path), max_chars=12000)
    ai_payload = await ai_enrich_analysis(text, level, 'MCQ + short essay + practical')
    if ai_payload:
        payload['ai'] = ai_payload
    lecture_id = await add_lecture(
        subject_id=int(subject_id),
        title=message.document.file_name,
        pages=analysis.pages,
        difficulty=analysis.difficulty,
        estimated_minutes=analysis.estimated_minutes,
        analysis_json=json.dumps(payload, ensure_ascii=False),
        file_path=str(path),
    )
    await state.clear()
    risks = '\n'.join(f'- {r}' for r in analysis.key_risks) or '- لا توجد مخاطر واضحة.'
    await message.answer(
        f'✅ تم استلام وتحليل الملزمة رقم {lecture_id}.\n'
        f'الصفحات: {analysis.pages}\n'
        f'الكلمات التقريبية: {analysis.words}\n'
        f'الكثافة: {analysis.density}\n'
        f'الصعوبة: {analysis.difficulty}\n'
        f'الوقت المتوقع: {analysis.estimated_minutes} دقيقة\n\n'
        f'مخاطر امتحانية:\n{risks}\n\n'
        f'استراتيجية: {analysis.strategy}',
        reply_markup=subjects_keyboard(),
    )
