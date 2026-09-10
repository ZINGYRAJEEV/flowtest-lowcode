"""
Allure 2–compatible results + self-contained HTML report (no Java CLI required).

Writes under flowtest_data/allure-results/<run_id>/ by default:
  - {uuid}-result.json
  - attachments/ (screenshots)
  - report.html (timeline-style suite/test/step view)
  - report.zip (optional via zip_report)
"""

from __future__ import annotations

import base64
import html
import json
import re
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flowtest.models import TestRun
from flowtest.storage import DATA_DIR

ALLURE_ROOT = DATA_DIR / "allure-results"


def _ms_now() -> int:
    return int(time.time() * 1000)


def _parse_ts_ms(value: str) -> int:
    if not value:
        return _ms_now()
    try:
        # 2024-01-01T12:00:00Z
        dt = datetime.strptime(value.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
        return int(dt.timestamp() * 1000)
    except Exception:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return _ms_now()


def _allure_status(status: str) -> str:
    s = (status or "").upper()
    if s == "PASS":
        return "passed"
    if s == "SKIP":
        return "skipped"
    if s == "WARN":
        return "broken"
    if s in ("FAIL", "ERROR"):
        return "failed"
    return "broken"


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", (name or "run").strip())[:80] or "run"


def _copy_attachment(src: str | Path, dest_dir: Path) -> tuple[str, str] | None:
    """Copy screenshot into attachments/; return (source_name, type) or None."""
    path = Path(src)
    if not path.is_file():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex[:12]}_{path.name}"
    dest = dest_dir / name
    try:
        shutil.copy2(path, dest)
    except Exception:
        return None
    mime = "image/png" if path.suffix.lower() == ".png" else "application/octet-stream"
    return name, mime


def _result_json_for_run(run: TestRun, attachments_dir: Path) -> dict[str, Any]:
    start = _parse_ts_ms(run.started_at)
    stop = _parse_ts_ms(run.finished_at) if run.finished_at else start + max(run.duration_ms, 0)
    steps_out: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    cursor = start

    for sr in run.step_results or []:
        step_stop = cursor + max(int(sr.duration_ms or 0), 1)
        step: dict[str, Any] = {
            "name": sr.step_name or sr.step_type,
            "status": _allure_status(sr.status),
            "stage": "finished",
            "start": cursor,
            "stop": step_stop,
            "statusDetails": {"message": (sr.detail or "")[:2000]} if sr.detail else {},
        }
        if sr.screenshot:
            copied = _copy_attachment(sr.screenshot, attachments_dir)
            if copied:
                att_name, mime = copied
                att = {"name": f"screenshot-{sr.step_name or 'step'}", "source": att_name, "type": mime}
                attachments.append(att)
                step["attachments"] = [att]
        steps_out.append(step)
        cursor = step_stop

    result = {
        "uuid": str(uuid.uuid4()),
        "historyId": run.test_id or run.id,
        "name": run.test_name or run.id,
        "fullName": f"{run.project_id}.{run.test_name}",
        "status": _allure_status(run.status),
        "stage": "finished",
        "start": start,
        "stop": stop,
        "labels": [
            {"name": "framework", "value": "flowtest"},
            {"name": "testId", "value": run.test_id},
            {"name": "runId", "value": run.id},
            {"name": "environment", "value": run.environment_name or ""},
            {"name": "suite", "value": run.trigger or "manual"},
        ],
        "steps": steps_out,
        "attachments": attachments,
        "statusDetails": {"message": (run.error or "")[:2000]} if run.error else {},
    }
    return result


def _embed_or_link(path: Path, rel: str) -> str:
    """Prefer small base64 embeds for PNG; otherwise link."""
    try:
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and path.stat().st_size < 1_500_000:
            b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            return f'<img src="data:{mime};base64,{b64}" alt="{html.escape(rel)}" />'
    except Exception:
        pass
    return f'<a href="{html.escape(rel)}" target="_blank">{html.escape(path.name)}</a>'


