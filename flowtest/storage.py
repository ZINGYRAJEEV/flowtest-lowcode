"""
FlowTest — SQLite persistence for projects, tests, runs, environments, users.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from flowtest.models import (
    AuditEntry,
    Environment,
    Project,
    StepResult,
    TestCase,
    TestRun,
    TestStep,
    User,
    new_id,
    utc_now,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "flowtest_data"
DB_PATH = DATA_DIR / "flowtest.db"
ARTIFACTS_DIR = DATA_DIR / "artifacts"


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS environments (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            base_url TEXT,
            variables_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            tags_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tests (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            tags_json TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            suite TEXT NOT NULL,
            version INTEGER NOT NULL,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            test_id TEXT NOT NULL,
            test_name TEXT NOT NULL,
            project_id TEXT NOT NULL,
            environment_id TEXT,
            environment_name TEXT,
            status TEXT NOT NULL,
            triggered_by TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            step_results_json TEXT NOT NULL,
            error TEXT,
            trigger TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()
    _seed_if_empty()


def _seed_if_empty() -> None:
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if n == 0:
        users = [
            User(new_id("usr_"), "admin", "Admin User", "Admin", _hash("admin123")),
            User(new_id("usr_"), "editor", "Editor User", "Editor", _hash("editor123")),
            User(new_id("usr_"), "viewer", "Viewer User", "Viewer", _hash("viewer123")),
            User(new_id("usr_"), "runner", "CI Runner", "Runner", _hash("runner123")),
        ]
        for u in users:
            conn.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,?)",
                (u.id, u.username, u.display_name, u.role, u.password_hash, u.created_at),
            )
        env = Environment(
            id=new_id("env_"),
            name="Staging",
            base_url="https://example.com",
            variables={"API_BASE": "https://jsonplaceholder.typicode.com", "USERNAME": "demo"},
        )
        conn.execute(
            "INSERT INTO environments VALUES (?,?,?,?,?)",
            (env.id, env.name, env.base_url, json.dumps(env.variables), env.created_at),
        )
        env2 = Environment(
            id=new_id("env_"),
            name="Dev",
            base_url="https://example.com",
            variables={"API_BASE": "https://jsonplaceholder.typicode.com", "USERNAME": "dev_user"},
        )
        conn.execute(
            "INSERT INTO environments VALUES (?,?,?,?,?)",
            (env2.id, env2.name, env2.base_url, json.dumps(env2.variables), env2.created_at),
        )
        proj = Project(
            id=new_id("prj_"),
            name="Sample Web App",
            description="Demo project with UI + API smoke flows",
            tags=["demo", "mvp"],
        )
        conn.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?)",
            (
                proj.id,
                proj.name,
                proj.description,
                json.dumps(proj.tags),
                proj.created_at,
                proj.updated_at,
            ),
        )
        sample_steps = [
            TestStep(
                id=new_id("stp_"),
                type="ui.goto",
                name="Open homepage",
                config={"url": "{{BASE_URL}}"},
            ),
            TestStep(
                id=new_id("stp_"),
                type="ui.wait",
                name="Wait for settle",
                config={"ms": 800},
            ),
            TestStep(
                id=new_id("stp_"),
                type="assert.title_contains",
                name="Title contains Example",
                config={"text": "Example"},
            ),
            TestStep(
                id=new_id("stp_"),
                type="api.request",
                name="GET httpbin /get",
                config={
                    "method": "GET",
                    "url": "{{API_BASE}}/posts/1",
                    "headers": {},
                    "body": "",
                    "save_as": "httpbin_get",
                },
            ),
            TestStep(
                id=new_id("stp_"),
                type="assert.api_status",
                name="Status is 200",
                config={"save_as": "httpbin_get", "status": 200},
            ),
        ]
        test = TestCase(
            id=new_id("tst_"),
            project_id=proj.id,
            name="Smoke: Example + JSONPlaceholder",
            description="Opens example.com, asserts title, then calls JSONPlaceholder GET /posts/1.",
            tags=["smoke", "ui", "api"],
            steps=sample_steps,
            suite="Smoke",
            created_by="admin",
        )
        conn.execute(
            "INSERT INTO tests VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                test.id,
                test.project_id,
                test.name,
                test.description,
                json.dumps(test.tags),
                json.dumps([s.to_dict() for s in test.steps]),
                test.suite,
                test.version,
                test.created_by,
                test.created_at,
                test.updated_at,
            ),
        )
        conn.commit()
    conn.close()


def _hash(password: str) -> str:
    import hashlib

    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return _hash(password) == password_hash


# ---------- Users ----------


def list_users() -> list[User]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    conn.close()
    return [
        User(r["id"], r["username"], r["display_name"], r["role"], r["password_hash"], r["created_at"])
        for r in rows
    ]


def get_user_by_username(username: str) -> User | None:
    conn = _connect()
    r = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not r:
        return None
    return User(r["id"], r["username"], r["display_name"], r["role"], r["password_hash"], r["created_at"])


def authenticate(username: str, password: str) -> User | None:
    user = get_user_by_username(username)
    if user and verify_password(password, user.password_hash):
        return user
    return None


def update_user_role(user_id: str, role: str) -> None:
    conn = _connect()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()


# ---------- Environments ----------


def list_environments() -> list[Environment]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM environments ORDER BY name").fetchall()
    conn.close()
    return [
        Environment(r["id"], r["name"], r["base_url"] or "", json.loads(r["variables_json"]), r["created_at"])
        for r in rows
    ]


def get_environment(env_id: str) -> Environment | None:
    conn = _connect()
    r = conn.execute("SELECT * FROM environments WHERE id=?", (env_id,)).fetchone()
    conn.close()
    if not r:
        return None
    return Environment(r["id"], r["name"], r["base_url"] or "", json.loads(r["variables_json"]), r["created_at"])


def save_environment(env: Environment) -> None:
    conn = _connect()
    existing = conn.execute("SELECT id FROM environments WHERE id=?", (env.id,)).fetchone()
    payload = (env.id, env.name, env.base_url, json.dumps(env.variables), env.created_at)
    if existing:
        conn.execute(
            "UPDATE environments SET name=?, base_url=?, variables_json=? WHERE id=?",
            (env.name, env.base_url, json.dumps(env.variables), env.id),
        )
    else:
        conn.execute("INSERT INTO environments VALUES (?,?,?,?,?)", payload)
    conn.commit()
    conn.close()


def delete_environment(env_id: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM environments WHERE id=?", (env_id,))
    conn.commit()
    conn.close()


# ---------- Projects ----------


def list_projects() -> list[Project]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
    conn.close()
    return [
        Project(r["id"], r["name"], r["description"] or "", json.loads(r["tags_json"]), r["created_at"], r["updated_at"])
        for r in rows
    ]


def get_project(project_id: str) -> Project | None:
    conn = _connect()
    r = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    if not r:
        return None
    return Project(r["id"], r["name"], r["description"] or "", json.loads(r["tags_json"]), r["created_at"], r["updated_at"])


def save_project(project: Project) -> None:
    project.updated_at = utc_now()
    conn = _connect()
    existing = conn.execute("SELECT id FROM projects WHERE id=?", (project.id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE projects SET name=?, description=?, tags_json=?, updated_at=? WHERE id=?",
            (project.name, project.description, json.dumps(project.tags), project.updated_at, project.id),
        )
    else:
        conn.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?)",
            (
                project.id,
                project.name,
                project.description,
                json.dumps(project.tags),
                project.created_at,
                project.updated_at,
            ),
        )
    conn.commit()
    conn.close()


def delete_project(project_id: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM tests WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()


# ---------- Tests ----------


def _row_to_test(r: sqlite3.Row) -> TestCase:
    steps_raw = json.loads(r["steps_json"])
    steps = [TestStep(**s) for s in steps_raw]
    return TestCase(
        id=r["id"],
        project_id=r["project_id"],
        name=r["name"],
        description=r["description"] or "",
        tags=json.loads(r["tags_json"]),
        steps=steps,
        suite=r["suite"],
        version=r["version"],
        created_by=r["created_by"] or "",
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def list_tests(project_id: str | None = None) -> list[TestCase]:
    conn = _connect()
    if project_id:
        rows = conn.execute(
            "SELECT * FROM tests WHERE project_id=? ORDER BY suite, name", (project_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tests ORDER BY suite, name").fetchall()
    conn.close()
    return [_row_to_test(r) for r in rows]


def get_test(test_id: str) -> TestCase | None:
    conn = _connect()
    r = conn.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
    conn.close()
    return _row_to_test(r) if r else None


def save_test(test: TestCase, bump_version: bool = True) -> None:
    test.updated_at = utc_now()
    conn = _connect()
    existing = conn.execute("SELECT id, version FROM tests WHERE id=?", (test.id,)).fetchone()
    steps_json = json.dumps([s.to_dict() for s in test.steps])
    if existing:
        version = existing["version"] + 1 if bump_version else existing["version"]
        test.version = version
        conn.execute(
            """UPDATE tests SET project_id=?, name=?, description=?, tags_json=?, steps_json=?,
               suite=?, version=?, updated_at=? WHERE id=?""",
            (
                test.project_id,
                test.name,
                test.description,
                json.dumps(test.tags),
                steps_json,
                test.suite,
                test.version,
                test.updated_at,
                test.id,
            ),
        )
    else:
        conn.execute(
            "INSERT INTO tests VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                test.id,
                test.project_id,
                test.name,
                test.description,
                json.dumps(test.tags),
                steps_json,
                test.suite,
                test.version,
                test.created_by,
                test.created_at,
                test.updated_at,
            ),
        )
    conn.commit()
    conn.close()


def delete_test(test_id: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM tests WHERE id=?", (test_id,))
    conn.commit()
    conn.close()


# ---------- Runs ----------


def save_run(run: TestRun) -> None:
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run.id,
            run.test_id,
            run.test_name,
            run.project_id,
            run.environment_id,
            run.environment_name,
            run.status,
            run.triggered_by,
            run.started_at,
            run.finished_at,
            run.duration_ms,
            json.dumps([s.to_dict() for s in run.step_results]),
            run.error,
            run.trigger,
        ),
    )
    conn.commit()
    conn.close()


def list_runs(limit: int = 100, project_id: str | None = None) -> list[TestRun]:
    conn = _connect()
    if project_id:
        rows = conn.execute(
            "SELECT * FROM runs WHERE project_id=? ORDER BY started_at DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [_row_to_run(r) for r in rows]


def get_run(run_id: str) -> TestRun | None:
    conn = _connect()
    r = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    return _row_to_run(r) if r else None


def _row_to_run(r: sqlite3.Row) -> TestRun:
    steps = [StepResult(**s) for s in json.loads(r["step_results_json"])]
    return TestRun(
        id=r["id"],
        test_id=r["test_id"],
        test_name=r["test_name"],
        project_id=r["project_id"],
        environment_id=r["environment_id"] or "",
        environment_name=r["environment_name"] or "",
        status=r["status"],
        triggered_by=r["triggered_by"] or "",
        started_at=r["started_at"],
        finished_at=r["finished_at"] or "",
        duration_ms=r["duration_ms"] or 0,
        step_results=steps,
        error=r["error"] or "",
        trigger=r["trigger"] or "manual",
    )


def run_stats() -> dict[str, Any]:
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"]
    passed = conn.execute("SELECT COUNT(*) AS c FROM runs WHERE status='PASS'").fetchone()["c"]
    failed = conn.execute(
        "SELECT COUNT(*) AS c FROM runs WHERE status IN ('FAIL','ERROR')"
    ).fetchone()["c"]
    tests = conn.execute("SELECT COUNT(*) AS c FROM tests").fetchone()["c"]
    projects = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
    conn.close()
    rate = round((passed / total) * 100, 1) if total else 0.0
    return {
        "total_runs": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": rate,
        "tests": tests,
        "projects": projects,
    }


# ---------- Audit ----------


def add_audit(actor: str, action: str, entity_type: str, entity_id: str, detail: str = "") -> None:
    entry = AuditEntry(new_id("aud_"), actor, action, entity_type, entity_id, detail)
    conn = _connect()
    conn.execute(
        "INSERT INTO audit_log VALUES (?,?,?,?,?,?,?)",
        (entry.id, entry.actor, entry.action, entry.entity_type, entry.entity_id, entry.detail, entry.created_at),
    )
    conn.commit()
    conn.close()


def list_audit(limit: int = 50) -> list[AuditEntry]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [
        AuditEntry(r["id"], r["actor"], r["action"], r["entity_type"], r["entity_id"], r["detail"] or "", r["created_at"])
        for r in rows
    ]


def export_test_json(test: TestCase) -> str:
    return json.dumps(test.to_dict(), indent=2)


def import_test_dict(data: dict[str, Any], project_id: str, created_by: str) -> TestCase:
    steps = [TestStep(**s) if isinstance(s, dict) else s for s in data.get("steps", [])]
    for s in steps:
        if not s.id:
            s.id = new_id("stp_")
    test = TestCase(
        id=new_id("tst_"),
        project_id=project_id,
        name=data.get("name", "Imported test"),
        description=data.get("description", ""),
        tags=data.get("tags", []),
        steps=steps,
        suite=data.get("suite", "Imported"),
        created_by=created_by,
    )
    save_test(test, bump_version=False)
    return test
