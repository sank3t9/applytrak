"""Vercel serverless entry point.

Vercel's Python runtime looks for a module-level ASGI/WSGI `app` in files under
api/. The package lives in src/, which isn't on the path in that environment,
so it's added here before importing.

Deployments must set RUN_SCHEDULER=false (no long-lived process exists to run
it) and EXPOSE_ADMIN_ENDPOINTS=false (visitors must not trigger pipeline runs).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from applytrak.api.main import app  # noqa: E402

__all__ = ["app"]
