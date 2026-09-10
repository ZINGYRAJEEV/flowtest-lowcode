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
            {"key": "testid", "label": "data-testid / data-qa", "kind": "text", "default": ""},
            {
                "key": "role",
                "label": "ARIA role (optional)",
                "kind": "select",
                "options": ["", "button", "link", "textbox", "checkbox", "radio", "menuitem", "option", "tab"],
                "default": "",
            },
            {
                "key": "alternates",
                "label": "Alternate selectors (one per line)",
                "kind": "textarea",
                "default": "",
            },
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
        ],
    },
    {
        "type": "ui.click_by_text",
        "category": "ui",
        "label": "Click / select by text",
        "description": "Find and click a visible option, button, or label by its text (stable when option order changes).",
        "fields": [
            {"key": "text", "label": "Visible text", "kind": "text", "default": ""},
            {
                "key": "exact",
                "label": "Exact match",
                "kind": "bool",
                "default": False,
            },
            {
                "key": "role",
                "label": "Prefer role",
                "kind": "select",
                "options": ["", "option", "button", "radio", "menuitem", "link", "checkbox"],
                "default": "option",
            },
            {
                "key": "within",
                "label": "Optional scope selector",
                "kind": "text",
                "default": "",
            },
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
            {"key": "testid", "label": "data-testid / data-qa", "kind": "text", "default": ""},
            {
                "key": "role",
                "label": "ARIA role (optional)",
                "kind": "select",
                "options": ["", "textbox", "searchbox", "combobox"],
                "default": "",
            },
            {
                "key": "alternates",
                "label": "Alternate selectors (one per line)",
                "kind": "textarea",
                "default": "",
            },
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
        "type": "ui.select_by_text",
        "category": "ui",
        "label": "Select option by text",
        "description": "Pick a native or custom dropdown option by visible text (not by changing index).",
        "fields": [
            {"key": "text", "label": "Option text", "kind": "text", "default": ""},
            {"key": "selector", "label": "Dropdown selector (optional)", "kind": "text", "default": ""},
            {"key": "exact", "label": "Exact match", "kind": "bool", "default": False},
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
            {"key": "testid", "label": "data-testid / data-qa", "kind": "text", "default": ""},
            {
                "key": "role",
                "label": "ARIA role (optional)",
                "kind": "select",
                "options": ["", "button", "link", "textbox", "heading", "img", "listitem"],
                "default": "",
            },
            {
                "key": "alternates",
                "label": "Alternate selectors (one per line)",
                "kind": "textarea",
                "default": "",
            },
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
    {
        "type": "ui.copy_text",
        "category": "ui",
        "label": "Copy text from page",
        "description": "Read text from a CSS selector (or current selection) into a variable and optionally the Windows clipboard — for pasting into Notepad/desktop apps.",
        "fields": [
            {"key": "selector", "label": "CSS selector", "kind": "text", "default": "body"},
            {
                "key": "use_selection",
                "label": "Use current text selection instead",
                "kind": "bool",
                "default": False,
            },
            {"key": "save_as", "label": "Save as variable", "kind": "text", "default": "web_text"},
            {
                "key": "to_clipboard",
                "label": "Also set Windows clipboard",
                "kind": "bool",
                "default": True,
            },
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 30000},
        ],
    },
    # Desktop (Windows local only — pip install -r requirements-desktop.txt)
    {
        "type": "desktop.focus_window",
        "category": "desktop",
        "label": "Focus window",
        "description": "Bring a desktop app window to the front by title (Windows, local only).",
        "fields": [
            {"key": "title", "label": "Window title contains", "kind": "text", "default": "Notepad"},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 15000},
        ],
    },
    {
        "type": "desktop.launch",
        "category": "desktop",
        "label": "Launch app",
        "description": "Start a desktop program (e.g. notepad.exe).",
        "fields": [
            {"key": "command", "label": "Command", "kind": "text", "default": "notepad.exe"},
            {"key": "wait_ms", "label": "Wait after launch (ms)", "kind": "number", "default": 1200},
        ],
    },
    {
        "type": "desktop.paste",
        "category": "desktop",
        "label": "Paste (Ctrl+V)",
        "description": "Paste clipboard into the focused desktop window. Optionally refresh clipboard from a variable first.",
        "fields": [
            {"key": "window_title", "label": "Window title contains", "kind": "text", "default": "Notepad"},
            {
                "key": "from_variable",
                "label": "Refresh clipboard from variable",
                "kind": "text",
                "default": "web_text",
            },
            {
                "key": "refresh_clipboard",
                "label": "Refresh clipboard before paste",
                "kind": "bool",
                "default": True,
            },
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 15000},
        ],
    },
    {
        "type": "desktop.click",
        "category": "desktop",
        "label": "Click desktop control",
        "description": "Click a button/menu/control by name or AutomationId (Windows UI Automation).",
        "fields": [
            {"key": "window_title", "label": "Window title contains", "kind": "text", "default": ""},
            {"key": "name", "label": "Control name / text", "kind": "text", "default": ""},
            {"key": "auto_id", "label": "AutomationId (optional)", "kind": "text", "default": ""},
            {
                "key": "control_type",
                "label": "Control type",
                "kind": "select",
                "options": ["", "Button", "Edit", "MenuItem", "TabItem", "ListItem", "CheckBox", "ComboBox", "Text"],
                "default": "Button",
            },
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 15000},
        ],
    },
    {
        "type": "desktop.type_text",
        "category": "desktop",
        "label": "Type into desktop",
        "description": "Type text into the focused window or a named control.",
        "fields": [
            {"key": "text", "label": "Text", "kind": "text", "default": ""},
            {"key": "window_title", "label": "Window title contains", "kind": "text", "default": ""},
            {"key": "name", "label": "Control name (optional)", "kind": "text", "default": ""},
            {"key": "auto_id", "label": "AutomationId (optional)", "kind": "text", "default": ""},
            {"key": "control_type", "label": "Control type", "kind": "select", "options": ["", "Edit", "Document"], "default": "Edit"},
            {"key": "clear", "label": "Clear first", "kind": "bool", "default": False},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 15000},
        ],
    },
    {
        "type": "desktop.send_keys",
        "category": "desktop",
        "label": "Send desktop keys",
        "description": "Hotkeys / special keys (e.g. ^s save, {ENTER}, %{F4}).",
        "fields": [
            {"key": "keys", "label": "Keys", "kind": "text", "default": "{ENTER}"},
            {"key": "window_title", "label": "Window title contains", "kind": "text", "default": ""},
        ],
    },
    {
        "type": "desktop.wait",
        "category": "desktop",
        "label": "Desktop wait (ms)",
        "description": "Fixed wait between desktop actions.",
        "fields": [
            {"key": "ms", "label": "Milliseconds", "kind": "number", "default": 1000},
        ],
    },
    {
        "type": "desktop.screenshot",
        "category": "desktop",
        "label": "Desktop screenshot",
        "description": "Capture the full desktop screen (local Windows).",
        "fields": [
            {"key": "label", "label": "Label", "kind": "text", "default": "desktop"},
        ],
    },
    {
        "type": "assert.desktop_window",
        "category": "desktop",
        "label": "Assert desktop window",
        "description": "Fail unless a window title matching text is present.",
        "fields": [
            {"key": "title", "label": "Window title contains", "kind": "text", "default": ""},
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 10000},
        ],
    },
    {
        "type": "assert.desktop_control",
        "category": "desktop",
        "label": "Assert desktop control",
        "description": "Fail unless a named control exists in the window.",
        "fields": [
            {"key": "window_title", "label": "Window title contains", "kind": "text", "default": ""},
            {"key": "name", "label": "Control name / text", "kind": "text", "default": ""},
            {"key": "auto_id", "label": "AutomationId (optional)", "kind": "text", "default": ""},
            {
                "key": "control_type",
                "label": "Control type",
                "kind": "select",
                "options": ["", "Button", "Edit", "MenuItem", "TabItem", "Text"],
                "default": "",
            },
            {"key": "timeout_ms", "label": "Timeout (ms)", "kind": "number", "default": 10000},
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
            {"key": "testid", "label": "data-testid / data-qa", "kind": "text", "default": ""},
            {
                "key": "role",
                "label": "ARIA role (optional)",
                "kind": "select",
                "options": ["", "button", "link", "textbox", "heading", "img", "listitem"],
                "default": "",
            },
            {
                "key": "alternates",
                "label": "Alternate selectors (one per line)",
                "kind": "textarea",
                "default": "",
            },
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
    # AI / Verify — independent oracles against polite / soft failures
    {
        "type": "verify.invariant",
        "category": "verify",
        "label": "Verify page invariant (JS)",
        "description": "Evaluate a JS expression that must be truthy (catches silent wrong UI state).",
        "fields": [
            {
                "key": "expression",
                "label": "JS expression (truthy = pass)",
                "kind": "textarea",
                "default": "document.body && document.body.innerText.length > 0",
            },
            {
                "key": "severity",
                "label": "Severity",
                "kind": "select",
                "options": ["hard", "soft"],
                "default": "hard",
            },
            {"key": "message", "label": "Failure message", "kind": "text", "default": "Invariant failed"},
        ],
    },
    {
        "type": "verify.page_truth",
        "category": "verify",
        "label": "Verify page Failure Truthfulness",
        "description": "Fail if the page looks 'OK' but shows error banners / empty shell / soft error text.",
        "fields": [
            {
                "key": "error_texts",
                "label": "Soft-error phrases (one per line)",
                "kind": "textarea",
                "default": "something went wrong\nunexpected error\nundefined\nnull is not\nfailed to load",
            },
            {
                "key": "require_min_text_len",
                "label": "Min body text length",
                "kind": "number",
                "default": 20,
            },
            {
                "key": "severity",
                "label": "Severity",
                "kind": "select",
                "options": ["hard", "soft"],
                "default": "hard",
            },
        ],
    },
    {
        "type": "verify.not_empty",
        "category": "verify",
        "label": "Verify value not empty",
        "description": "Variable/result must be non-empty — blocks empty-success polite failures.",
        "fields": [
            {"key": "variable", "label": "Variable name", "kind": "text", "default": "last_response"},
            {
                "key": "json_path",
                "label": "Optional JSON path under variable",
                "kind": "text",
                "default": "",
            },
            {
                "key": "severity",
                "label": "Severity",
                "kind": "select",
                "options": ["hard", "soft"],
                "default": "hard",
            },
        ],
    },
    {
        "type": "verify.api_truthful",
        "category": "verify",
        "label": "Verify API response truthful",
        "description": "If status is success-class, body must not be empty and optional field must exist.",
        "fields": [
            {"key": "save_as", "label": "Response variable", "kind": "text", "default": "last_response"},
            {
                "key": "success_statuses",
                "label": "Success statuses (comma)",
                "kind": "text",
                "default": "200,201,204",
            },
            {
                "key": "require_field",
                "label": "Required JSON field (optional)",
                "kind": "text",
                "default": "",
            },
            {
                "key": "forbid_field_equals",
                "label": "Forbid field=value (e.g. success=false)",
                "kind": "text",
                "default": "",
            },
            {
                "key": "severity",
                "label": "Severity",
                "kind": "select",
                "options": ["hard", "soft"],
                "default": "hard",
            },
        ],
    },
    {
        "type": "verify.intent_table",
        "category": "verify",
        "label": "Verify intent table (JS)",
        "description": "Run rows of {input, expect} via a JS function — catches intent inversion.",
        "fields": [
            {
                "key": "function_body",
                "label": "JS function body (args: input) → value",
                "kind": "textarea",
                "default": "return String(input).length;",
            },
            {
                "key": "cases_json",
                "label": "Cases JSON array [{input, expect}]",
                "kind": "textarea",
                "default": '[{"input":"ab","expect":2},{"input":"","expect":0}]',
            },
            {
                "key": "severity",
                "label": "Severity",
                "kind": "select",
                "options": ["hard", "soft"],
                "default": "hard",
            },
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
        "type": "util.clipboard_set",
        "category": "util",
        "label": "Set clipboard",
        "description": "Put text (or a {{variable}}) on the Windows clipboard.",
        "fields": [
            {"key": "text", "label": "Text / {{variable}}", "kind": "textarea", "default": "{{web_text}}"},
        ],
    },
    {
        "type": "util.clipboard_get",
        "category": "util",
        "label": "Get clipboard",
        "description": "Read the Windows clipboard into a variable.",
        "fields": [
            {"key": "save_as", "label": "Save as variable", "kind": "text", "default": "clipboard_text"},
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
            {
                "key": "expect_contains",
                "label": "Fail unless result contains",
                "kind": "text",
                "default": "",
            },
            {
                "key": "fail_if_contains",
                "label": "Fail if result contains",
                "kind": "text",
                "default": "",
            },
        ],
    },
]


def steps_by_category() -> dict[str, list[dict[str, Any]]]:
    from flowtest.models import STEP_CATEGORIES

    grouped: dict[str, list[dict[str, Any]]] = {k: [] for k in STEP_CATEGORIES}
    for step in STEP_LIBRARY:
        grouped.setdefault(step["category"], []).append(step)
    # Drop empty categories; keep declared order first
    return {k: v for k, v in grouped.items() if v}


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
