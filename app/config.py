from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _split_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "").strip()
    admin_ids: set[int] | None = None
    timezone: str = os.getenv("TIMEZONE", "Asia/Baghdad").strip() or "Asia/Baghdad"
    signature: str = os.getenv("BOT_SIGNATURE", "Study Commander Bot").strip() or "Study Commander Bot"
    environment: str = os.getenv("ENVIRONMENT", "production").strip().lower() or "production"

    database_url: str = os.getenv("DATABASE_URL", "").strip()
    database_path: str = os.getenv("DATABASE_PATH", "/data/study_commander.sqlite3").strip()

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"

    backup_keep_days: int = _env_int("BACKUP_KEEP_DAYS", 30, minimum=1, maximum=3650)
    backup_encryption_key: str = os.getenv("BACKUP_ENCRYPTION_KEY", "").strip()
    require_encrypted_backups: bool = _env_bool("REQUIRE_ENCRYPTED_BACKUPS", False)

    # Telegram network settings. The default is intentionally sequential to keep
    # multi-step flows ordered and prevent context.user_data races.
    bot_concurrent_updates: int = _env_int("BOT_CONCURRENT_UPDATES", 1, minimum=1, maximum=128)
    tg_connection_pool_size: int = _env_int("TG_CONNECTION_POOL_SIZE", 16, minimum=4, maximum=256)
    tg_pool_timeout: int = _env_int("TG_POOL_TIMEOUT", 20, minimum=5, maximum=120)
    tg_read_timeout: int = _env_int("TG_READ_TIMEOUT", 30, minimum=5, maximum=180)
    tg_write_timeout: int = _env_int("TG_WRITE_TIMEOUT", 30, minimum=5, maximum=180)

    # Inbound abuse controls.
    inbound_limit_count: int = _env_int("INBOUND_LIMIT_COUNT", 18, minimum=3, maximum=300)
    inbound_limit_window_seconds: int = _env_int("INBOUND_LIMIT_WINDOW_SECONDS", 20, minimum=5, maximum=3600)
    inbound_block_seconds: int = _env_int("INBOUND_BLOCK_SECONDS", 20, minimum=5, maximum=3600)

    # Upload controls used before downloading from Telegram.
    ai_max_file_bytes: int = _env_int(
        "AI_MAX_FILE_BYTES", 8 * 1024 * 1024, minimum=128 * 1024, maximum=50 * 1024 * 1024
    )
    prayer_job_interval: int = _env_int("PRAYER_JOB_INTERVAL", 60, minimum=30, maximum=3600)

    def __post_init__(self) -> None:
        object.__setattr__(self, "admin_ids", _split_admin_ids(os.getenv("ADMIN_IDS", "")))
        if not self.database_url:
            db_path = Path(self.database_path)
            if not db_path.is_absolute():
                db_path = Path.cwd() / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
