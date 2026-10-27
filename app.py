"""Reviewer-friendly launcher for the Agrinox FastAPI backend."""

from pathlib import Path

import uvicorn

BACKEND_ROOT = Path(__file__).resolve().parent / "backend"


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        app_dir=str(BACKEND_ROOT),
    )
