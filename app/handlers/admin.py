from __future__ import annotations

from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import settings
from app.keyboards import admin_keyboard, back_keyboard, paid_confirmation_keyboard, subscription_plan_keyboard
from app.services.access_service import admin_stats, grant_subscription, list_users_with_subscriptions, revoke_subscription
from app.services.user_service import block_user, resolve_user, upsert_user
from app.states import AdminStates

router = Router()


def _is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_ids


def _require_admin(message: Message) -> bool:
    return bool(message.from_user and _is_admin(message.from_user.id))


@router.message(F.text == '🧑‍✈️ الأدمن')
async def admin_home(message: Message) -> None:
    await upsert_user(message.from_user)
    if not _require_admin(message):
        await message.answer('هذه اللوحة للمدير فقط.')
        return
    stats = await admin_stats()
    await message.answer(
        '🧑‍✈️ Admin Panel\n'
        f'- المستخدمون: {stats["users"]}\n'
        f'- الاشتراكات الفعالة: {stats["active_subscriptions"]}\n'
        f'- الاشتراكات المنتهية: {stats["expired_subscriptions"]}\n'
        f'- طلبات الاشتراك المعلقة: {stats["pending_requests"]}\n'
        f'- المحظورون: {stats["blocked"]}\n\n'
        'اختر أمرًا من لوحة الأدمن.',
        reply_markup=admin_keyboard(),
    )


@router.message(F.text == '📊 إحصائيات الأدمن')
async def admin_statistics(message: Message) -> None:
    if not _require_admin(message):
        return
    stats = await admin_stats()
    await message.answer(
        '📊 إحصائيات النظام:\n'
        f'- كل المستخدمين: {stats["users"]}\n'
        f'- فعالون باشتراك: {stats["active_subscriptions"]}\n'
        f'- منتهية اشتراكاتهم: {stats["expired_subscriptions"]}\n'
        f'- طلبات اشتراك معلقة: {stats["pending_requests"]}\n'
        f'- محظورون: {stats["blocked"]}'
    )


@router.message(F.text == '🔐 تفعيل اشتراك')
async def sub_start(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    await state.set_state(AdminStates.waiting_sub_identifier)
    await message.answer(
        'اكتب Telegram ID الرقمي أو username للطالب.\n'
        'إذا الطالب لم يدخل للبوت بعد، استخدم رقمه فقط حتى ينفتح له عند أول /start.',
        reply_markup=back_keyboard(),
    )


@router.message(AdminStates.waiting_sub_identifier)
async def sub_identifier(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    ident = message.text.strip()
    target = await resolve_user(ident, created_by_admin_id=message.from_user.id)
    if not target:
        await message.answer('لم أجد المستخدم. إذا تريد إضافة شخص جديد استخدم Telegram numeric ID فقط.')
        return
    await state.update_data(identifier=ident, target_tg_id=target['tg_id'], target_name=target.get('full_name') or target.get('username') or str(target['tg_id']))
    await state.set_state(AdminStates.waiting_sub_plan)
    await message.answer(
        f'المستخدم: {target.get("full_name") or "-"} | @{target.get("username") or "-"} | <code>{target["tg_id"]}</code>\n'
        'اختر مدة الاشتراك:',
        reply_markup=subscription_plan_keyboard(),
    )


@router.message(AdminStates.waiting_sub_plan)
async def sub_plan(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    plan = message.text.strip()
    if plan not in {'شهري', '٣ أشهر', '٦ أشهر', 'سنوي', '٧ أيام تجربة'}:
        await message.answer('اختر مدة من الأزرار فقط.')
        return
    await state.update_data(plan=plan)
    await state.set_state(AdminStates.waiting_sub_paid)
    data = await state.get_data()
    await message.answer(
        f'تأكيد الدفع:\n'
        f'- الطالب: {data["target_name"]}\n'
        f'- المدة: {plan}\n\n'
        'هل الطالب دفع؟ إذا نعم يفتح البوت فورًا.',
        reply_markup=paid_confirmation_keyboard(),
    )


@router.message(AdminStates.waiting_sub_paid)
async def sub_paid(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    data = await state.get_data()
    if message.text == '❌ لم يدفع':
        await state.clear()
        await message.answer('لم يتم فتح الاشتراك. الحساب يبقى مقفلًا.', reply_markup=admin_keyboard())
        return
    if message.text != '✅ دفع':
        await message.answer('اختر: ✅ دفع أو ❌ لم يدفع.')
        return

    result = await grant_subscription(
        data['identifier'],
        data['plan'],
        created_by_tg_id=message.from_user.id,
        paid=True,
        note='Activated from admin panel after payment confirmation',
    )
    await state.clear()
    if not result:
        await message.answer('فشل التفعيل: لم أجد المستخدم.', reply_markup=admin_keyboard())
        return
    end: datetime = result['end']
    await message.answer(
        '✅ تم فتح الاشتراك.\n'
        f'- الطالب: {result["user"].get("full_name") or result["user"]["tg_id"]}\n'
        f'- الخطة: {data["plan"]}\n'
        f'- ينتهي: {end.strftime("%Y-%m-%d %H:%M")}\n\n'
        'من الآن يقدر يستخدم كل خدمات البوت.',
        reply_markup=admin_keyboard(),
    )


@router.message(F.text == '⛔️ إيقاف اشتراك')
async def revoke_start(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    await state.set_state(AdminStates.waiting_revoke_identifier)
    await message.answer('اكتب Telegram ID أو username لإيقاف اشتراكه.', reply_markup=back_keyboard())


@router.message(AdminStates.waiting_revoke_identifier)
async def revoke_done(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    ok = await revoke_subscription(message.text.strip())
    await state.clear()
    await message.answer('تم إيقاف الاشتراك.' if ok else 'لم أجد المستخدم.', reply_markup=admin_keyboard())


@router.message(F.text == 'حظر')
async def block_start(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    await state.set_state(AdminStates.waiting_block_identifier)
    await message.answer('اكتب Telegram ID أو username للحظر.', reply_markup=back_keyboard())


@router.message(AdminStates.waiting_block_identifier)
async def block_done(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    ok = await block_user(message.text.strip(), True)
    await state.clear()
    await message.answer('تم الحظر.' if ok else 'لم أجد هذا المستخدم.', reply_markup=admin_keyboard())


@router.message(F.text == 'إلغاء حظر')
async def unblock_start(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    await state.set_state(AdminStates.waiting_unblock_identifier)
    await message.answer('اكتب Telegram ID أو username لإلغاء الحظر.', reply_markup=back_keyboard())


@router.message(AdminStates.waiting_unblock_identifier)
async def unblock_done(message: Message, state: FSMContext) -> None:
    if not _require_admin(message):
        return
    ok = await block_user(message.text.strip(), False)
    await state.clear()
    await message.answer('تم إلغاء الحظر.' if ok else 'لم أجد هذا المستخدم.', reply_markup=admin_keyboard())


@router.message(F.text == 'قائمة المستخدمين')
async def user_list(message: Message) -> None:
    if not _require_admin(message):
        return
    rows = await list_users_with_subscriptions(limit=30)
    lines = ['آخر المستخدمين:']
    for r in rows:
        sub = 'ACTIVE' if r.get('sub_active') else 'LOCKED'
        sub_end = r.get('sub_end') or '-'
        lines.append(
            f'- <code>{r["tg_id"]}</code> @{r["username"] or "-"} | {r["full_name"] or "-"} | {sub} | {r.get("sub_plan") or "-"} | {sub_end} | blocked={r["is_blocked"]}'
        )
    await message.answer('\n'.join(lines))
