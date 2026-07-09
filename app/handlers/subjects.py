from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import LEVELS
from app.keyboards import back_keyboard, subjects_keyboard
from app.services.planner import create_today_tasks, plan_overview
from app.services.subject_service import add_lecture, add_subject, list_lectures, list_subjects
from app.services.user_service import upsert_user
from app.states import SubjectStates

router = Router()


@router.message(F.text == '📚 المواد')
async def subjects_home(message: Message) -> None:
    await upsert_user(message.from_user)
    await message.answer('📚 لوحة المواد والملازم:', reply_markup=subjects_keyboard())


@router.message(F.text == '➕ إضافة مادة')
async def add_subject_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SubjectStates.waiting_name)
    await message.answer('اكتب اسم المادة. مثال: Anatomy / Histology / Biochemistry', reply_markup=back_keyboard())


@router.message(SubjectStates.waiting_name)
async def add_subject_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(SubjectStates.waiting_exam_date)
    await message.answer('موعد الامتحان؟ اكتب YYYY-MM-DD أو اكتب: لا')


@router.message(SubjectStates.waiting_exam_date)
async def add_subject_exam(message: Message, state: FSMContext) -> None:
    exam = None if message.text.strip() in ('لا', '-', 'none') else message.text.strip()
    await state.update_data(exam_date=exam)
    await state.set_state(SubjectStates.waiting_level)
    await message.answer('مستواك بالمادة؟ اختر/اكتب: ضعيف، متوسط، جيد، قوي')


@router.message(SubjectStates.waiting_level)
async def add_subject_level(message: Message, state: FSMContext) -> None:
    level = message.text.strip()
    if level not in LEVELS:
        await message.answer('اكتب واحد من: ضعيف، متوسط، جيد، قوي')
        return
    await state.update_data(level=level)
    await state.set_state(SubjectStates.waiting_practical)
    await message.answer('بيها عملي؟ اكتب نعم أو لا')


@router.message(SubjectStates.waiting_practical)
async def add_subject_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user = await upsert_user(message.from_user)
    has_practical = message.text.strip().lower() in ('نعم', 'اي', 'yes', 'y')
    sid = await add_subject(user['id'], data['name'], data['exam_date'], data['level'], has_practical)
    await state.clear()
    await message.answer(f'✅ تمت إضافة المادة رقم {sid}: {data["name"]}', reply_markup=subjects_keyboard())


@router.message(F.text == '📖 عرض المواد')
async def show_subjects(message: Message) -> None:
    user = await upsert_user(message.from_user)
    subjects = await list_subjects(user['id'])
    lectures = await list_lectures(user['id'])
    if not subjects:
        await message.answer('لا توجد مواد بعد. اضغط ➕ إضافة مادة.')
        return
    lines = ['📚 موادك:']
    for s in subjects:
        lec_count = sum(1 for l in lectures if l['subject_id'] == s['id'])
        lines.append(f'{s["id"]}. {s["name"]} | مستوى: {s["level"]} | امتحان: {s["exam_date"] or "غير محدد"} | ملازم: {lec_count}')
    await message.answer('\n'.join(lines))


@router.message(F.text == '➕ إضافة ملزمة')
async def add_lecture_start(message: Message, state: FSMContext) -> None:
    user = await upsert_user(message.from_user)
    subjects = await list_subjects(user['id'])
    if not subjects:
        await message.answer('أضف مادة أولًا.')
        return
    await state.set_state(SubjectStates.waiting_lecture_subject)
    await message.answer('اكتب رقم المادة التي تريد إضافة ملزمة لها:\n' + '\n'.join(f'{s["id"]}. {s["name"]}' for s in subjects), reply_markup=back_keyboard())


@router.message(SubjectStates.waiting_lecture_subject)
async def add_lecture_subject(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer('اكتب رقم المادة فقط.')
        return
    await state.update_data(subject_id=int(message.text.strip()))
    await state.set_state(SubjectStates.waiting_lecture_title)
    await message.answer('اكتب عنوان الملزمة.')


@router.message(SubjectStates.waiting_lecture_title)
async def add_lecture_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(SubjectStates.waiting_lecture_pages)
    await message.answer('عدد الصفحات؟')


@router.message(SubjectStates.waiting_lecture_pages)
async def add_lecture_pages(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer('اكتب رقم الصفحات فقط.')
        return
    data = await state.get_data()
    pages = int(message.text.strip())
    est = max(25, pages * 7)
    lid = await add_lecture(data['subject_id'], data['title'], pages, 'متوسطة', est)
    await state.clear()
    await message.answer(f'✅ تمت إضافة الملزمة رقم {lid}. الوقت التقريبي: {est} دقيقة.', reply_markup=subjects_keyboard())


@router.message(F.text == '🧠 حلل الخطة')
async def analyze_plan(message: Message) -> None:
    user = await upsert_user(message.from_user)
    await message.answer(await plan_overview(user['id']))


@router.message(F.text == '📋 يومي')
async def my_day(message: Message) -> None:
    user = await upsert_user(message.from_user)
    tasks = await create_today_tasks(user['id'], available_minutes=300)
    if not tasks:
        await message.answer('لا توجد مهام جاهزة. أضف ملازم أولًا.')
        return
    lines = ['📋 أوامر اليوم:']
    for t in tasks:
        lines.append(f'- {t["start"]}-{t["end"]}: {t["title"]}')
    lines.append('\nبعد كل جلستين: مشي إجباري 7 دقائق + ماء.')
    await message.answer('\n'.join(lines))
