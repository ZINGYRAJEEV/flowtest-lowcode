"""Helpers for packaging / downloading the FlowTest Chrome recorder extension."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path


def chrome_extension_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "chrome-extension"


def build_chrome_extension_zip() -> bytes:
    """Zip the chrome-extension folder for Load unpacked after extract."""
    root = chrome_extension_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"Chrome extension folder not found: {root}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            # Keep folder name so unzip creates chrome-extension/
            arcname = Path("chrome-extension") / path.relative_to(root)
            zf.write(path, arcname.as_posix())
    return buf.getvalue()
