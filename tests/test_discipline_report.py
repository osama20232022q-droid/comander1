from types import SimpleNamespace

from app.services.discipline_report import (
    calculate_discipline_score,
    calculate_sleep_minutes,
    generate_daily_html,
    generate_weekly_html,
    parse_clock,
)


def test_parse_clock_formats():
    assert parse_clock("3") == "03:00"
    assert parse_clock("0300") == "03:00"
    assert parse_clock("21:30") == "21:30"
    assert parse_clock("25:00") is None


def test_sleep_crosses_midnight():
    assert calculate_sleep_minutes("21:00", "03:00") == 360
    assert calculate_sleep_minutes("03:00", "09:00") == 360


def test_full_discipline_score():
    result = calculate_discipline_score(
        {
            "sleep_minutes": 7 * 60,
            "phone_locked": True,
            "theory_minutes": 90,
            "practical_minutes": 60,
            "mcq_total": 40,
            "mcq_correct": 36,
            "essay_count": 2,
            "review_completed": True,
        }
    )
    assert result.score == 100
    assert result.status == "green"


def test_html_reports_are_self_contained():
    profile = SimpleNamespace(full_name="علي محمد حسن", college="كلية الطب")
    report = SimpleNamespace(
        id=1,
        date_key="2026-07-12",
        sleep_time="21:00",
        wake_time="03:00",
        sleep_minutes=360,
        phone_locked=True,
        theory_minutes=90,
        practical_minutes=60,
        mcq_total=40,
        mcq_correct=30,
        essay_count=2,
        review_completed=True,
        notes="يوم جيد",
        score=90,
        status="green",
    )
    daily = generate_daily_html(profile, report, ["التشريح", "الكيمياء الحياتية"])
    weekly = generate_weekly_html(profile, [report])
    assert "تقرير القيادة والانضباط اليومي" in daily
    assert "تقرير القيادة الأسبوعي" in weekly
    assert "<html" in daily and "<style>" in daily
