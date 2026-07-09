from __future__ import annotations


def discipline_score(
    planned_minutes: int,
    study_minutes: int,
    phone_events: int = 0,
    missed_tasks: int = 0,
    sleep_ok: bool = True,
    reports_done: bool = True,
) -> int:
    score = 100
    if planned_minutes > 0:
        completion = min(1.0, study_minutes / planned_minutes)
        score -= int((1.0 - completion) * 45)
    else:
        score -= 20
    score -= min(25, phone_events * 8)
    score -= min(20, missed_tasks * 5)
    if not sleep_ok:
        score -= 10
    if not reports_done:
        score -= 10
    return max(0, min(100, score))


def classify_excuse(text: str) -> tuple[str, str]:
    value = text.strip().lower()
    accepted = ['مرض', 'مريض', 'طوارئ', 'مستشفى', 'اهل', 'دوام', 'امتحان', 'صلاة']
    partial = ['تعب', 'نعاس', 'صداع', 'ضيوف', 'مراجعة', 'اكل']
    rejected = ['تيك', 'تكتك', 'انستا', 'يوتيوب', 'سوشال', 'ملل', 'ماكو واهس']
    if any(k in value for k in accepted):
        return 'مقبول', 'العذر مقبول، يعاد توزيع الخطة بلا عقوبة.'
    if any(k in value for k in rejected):
        return 'غير مقبول', 'هذا تسويف واضح. العقوبة: جلسة MCQ إضافية 30 دقيقة.'
    if any(k in value for k in partial):
        return 'جزئي', 'العذر جزئي. نخفف الخطة لكن نسجل تنبيه انضباط.'
    return 'غير محسوم', 'البوت يحتاج توضيحًا أدق للحكم على العذر.'
