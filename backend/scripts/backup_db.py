"""Create a consistent snapshot of the SQLite database (safe while the server runs).

Usage (from the backend folder):  python scripts/backup_db.py
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

settings.backup_dir.mkdir(parents=True, exist_ok=True)
target = settings.backup_dir / f"ro_membrane_{datetime.now():%Y%m%d_%H%M%S}.db"
src, dst = sqlite3.connect(settings.database_path), sqlite3.connect(target)
with dst:
    src.backup(dst)
src.close()
dst.close()
print(f"Backup written to {target}")
