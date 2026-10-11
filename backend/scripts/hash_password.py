"""Generate a bcrypt hash for RO_ADMIN_PASSWORD_HASH.

Usage (from the backend folder):  python scripts/hash_password.py
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security import hash_password  # noqa: E402

pw = getpass.getpass("New admin password: ")
if len(pw) < 10:
    sys.exit("Use at least 10 characters.")
if pw != getpass.getpass("Repeat password: "):
    sys.exit("Passwords do not match.")
print("\nAdd this line to backend/.env (and remove RO_ADMIN_PASSWORD):\n")
print(f"RO_ADMIN_PASSWORD_HASH={hash_password(pw)}")
