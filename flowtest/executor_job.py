"""
Standalone test execution job for Streamlit-safe subprocess runs.
  python -m flowtest.executor_job <input.json> <output.json>
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python -m flowtest.executor_job <input.json> <output.json>", file=sys.stderr)
        return 2
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    try:
        payload = json.loads(in_path.read_text(encoding="utf-8"))
        from flowtest.executor import _execute_payload

        result = _execute_payload(payload)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:
        err = {"error": str(exc), "traceback": traceback.format_exc(), "status": "ERROR"}
        try:
            out_path.write_text(json.dumps(err, indent=2), encoding="utf-8")
        except Exception:
            pass
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
