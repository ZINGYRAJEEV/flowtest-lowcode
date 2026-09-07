# Desktop UI automation (Windows)

FlowTest can drive **native Windows apps** (Notepad, Electron, WinForms, WPF, etc.) via UI Automation.

## Setup

```bash
pip install -r requirements-desktop.txt
```

Run FlowTest **locally** (`streamlit run app.py`). Desktop steps do **not** work on Streamlit Cloud.

## In the Test Builder

Open **Desktop UI** in the step library:

| Step | Use |
|------|-----|
| Focus window | Bring app to front by title |
| Click desktop control | Click by name / AutomationId |
| Type into desktop | Type into Edit or focused window |
| Send desktop keys | Hotkeys (`^s`, `{ENTER}`, `%{F4}`) |
| Desktop wait / screenshot | Timing + evidence |
| Assert window / control | Hard fail if missing |

## MCP (Cursor)

Same actions as tools: `desktop_list_windows`, `desktop_focus_window`, `desktop_click`, …

Example: open Notepad, then ask Cursor to focus Notepad and type text.
