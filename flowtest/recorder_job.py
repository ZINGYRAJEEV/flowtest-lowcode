"""
Standalone recorder job — run as:
  python -m flowtest.recorder_job <input.json> <output.json>

Must not be invoked via ProcessPoolExecutor from Streamlit on Windows,
because spawn re-imports app.py and dies on session state.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python -m flowtest.recorder_job <input.json> <output.json>", file=sys.stderr)
        return 2
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    try:
        payload = json.loads(in_path.read_text(encoding="utf-8"))
        from flowtest.recorder import record_browser_session

        result = record_browser_session(
            start_url=payload["start_url"],
            replace_base_url=payload.get("replace_base_url"),
            max_seconds=int(payload.get("max_seconds") or 600),
        )
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:
        err = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "steps": [],
            "events": [],
            "count": 0,
        }
        try:
            out_path.write_text(json.dumps(err, indent=2), encoding="utf-8")
        except Exception:
            pass
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
