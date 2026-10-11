"""Create or upgrade the local SQLite database and load the starter dataset.

Usage (from the backend folder):  python scripts/init_db.py
Safe to run repeatedly: only migrations not yet applied are executed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.migrations import migrate  # noqa: E402

version = migrate()
print(f"Database ready at {settings.database_path} (schema version {version}).")
