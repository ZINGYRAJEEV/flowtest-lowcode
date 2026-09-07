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

## Desktop recorder

In **Test Builder → Record desktop session**:

1. Optionally set an app to launch (e.g. `notepad.exe`)
2. Click **Start desktop recording**
3. A floating panel appears — use your apps normally (click / type)
4. Press **F8** to assert the current window, or **Finish** / **F9** when done
5. Review the generated Desktop UI steps and save

Requires local Windows + `pip install -r requirements-desktop.txt`.
