"""
Optional local research dashboard.

Importing this package does not require the ``web`` extra; calling
``create_app()`` does. Install with::

    pip install -e ".[web]"
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

__all__ = ["create_app"]


def create_app(data_dir: Optional[Path] = None, runs_dir: Optional[Path] = None):
    """Create the FastAPI app, with a friendly error if the extra is missing."""
    try:
        from .app import create_app as _create_app
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            "The browser dashboard requires optional dependencies. "
            'Install them with: pip install -e ".[web]"'
        ) from exc
    return _create_app(data_dir=data_dir, runs_dir=runs_dir)
