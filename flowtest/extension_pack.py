"""Helpers for packaging / downloading the FlowTest Chrome recorder extension."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path


def chrome_extension_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "chrome-extension"


def build_chrome_extension_zip() -> bytes:
    """
    Zip extension files at the archive root so unzipping
    flowtest-chrome-extension.zip yields a folder with manifest.json
    (ready for Chrome → Load unpacked).
    """
    root = chrome_extension_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"Chrome extension folder not found: {root}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            # Put files at zip root (not chrome-extension/...) so Load unpacked works
            # on the extracted folder itself.
            arcname = path.relative_to(root).as_posix()
            zf.write(path, arcname)
    return buf.getvalue()
