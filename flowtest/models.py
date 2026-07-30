"""
FlowTest — shared models for tests, projects, runs, environments, and users.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str = "") -> str:
    uid = uuid4().hex[:10]
    return f"{prefix}{uid}" if prefix else uid


ROLES = ("Admin", "Editor", "Runner", "Viewer")

STEP_CATEGORIES = {
    "ui": "Web UI",
    "api": "REST API",
    "assert": "Assertions",
    "data": "Data / ETL",
    "flow": "Flow Control",
    "util": "Utilities",
}


@dataclass
class User:
    id: str
    username: str
    display_name: str
    role: str = "Editor"
    password_hash: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Environment:
    id: str
    name: str
    base_url: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Project:
    id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestStep:
    id: str
    type: str
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestCase:
    id: str
    project_id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    steps: list[TestStep] = field(default_factory=list)
    suite: str = "Default"
    version: int = 1
    created_by: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StepResult:
    step_id: str
    step_name: str
    step_type: str
    status: str  # PASS | FAIL | SKIP
    detail: str = ""
    duration_ms: int = 0
    screenshot: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestRun:
    id: str
    test_id: str
    test_name: str
    project_id: str
    environment_id: str
    environment_name: str
    status: str  # PASS | FAIL | ERROR | RUNNING
    triggered_by: str = ""
    started_at: str = field(default_factory=utc_now)
    finished_at: str = ""
    duration_ms: int = 0
    step_results: list[StepResult] = field(default_factory=list)
    error: str = ""
    trigger: str = "manual"  # manual | schedule | webhook | cli

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEntry:
    id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str
    detail: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
