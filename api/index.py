"""Vercel serverless entry point.

Vercel's Python runtime serves the ASGI ``app`` exported here for every /api/* request (see vercel.json).
The static client is built from frontend/ and served by Vercel's CDN.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
from app.migrations import migrate  # noqa: E402

# Serverless runtimes may not run ASGI lifespan events, so apply pending migrations at cold start.
# Idempotent, and serialised by an advisory lock on Postgres.
migrate()
