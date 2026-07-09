from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_admin_ids(value: str | None) -> set[int]:
    if not value:
        return set()
    result: set[int] = set()
    for part in value.split(','):
        part = part.strip()
        if part.isdigit():
            result.add(int(part))
    return result


def _path_from_env(name: str, default: str) -> Path:
    value = os.getenv(name, default)
    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv('BOT_TOKEN', '')
    admin_ids: set[int] = None  # type: ignore[assignment]
    timezone_name: str = os.getenv('TIMEZONE', 'Asia/Baghdad')
    database_path: Path = _path_from_env('DATABASE_PATH', 'data/study_commander.sqlite3')
    uploads_dir: Path = _path_from_env('UPLOADS_DIR', 'storage/uploads')
    certificates_dir: Path = _path_from_env('CERTIFICATES_DIR', 'storage/certificates')
    openai_api_key: str | None = os.getenv('OPENAI_API_KEY') or None
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    bot_signature: str = os.getenv('BOT_SIGNATURE', 'Study Commander Bot')
    subscription_grace_hours: int = int(os.getenv('SUBSCRIPTION_GRACE_HOURS', '0') or 0)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'admin_ids', _parse_admin_ids(os.getenv('ADMIN_IDS')))
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.certificates_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)


settings = Settings()
