"""Vercel's FastAPI entrypoint. Keep backend code in its existing package."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402
