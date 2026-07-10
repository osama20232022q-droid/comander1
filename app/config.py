from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _split_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "").strip()
    admin_ids: set[int] = None  # type: ignore
    timezone: str = os.getenv("TIMEZONE", "Asia/Baghdad").strip() or "Asia/Baghdad"
    signature: str = os.getenv("BOT_SIGNATURE", "Study Commander Bot").strip()
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    database_path: str = os.getenv("DATABASE_PATH", "/data/study_commander.sqlite3").strip()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    backup_keep_days: int = int(os.getenv("BACKUP_KEEP_DAYS", "30") or "30")

    def __post_init__(self):
        object.__setattr__(self, "admin_ids", _split_admin_ids(os.getenv("ADMIN_IDS", "")))
        if self.database_url:
            return
        db_path = Path(self.database_path)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
