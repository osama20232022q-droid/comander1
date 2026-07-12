from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import inspect

from app.config import settings
from app.db import engine, init_db
from app.services.backup import decode_backup_bytes
from app.services.inbound_rate_limit import InboundRateLimiter
from app.services.temp_files import temporary_path


def test_alembic_baseline_creates_schema():
    init_db()
    tables = set(inspect(engine).get_table_names())
    assert "alembic_version" in tables
    assert "users" in tables
    assert "daily_discipline_reports" in tables
    assert "ai_usage_daily" in tables


def test_temporary_path_is_removed():
    with temporary_path(suffix=".txt") as path:
        path.write_text("hello", encoding="utf-8")
        assert path.exists()
        saved = Path(path)
    assert not saved.exists()


def test_encrypted_backup_decoding():
    old_key = settings.backup_encryption_key
    key = Fernet.generate_key().decode("utf-8")
    object.__setattr__(settings, "backup_encryption_key", key)
    try:
        payload = {"schema": "study_commander_v8", "tables": {}}
        encrypted = Fernet(key.encode("utf-8")).encrypt(json.dumps(payload).encode("utf-8"))
        assert decode_backup_bytes(encrypted, "backup.json.enc") == payload
    finally:
        object.__setattr__(settings, "backup_encryption_key", old_key)


@pytest.mark.asyncio
async def test_inbound_limiter_blocks_fast_flood():
    old_count = settings.inbound_limit_count
    old_window = settings.inbound_limit_window_seconds
    old_block = settings.inbound_block_seconds
    object.__setattr__(settings, "inbound_limit_count", 2)
    object.__setattr__(settings, "inbound_limit_window_seconds", 30)
    object.__setattr__(settings, "inbound_block_seconds", 10)
    try:
        limiter = InboundRateLimiter()
        assert (await limiter.check(100))[0] is True
        assert (await limiter.check(100))[0] is True
        allowed, wait = await limiter.check(100)
        assert allowed is False
        assert wait >= 1
    finally:
        object.__setattr__(settings, "inbound_limit_count", old_count)
        object.__setattr__(settings, "inbound_limit_window_seconds", old_window)
        object.__setattr__(settings, "inbound_block_seconds", old_block)