def _write_html_report(
    out_dir: Path,
    title: str,
    runs: list[TestRun],
    summary: dict[str, Any] | None = None,
) -> Path:
    rows: list[str] = []
    summary = summary or {}
    passed = summary.get("passed")
    failed = summary.get("failed")
    if passed is None:
        passed = sum(1 for r in runs if r.status == "PASS")
    if failed is None:
        failed = sum(1 for r in runs if r.status != "PASS")

    for run in runs:
        status_cls = "pass" if run.status == "PASS" else "fail"
        step_html: list[str] = []
        for sr in run.step_results or []:
            sc = "pass" if sr.status == "PASS" else ("skip" if sr.status == "SKIP" else ("warn" if sr.status == "WARN" else "fail"))
            img = ""
            if sr.screenshot:
                # Prefer attachment copy under out_dir/attachments
                src_path = Path(sr.screenshot)
                att_candidates = list((out_dir / "attachments").glob(f"*_{src_path.name}")) if src_path.name else []
                show = att_candidates[0] if att_candidates else src_path
                if show.is_file():
                    try:
                        rel = show.relative_to(out_dir).as_posix()
                    except ValueError:
                        rel = str(show)
                    img = f'<div class="shot">{_embed_or_link(show, rel)}</div>'
            step_html.append(
                f'<div class="step {sc}">'
                f'<div class="step-h"><span class="badge">{html.escape(sr.status)}</span> '
                f"{html.escape(sr.step_name or sr.step_type)} "
                f'<span class="muted">{int(sr.duration_ms or 0)} ms</span></div>'
                f'<div class="detail">{html.escape((sr.detail or "")[:500])}</div>'
                f"{img}</div>"
            )
        rows.append(
            f'<section class="test {status_cls}">'
            f"<h2><span class=\"badge\">{html.escape(run.status)}</span> "
            f"{html.escape(run.test_name)} "
            f'<span class="muted">{run.duration_ms} ms · {html.escape(run.environment_name or "")}</span></h2>'
            f'<div class="meta">run <code>{html.escape(run.id)}</code> · trigger {html.escape(run.trigger)}</div>'
            f'{"".join(step_html)}</section>'
        )

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>
:root {{ --bg:#0f1419; --card:#1a222c; --pass:#3dd68c; --fail:#f07178; --skip:#e6c07b; --text:#e6edf3; --muted:#8b9bb4; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:15px/1.45 system-ui,Segoe UI,sans-serif; background:linear-gradient(160deg,#0f1419,#182230); color:var(--text); }}
header {{ padding:28px 32px 12px; }}
h1 {{ margin:0 0 8px; font-size:1.55rem; }}
.summary {{ display:flex; gap:16px; flex-wrap:wrap; margin:12px 0 24px; }}
.pill {{ background:var(--card); padding:10px 14px; border-radius:10px; border:1px solid #2a3544; }}
.pill strong {{ color:var(--pass); }}
.pill.fail strong {{ color:var(--fail); }}
main {{ padding:0 32px 48px; display:grid; gap:16px; }}
.test {{ background:var(--card); border-radius:12px; padding:16px 18px; border-left:4px solid var(--pass); }}
.test.fail {{ border-left-color:var(--fail); }}
.test h2 {{ margin:0 0 8px; font-size:1.1rem; }}
.meta {{ color:var(--muted); font-size:12px; margin-bottom:10px; }}
.step {{ margin:8px 0; padding:10px 12px; border-radius:8px; background:#121820; border:1px solid #243041; }}
.step.fail {{ border-color:#5c2b32; }}
.step.pass {{ border-color:#1f4d3a; }}
.step.skip {{ border-color:#4d4328; }}
.step.warn {{ border-color:#8a6d1b; }}
.badge {{ display:inline-block; font-size:11px; font-weight:700; letter-spacing:.04em; padding:2px 8px; border-radius:999px; background:#243041; }}
.pass .badge, .step.pass .badge {{ background:#1f4d3a; color:var(--pass); }}
.fail .badge, .step.fail .badge {{ background:#5c2b32; color:var(--fail); }}
.skip .badge, .step.skip .badge {{ background:#4d4328; color:var(--skip); }}
.warn .badge, .step.warn .badge {{ background:#5c4a1b; color:var(--skip); }}
.muted {{ color:var(--muted); font-weight:500; font-size:12px; }}
.detail {{ color:var(--muted); font-size:13px; margin-top:4px; white-space:pre-wrap; }}
.shot img {{ max-width:min(720px,100%); margin-top:8px; border-radius:8px; border:1px solid #2a3544; }}
code {{ font-size:12px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="summary">
    <div class="pill">Passed <strong>{passed}</strong></div>
    <div class="pill fail">Failed <strong>{failed}</strong></div>
    <div class="pill">Tests <strong>{len(runs)}</strong></div>
    <div class="pill">Generated <strong>{html.escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))}</strong></div>
  </div>
</header>
<main>
{"".join(rows) or "<p>No runs.</p>"}
</main>
</body>
</html>
"""
    report_path = out_dir / "report.html"
    report_path.write_text(body, encoding="utf-8")
    return report_path


def write_run_allure(run: TestRun, out_dir: str | Path | None = None) -> Path:
    """Write Allure result JSON + HTML report for a single TestRun."""
    base = Path(out_dir) if out_dir else ALLURE_ROOT / f"run_{_safe_name(run.id)}"
    base.mkdir(parents=True, exist_ok=True)
    attachments_dir = base / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    result = _result_json_for_run(run, attachments_dir)
    result_path = base / f"{result['uuid']}-result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Also keep a stable name for easy lookup
    (base / "run-meta.json").write_text(
        json.dumps(
            {
                "run_id": run.id,
                "test_name": run.test_name,
                "status": run.status,
                "result_file": result_path.name,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _write_html_report(base, f"FlowTest · {run.test_name}", [run])
    return base


def write_suite_allure(
    summary: dict[str, Any],
    runs: list[TestRun],
    *,
    out_dir: str | Path | None = None,
    label: str = "suite",
) -> Path:
    """Write combined Allure results + HTML for a suite summary."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = Path(out_dir) if out_dir else ALLURE_ROOT / f"{_safe_name(label)}_{stamp}"
    base.mkdir(parents=True, exist_ok=True)
    attachments_dir = base / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    for run in runs:
        result = _result_json_for_run(run, attachments_dir)
        (base / f"{result['uuid']}-result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

    (base / "suite-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    title = f"FlowTest suite · {summary.get('suite') or label}"
    _write_html_report(base, title, runs, summary=summary)
    return base


def zip_report(report_dir: str | Path) -> Path:
    """Zip an allure-results directory; returns path to .zip next to it."""
    d = Path(report_dir)
    if not d.is_dir():
        raise FileNotFoundError(str(d))
    zip_path = d.with_suffix(".zip") if d.suffix != ".zip" else d.parent / f"{d.name}.zip"
    # Prefer sibling zip: flowtest_data/allure-results/run_xyz.zip
    zip_path = d.parent / f"{d.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in d.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(d).as_posix())
    return zip_path


def find_run_report_dir(run_id: str) -> Path | None:
    candidate = ALLURE_ROOT / f"run_{_safe_name(run_id)}"
    if candidate.is_dir() and (candidate / "report.html").is_file():
        return candidate
    # Fallback scan
    if not ALLURE_ROOT.is_dir():
        return None
    for d in ALLURE_ROOT.iterdir():
        if not d.is_dir():
            continue
        meta = d / "run-meta.json"
        if meta.is_file():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                if data.get("run_id") == run_id and (d / "report.html").is_file():
                    return d
            except Exception:
                continue
    return None
