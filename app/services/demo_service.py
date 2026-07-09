from __future__ import annotations

from datetime import timedelta

from app.db import db, dt_iso, dumps
from app.services.report_service import daily_report, weekly_minutes
from app.utils.certificates import CertificateData, render_certificate
from app.utils.scoring import discipline_score
from app.utils.time_utils import now, today, week_bounds


async def run_full_demo(user: dict) -> dict:
    user_id = user['id']
    created = now()
    summary_lines: list[str] = []

    async with db.connect() as conn:
        cur = await conn.execute(
            '''INSERT INTO subjects(user_id,name,exam_date,level,has_practical,created_at)
               VALUES(?,?,?,?,?,?)''',
            (user_id, 'DEMO Anatomy', (today() + timedelta(days=30)).isoformat(), 'متوسط', 1, dt_iso()),
        )
        subject_id = int(cur.lastrowid)
        summary_lines.append('تم إنشاء مادة تجريبية.')

        analysis = {
            'pages': 11,
            'density': 'متوسطة',
            'difficulty': 'متوسطة',
            'estimated_minutes': 140,
            'strategy': 'قراءة عناوين + Key points + MCQ + Short essay',
            'key_risks': ['Definitions', 'Comparisons', 'Numbers', 'Practical images'],
        }
        cur = await conn.execute(
            '''INSERT INTO lectures(subject_id,title,pages,difficulty,status,estimated_minutes,analysis_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)''',
            (subject_id, 'DEMO Introduction.pdf', 11, 'متوسطة', 'done', 140, dumps(analysis), dt_iso()),
        )
        lecture_id = int(cur.lastrowid)
        summary_lines.append('تم إنشاء ملزمة تجريبية وتحليلها.')

        for days_ago, mins, focus in [(0, 90, 4), (1, 70, 3), (2, 100, 5), (4, 50, 3)]:
            start = created - timedelta(days=days_ago, hours=2)
            end = start + timedelta(minutes=mins)
            await conn.execute(
                '''INSERT INTO sessions(user_id,subject_id,lecture_id,session_type,started_at,ended_at,duration_minutes,focus_score,notes,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (user_id, subject_id, lecture_id, 'focus', dt_iso(start), dt_iso(end), mins, focus, 'demo_session', dt_iso(start)),
            )
        summary_lines.append('تم إنشاء جلسات دراسة تجريبية للأسبوع الحالي.')

        await conn.execute(
            '''INSERT INTO tasks(user_id,subject_id,lecture_id,title,planned_start,planned_end,status,created_at)
               VALUES(?,?,?,?,?,?,?,?)''',
            (user_id, subject_id, lecture_id, 'DEMO Task: Anatomy MCQ review', dt_iso(created), dt_iso(created + timedelta(minutes=60)), 'done', dt_iso()),
        )

        await conn.execute(
            '''INSERT INTO food_logs(user_id,logged_at,item,calories_min,calories_max,note)
               VALUES(?,?,?,?,?,?)''',
            (user_id, dt_iso(), 'DEMO: تمن + دجاج + شاي', 550, 780, 'وجبة متوسطة/ثقيلة؛ بعدها مراجعة أو مشي.'),
        )
        await conn.execute('INSERT INTO water_logs(user_id,logged_at,ml) VALUES(?,?,?)', (user_id, dt_iso(), 500))
        summary_lines.append('تم تسجيل أكل وماء تجريبي.')

        await conn.execute(
            '''INSERT INTO discipline_events(user_id,event_at,category,severity,reason,action)
               VALUES(?,?,?,?,?,?)''',
            (user_id, dt_iso(), 'phone', 'medium', 'DEMO TikTok delay', '30 دقيقة MCQ إضافية'),
        )
        summary_lines.append('تم تسجيل مخالفة تجريبية حتى تظهر بالتقارير.')

        await conn.execute(
            '''INSERT INTO routine_experiments(user_id,name,start_date,end_date,sleep_time,wake_time,goal,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)''',
            (user_id, 'DEMO Morning Routine Trial', today().isoformat(), (today() + timedelta(days=6)).isoformat(), '21:30', '04:30', 'اختبار نظام صباحي', 'active', dt_iso()),
        )
        summary_lines.append('تم إنشاء تجربة نظام صباحي.')

        data = await conn.execute_fetchall(
            'SELECT COALESCE(SUM(duration_minutes),0) AS study_minutes FROM sessions WHERE user_id=? AND started_at LIKE ?',
            (user_id, f'{today().isoformat()}%'),
        )
        score = discipline_score(240, int(data[0]['study_minutes'] or 0), phone_events=1, missed_tasks=0)
        await conn.execute(
            '''INSERT INTO reports(user_id,report_date,study_minutes,planned_minutes,discipline_score,summary,delays_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id,report_date) DO UPDATE SET
               study_minutes=excluded.study_minutes,
               planned_minutes=excluded.planned_minutes,
               discipline_score=excluded.discipline_score,
               summary=excluded.summary,
               delays_json=excluded.delays_json''',
            (user_id, today().isoformat(), int(data[0]['study_minutes'] or 0), 240, score, 'DEMO report generated', dumps([]), dt_iso()),
        )

        await conn.execute(
            '''INSERT INTO student_evaluations(user_id,created_at,academic_level,discipline_level,energy_pattern,summary,data_json)
               VALUES(?,?,?,?,?,?,?)''',
            (user_id, dt_iso(), 'متوسط', 'Improving', 'صباحي محتمل', 'تقييم تجريبي بعد أول شهادة/تقرير.', dumps({'demo': True})),
        )

    start_week, end_week = week_bounds()
    daily = await weekly_minutes(user_id, start_week, end_week)
    report = await daily_report(user_id, today())
    cert_data = CertificateData(
        student_name=user.get('full_name') or 'Student',
        week_start=start_week,
        week_end=end_week,
        study_hours=sum(daily.values()) / 60,
        sessions=sum(1 for value in daily.values() if value > 0),
        subjects_done=['DEMO Anatomy'],
        discipline_score=report['discipline_score'],
        daily_minutes=daily,
    )
    cert_path = render_certificate(cert_data)

    async with db.connect() as conn:
        await conn.execute(
            'INSERT INTO certificates(user_id,week_start,week_end,html_path,created_at) VALUES(?,?,?,?,?)',
            (user_id, start_week.isoformat(), end_week.isoformat(), str(cert_path), dt_iso()),
        )
        await conn.execute(
            'INSERT INTO demo_runs(user_id,created_at,summary) VALUES(?,?,?)',
            (user_id, dt_iso(), '\n'.join(summary_lines)),
        )

    return {
        'summary': '\n'.join(f'- {line}' for line in summary_lines),
        'certificate_path': cert_path,
        'report': report,
    }
