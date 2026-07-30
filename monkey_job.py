"""
Standalone monkey assess/execute jobs for Streamlit-safe subprocess runs.
  python -m monkey_job assess <input.json> <output.json>
  python -m monkey_job execute <input.json> <output.json>
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: python -m monkey_job <assess|execute> <input.json> <output.json>", file=sys.stderr)
        return 2
    mode = sys.argv[1]
    in_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3])
    try:
        payload = json.loads(in_path.read_text(encoding="utf-8"))
        if mode == "assess":
            from monkey_engine import assess_webpage

            result = assess_webpage(
                payload["url"],
                timeout_ms=int(payload.get("timeout_ms") or 30000),
                headless=bool(payload.get("headless", True)),
            )
            out_path.write_text(json.dumps(result.to_dict()), encoding="utf-8")
            return 0
        if mode == "execute":
            from dataclasses import asdict

            from monkey_engine import MonkeyStep, MonkeyTestCase, execute_test_case

            tc_data = payload["test_case"]
            steps = [MonkeyStep(**s) for s in tc_data["steps"]]
            tc = MonkeyTestCase(
                id=tc_data["id"],
                name=tc_data["name"],
                description=tc_data.get("description", ""),
                priority=tc_data.get("priority", "Medium"),
                steps=steps,
                tags=tc_data.get("tags", []),
                enabled=tc_data.get("enabled", True),
                objective=tc_data.get("objective", ""),
                coverage=tc_data.get("coverage", ""),
                expected_result=tc_data.get("expected_result", ""),
                rationale=tc_data.get("rationale", ""),
            )
            result = execute_test_case(
                tc,
                base_url=payload["base_url"],
                timeout_ms=int(payload.get("timeout_ms") or 15000),
                headless=bool(payload.get("headless", True)),
                stop_on_fail=bool(payload.get("stop_on_fail", False)),
            )
            out_path.write_text(json.dumps(asdict(result)), encoding="utf-8")
            return 0
        raise RuntimeError(f"Unknown mode: {mode}")
    except Exception as exc:
        err = {"error": str(exc), "traceback": traceback.format_exc()}
        try:
            out_path.write_text(json.dumps(err), encoding="utf-8")
        except Exception:
            pass
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
