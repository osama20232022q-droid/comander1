from __future__ import annotations

from aiogram import Router, F
from aiogram.types import FSInputFile, Message

from app.keyboards import demo_keyboard
from app.services.demo_service import run_full_demo
from app.services.user_service import upsert_user
from app.utils.time_utils import human_minutes

router = Router()


@router.message(F.text == '🧪 تجربة الخدمات')
async def demo_home(message: Message) -> None:
    await upsert_user(message.from_user)
    await message.answer(
        '🧪 مركز تجربة الخدمات.\n'
        'اضغط تشغيل تجربة كاملة حتى ينشئ البوت بيانات وهمية آمنة داخل حسابك فقط:\n'
        '- مادة وملزمة وتحليل\n'
        '- جلسات دراسة\n'
        '- أكل وماء\n'
        '- تقرير وانضباط\n'
        '- شهادة HTML\n'
        '- تقييم مستوى\n\n'
        'هذا مخصص للفحص السريع حتى لا تنتظر أسبوعًا كاملًا.',
        reply_markup=demo_keyboard(),
    )


@router.message(F.text == '🧪 تشغيل تجربة كاملة')
async def demo_run(message: Message) -> None:
    user = await upsert_user(message.from_user)
    await message.answer('جاري تشغيل اختبار كامل لكل خدمات البوت...')
    result = await run_full_demo(user)
    report = result['report']
    await message.answer(
        '✅ انتهت التجربة الكاملة.\n\n'
        f'{result["summary"]}\n\n'
        '📊 تقرير اليوم بعد التجربة:\n'
        f'- دراسة صافية: {human_minutes(report["study_minutes"])}\n'
        f'- المخطط: {human_minutes(report["planned_minutes"])}\n'
        f'- Discipline Score: {report["discipline_score"]}/100\n\n'
        'افحص الآن أزرار: 📊 التقارير، 🏅 الشهادات، 📚 المواد، 🍽️ أكل وماء.'
    )
    await message.answer_document(
        FSInputFile(result['certificate_path']),
        caption='🏅 شهادة تجريبية HTML للتأكد من عمل نظام الشهادات.'
    )
