"""Serve the built web client (web/dist) from the same origin as the API."""

from __future__ import annotations

import mimetypes
from pathlib import Path

DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def load(url_path: str, root: Path = DIST) -> tuple[bytes, str] | None:
    """Return (body, content_type) for a client file, or None if there is no build."""
    if not root.is_dir():
        return None
    rel = url_path.lstrip("/")
    target = (root / rel).resolve()
    if not rel or not target.is_file() or root.resolve() not in target.parents:
        target = root / "index.html"
        if not target.is_file():
            return None
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return target.read_bytes(), ctype
