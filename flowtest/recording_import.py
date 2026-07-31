"""Import recordings from the FlowTest Chrome extension (or local recorder JSON)."""

from __future__ import annotations

import json
from typing import Any

from flowtest.models import TestStep, new_id
from flowtest.recorder import events_to_steps


def parse_recording_payload(
    data: dict[str, Any] | list[Any],
    replace_base_url: str | None = None,
) -> list[TestStep]:
    """
    Accept:
      - { "steps": [ TestStep dicts... ] }
      - { "events": [ recorder events... ] }
      - [ TestStep dicts... ]
    """
    if isinstance(data, list):
        return [_coerce_step(s) for s in data if isinstance(s, dict) and s.get("type")]

    if not isinstance(data, dict):
        raise ValueError("Recording JSON must be an object or a list of steps")

    steps_raw = data.get("steps")
    if isinstance(steps_raw, list) and steps_raw:
        return [_coerce_step(s) for s in steps_raw if isinstance(s, dict) and s.get("type")]

    events = data.get("events")
    if isinstance(events, list) and events:
        return events_to_steps(events, replace_base_url=replace_base_url)

    raise ValueError("No steps or events found in recording JSON")


def parse_recording_text(text: str, replace_base_url: str | None = None) -> list[TestStep]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Paste or upload a recording JSON first")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    return parse_recording_payload(data, replace_base_url=replace_base_url)


def _coerce_step(raw: dict[str, Any]) -> TestStep:
    sid = str(raw.get("id") or new_id("stp_"))
    return TestStep(
        id=sid,
        type=str(raw.get("type") or ""),
        name=str(raw.get("name") or raw.get("type") or "Step"),
        config=dict(raw.get("config") or {}),
        enabled=bool(raw.get("enabled", True)),
        notes=str(raw.get("notes") or ""),
    )
