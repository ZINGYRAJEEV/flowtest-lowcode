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

## Recipe: web text → Notepad

In **Test Builder → Recipe: copy web text → Notepad**:

1. Set the web URL and CSS selector (or use text selection)
2. Click **Insert Web → Notepad recipe**
3. Save and run **locally** (headed)

Generated flow: open page → copy text (variable + clipboard) → launch Notepad → paste (Ctrl+V).

You can refine the web half with the browser recorder and the Notepad half with the desktop recorder (Ctrl+V is captured as Paste).

New steps: `ui.copy_text`, `desktop.launch`, `desktop.paste`, `util.clipboard_set` / `util.clipboard_get`.
