from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from app.config import settings


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        await db.execute('PRAGMA foreign_keys = ON')
        try:
            yield db
            await db.commit()
        finally:
            await db.close()

    async def migrate(self) -> None:
        async with self.connect() as conn:
            await conn.executescript(SCHEMA)
            await self._safe_alter(conn, 'profiles', 'study_level', "TEXT DEFAULT 'متوسط'")
            await self._safe_alter(conn, 'profiles', 'energy_pattern', "TEXT DEFAULT 'غير محدد'")
            await self._safe_alter(conn, 'profiles', 'food_goal_json', "TEXT DEFAULT '{}'")
            await self._safe_alter(conn, 'profiles', 'phone_risk_window', "TEXT DEFAULT '22:30-00:30'")
            await self._safe_alter(conn, 'users', 'last_seen_at', 'TEXT')
            await self._safe_alter(conn, 'users', 'created_by_admin_id', 'INTEGER')

    async def _safe_alter(self, conn: aiosqlite.Connection, table: str, column: str, spec: str) -> None:
        rows = await conn.execute_fetchall(f'PRAGMA table_info({table})')
        if any(row['name'] == column for row in rows):
            return
        try:
            await conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {spec}')
        except aiosqlite.OperationalError:
            pass


db = Database(settings.database_path)


def dt_iso(value: datetime | None = None) -> str:
    value = value or datetime.now(settings.timezone)
    return value.isoformat(timespec='seconds')


def d_iso(value: date | None = None) -> str:
    value = value or datetime.now(settings.timezone).date()
    return value.isoformat()


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def loads(data: str | None, default: Any = None) -> Any:
    if not data:
        return default
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return default


SCHEMA = r'''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'student',
    is_blocked INTEGER NOT NULL DEFAULT 0,
    created_by_admin_id INTEGER,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY,
    display_name TEXT,
    age INTEGER,
    height_cm REAL,
    weight_kg REAL,
    city TEXT DEFAULT 'Iraq',
    timezone TEXT DEFAULT 'Asia/Baghdad',
    sleep_time TEXT DEFAULT '22:00',
    wake_time TEXT DEFAULT '04:30',
    pomodoro_focus INTEGER DEFAULT 50,
    pomodoro_break INTEGER DEFAULT 10,
    long_break_every INTEGER DEFAULT 2,
    discipline_mode TEXT DEFAULT 'صارم',
    study_level TEXT DEFAULT 'متوسط',
    energy_pattern TEXT DEFAULT 'غير محدد',
    food_goal_json TEXT DEFAULT '{}',
    phone_risk_window TEXT DEFAULT '22:30-00:30',
    prayer_times_json TEXT DEFAULT '{}',
    updated_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    paid INTEGER NOT NULL DEFAULT 1,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    note TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscription_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    requested_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    exam_date TEXT,
    level TEXT DEFAULT 'متوسط',
    has_practical INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lectures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    pages INTEGER DEFAULT 0,
    difficulty TEXT DEFAULT 'متوسطة',
    status TEXT DEFAULT 'pending',
    estimated_minutes INTEGER DEFAULT 60,
    analysis_json TEXT DEFAULT '{}',
    file_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject_id INTEGER,
    lecture_id INTEGER,
    title TEXT NOT NULL,
    planned_start TEXT,
    planned_end TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY(lecture_id) REFERENCES lectures(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject_id INTEGER,
    lecture_id INTEGER,
    session_type TEXT DEFAULT 'study',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_minutes INTEGER DEFAULT 0,
    focus_score INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY(lecture_id) REFERENCES lectures(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS active_timers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    focus_minutes INTEGER NOT NULL,
    break_minutes INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    notified INTEGER DEFAULT 0,
    cycles_done INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS food_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    logged_at TEXT NOT NULL,
    item TEXT NOT NULL,
    calories_min INTEGER DEFAULT 0,
    calories_max INTEGER DEFAULT 0,
    note TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS water_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    logged_at TEXT NOT NULL,
    ml INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sleep_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sleep_date TEXT NOT NULL,
    slept_at TEXT,
    woke_at TEXT,
    hours REAL,
    quality INTEGER,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    study_minutes INTEGER DEFAULT 0,
    planned_minutes INTEGER DEFAULT 0,
    discipline_score INTEGER DEFAULT 0,
    summary TEXT,
    delays_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, report_date),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS routine_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    sleep_time TEXT NOT NULL,
    wake_time TEXT NOT NULL,
    goal TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    html_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS discipline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_at TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    reason TEXT,
    action TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    academic_level TEXT,
    discipline_level TEXT,
    energy_pattern TEXT,
    summary TEXT,
    data_json TEXT DEFAULT '{}',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS demo_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    summary TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_tg ON users(tg_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id, status, end_at);
CREATE INDEX IF NOT EXISTS idx_subjects_user ON subjects(user_id);
CREATE INDEX IF NOT EXISTS idx_lectures_subject ON lectures(subject_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_started ON sessions(user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_food_user_time ON food_logs(user_id, logged_at);
CREATE INDEX IF NOT EXISTS idx_water_user_time ON water_logs(user_id, logged_at);
CREATE INDEX IF NOT EXISTS idx_discipline_user_time ON discipline_events(user_id, event_at);
'''
