"""
FlowTest — step type catalog for the low-code builder.
"""

from __future__ import annotations

from typing import Any


STEP_LIBRARY: list[dict[str, Any]] = [
    # UI
    {
        "type": "ui.goto",
        "category": "ui",
        "label": "Navigate to URL",
        "description": "Open a page in the browser (supports {{BASE_URL}} and variables).",
        "fields": [
            {"key": "url", "label": "URL", "kind": "text", "default": "{{BASE_URL}}"},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
        ],
    },
    {
        "type": "ui.click",
        "category": "ui",
        "label": "Click element",
        "description": "Click a visible element by CSS selector or text (auto-waits until ready).",
        "fields": [
            {"key": "selector", "label": "CSS selector", "kind": "text", "default": ""},
            {"key": "text", "label": "Or button/link text", "kind": "text", "default": ""},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
        ],
    },
    {
        "type": "ui.fill",
        "category": "ui",
        "label": "Fill input",
        "description": "Type into an input/textarea. Auto-waits; handles readonly/masked fields.",
        "fields": [
            {"key": "selector", "label": "CSS selector", "kind": "text", "default": ""},
            {"key": "value", "label": "Value", "kind": "text", "default": ""},
            {"key": "clear", "label": "Clear first", "kind": "bool", "default": True},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
        ],
    },
    {
        "type": "ui.select",
        "category": "ui",
        "label": "Select dropdown",
        "description": "Choose an option by label or index (auto-waits).",
        "fields": [
            {"key": "selector", "label": "CSS selector", "kind": "text", "default": ""},
            {"key": "label", "label": "Option label", "kind": "text", "default": ""},
            {"key": "index", "label": "Or option index", "kind": "number", "default": 1},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
        ],
    },
    {
        "type": "ui.wait",
        "category": "ui",
        "label": "Wait (ms)",
        "description": "Fixed wait to reduce flakiness.",
        "fields": [
            {"key": "ms", "label": "Milliseconds", "kind": "number", "default": 1000},
        ],
    },
    {
        "type": "ui.wait_for",
        "category": "ui",
        "label": "Wait for selector",
        "description": "Wait until an element is visible (or attached).",
        "fields": [
            {"key": "selector", "label": "CSS selector", "kind": "text", "default": ""},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
            {
                "key": "state",
                "label": "State",
                "kind": "select",
                "options": ["visible", "attached", "hidden", "detached"],
                "default": "visible",
            },
        ],
    },
    {
        "type": "ui.screenshot",
        "category": "ui",
        "label": "Take screenshot",
        "description": "Capture the current page.",
        "fields": [
            {"key": "label", "label": "Label", "kind": "text", "default": "checkpoint"},
        ],
    },
    # API
    {
        "type": "api.request",
        "category": "api",
        "label": "HTTP request",
        "description": "Call a REST endpoint and optionally store the response.",
        "fields": [
            {"key": "method", "label": "Method", "kind": "select", "options": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
            {"key": "url", "label": "URL", "kind": "text", "default": "{{API_BASE}}/"},
            {"key": "headers", "label": "Headers (JSON object)", "kind": "json", "default": "{}"},
            {"key": "body", "label": "Body", "kind": "textarea", "default": ""},
            {"key": "save_as", "label": "Save response as", "kind": "text", "default": "last_response"},
        ],
    },
    # Assertions
    {
        "type": "assert.title_contains",
        "category": "assert",
        "label": "Assert title contains",
        "description": "Page title must contain text.",
        "fields": [
            {"key": "text", "label": "Expected text", "kind": "text", "default": ""},
        ],
    },
    {
        "type": "assert.element_exists",
        "category": "assert",
        "label": "Assert element exists",
        "description": "Element matching selector is visible.",
        "fields": [
            {"key": "selector", "label": "CSS selector", "kind": "text", "default": ""},
        ],
    },
    {
        "type": "assert.text_contains",
        "category": "assert",
        "label": "Assert text contains",
        "description": "Page/element contains text (auto-waits; falls back to full page if selector misses).",
        "fields": [
            {"key": "selector", "label": "CSS selector", "kind": "text", "default": "body"},
            {"key": "text", "label": "Expected text", "kind": "text", "default": ""},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
            {"key": "ignore_case", "label": "Ignore case", "kind": "bool", "default": True},
        ],
    },
    {
        "type": "assert.api_status",
        "category": "assert",
        "label": "Assert API status",
        "description": "Saved API response status equals expected.",
        "fields": [
            {"key": "save_as", "label": "Response variable", "kind": "text", "default": "last_response"},
            {"key": "status", "label": "Expected status", "kind": "number", "default": 200},
        ],
    },
    {
        "type": "assert.json_path",
        "category": "assert",
        "label": "Assert JSON field",
        "description": "Check a top-level JSON field equals expected (dot path supported).",
        "fields": [
            {"key": "save_as", "label": "Response variable", "kind": "text", "default": "last_response"},
            {"key": "path", "label": "JSON path (e.g. url)", "kind": "text", "default": ""},
            {"key": "equals", "label": "Expected value", "kind": "text", "default": ""},
        ],
    },
    # Data / ETL (basic)
    {
        "type": "data.sql_query",
        "category": "data",
        "label": "Run SQL query",
        "description": "Execute a query against a configured SQLite/Postgres/MySQL DSN and save rows.",
        "fields": [
            {"key": "dsn", "label": "DSN / SQLite path", "kind": "text", "default": "sqlite:///flowtest_data/sample.db"},
            {"key": "sql", "label": "SQL", "kind": "textarea", "default": "SELECT 1 AS ok"},
            {"key": "save_as", "label": "Save rows as", "kind": "text", "default": "query_rows"},
        ],
    },
    {
        "type": "assert.row_count",
        "category": "data",
        "label": "Assert row count",
        "description": "Saved query row count matches expected.",
        "fields": [
            {"key": "save_as", "label": "Rows variable", "kind": "text", "default": "query_rows"},
            {"key": "count", "label": "Expected count", "kind": "number", "default": 1},
            {"key": "op", "label": "Operator", "kind": "select", "options": ["eq", "gte", "lte", "gt", "lt"], "default": "eq"},
        ],
    },
    {
        "type": "data.compare_counts",
        "category": "data",
        "label": "Compare dataset counts",
        "description": "Compare two saved row-set lengths (source vs target ETL check).",
        "fields": [
            {"key": "source", "label": "Source variable", "kind": "text", "default": "source_rows"},
            {"key": "target", "label": "Target variable", "kind": "text", "default": "target_rows"},
        ],
    },
    # Flow / util
    {
        "type": "flow.set_var",
        "category": "flow",
        "label": "Set variable",
        "description": "Set a runtime variable for later steps.",
        "fields": [
            {"key": "name", "label": "Variable name", "kind": "text", "default": "my_var"},
            {"key": "value", "label": "Value", "kind": "text", "default": ""},
        ],
    },
    {
        "type": "util.comment",
        "category": "util",
        "label": "Comment / annotation",
        "description": "Documentation step for collaboration (always passes).",
        "fields": [
            {"key": "text", "label": "Comment", "kind": "textarea", "default": ""},
        ],
    },
    {
        "type": "util.custom_js",
        "category": "util",
        "label": "Advanced: custom JS in page",
        "description": "Power-user escape hatch — evaluate JavaScript in the browser context.",
        "fields": [
            {"key": "script", "label": "JavaScript expression/script", "kind": "textarea", "default": "document.title"},
            {"key": "save_as", "label": "Save result as", "kind": "text", "default": "js_result"},
        ],
    },
]


def steps_by_category() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for step in STEP_LIBRARY:
        grouped.setdefault(step["category"], []).append(step)
    return grouped


def get_step_def(step_type: str) -> dict[str, Any] | None:
    for step in STEP_LIBRARY:
        if step["type"] == step_type:
            return step
    return None


def default_config(step_type: str) -> dict[str, Any]:
    meta = get_step_def(step_type)
    if not meta:
        return {}
    return {f["key"]: f.get("default", "") for f in meta["fields"]}
