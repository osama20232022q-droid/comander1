from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def temporary_path(*, suffix: str = "", prefix: str = "study_commander_") -> Iterator[Path]:
    """Create a temporary path and always remove it afterwards."""
    fd, raw_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    path = Path(raw_path)
    try:
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
