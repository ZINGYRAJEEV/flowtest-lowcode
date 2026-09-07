"""
Ready-made hybrid step recipes (web UI + desktop).
"""

from __future__ import annotations

from flowtest.models import TestStep, new_id


def _stp(stype: str, name: str, config: dict, notes: str = "") -> TestStep:
    return TestStep(id=new_id("stp_"), type=stype, name=name, config=config, notes=notes)


def recipe_web_text_to_notepad(
    url: str = "{{BASE_URL}}",
    selector: str = "body",
    use_selection: bool = False,
    notepad_title: str = "Notepad",
    launch_notepad: bool = True,
    save_as: str = "web_text",
    paste_mode: str = "clipboard",
) -> list[TestStep]:
    """
    Copy text from a web page into Notepad.

    paste_mode:
      - clipboard: set OS clipboard + Ctrl+V in Notepad (best for long text)
      - type: type {{save_as}} keystrokes into Notepad
    """
    url = (url or "{{BASE_URL}}").strip() or "{{BASE_URL}}"
    selector = (selector or "body").strip() or "body"
    save_as = (save_as or "web_text").strip() or "web_text"
    notepad_title = (notepad_title or "Notepad").strip() or "Notepad"
    mode = (paste_mode or "clipboard").strip().lower()

    steps: list[TestStep] = [
        _stp(
            "util.comment",
            "Recipe: web to Notepad",
            {
                "text": (
                    "Copies text from the web page, opens Notepad, and pastes it. "
                    "Record/refine selectors with browser + desktop recorders if needed."
                )
            },
        ),
        _stp("ui.goto", "Open web page", {"url": url, "timeout_ms": 60000}),
        _stp("ui.wait", "Wait for page", {"ms": 1500}),
        _stp(
            "ui.copy_text",
            "Copy text from web",
            {
                "selector": "" if use_selection else selector,
                "use_selection": bool(use_selection),
                "save_as": save_as,
                "to_clipboard": True,
                "timeout_ms": 30000,
            },
            "Saves to variable and Windows clipboard",
        ),
    ]

    if launch_notepad:
        steps.append(
            _stp(
                "desktop.launch",
                "Launch Notepad",
                {"command": "notepad.exe", "wait_ms": 1200},
            )
        )
    steps.append(
        _stp(
            "desktop.focus_window",
            "Focus Notepad",
            {"title": notepad_title, "timeout_ms": 15000},
        )
    )
    steps.append(_stp("desktop.wait", "Settle Notepad", {"ms": 400}))

    if mode == "type":
        steps.append(
            _stp(
                "desktop.type_text",
                "Type copied web text",
                {
                    "text": "{{" + save_as + "}}",
                    "window_title": notepad_title,
                    "name": "",
                    "auto_id": "",
                    "control_type": "Edit",
                    "clear": False,
                    "timeout_ms": 30000,
                },
            )
        )
    else:
        steps.append(
            _stp(
                "desktop.paste",
                "Paste into Notepad",
                {
                    "window_title": notepad_title,
                    "from_variable": save_as,
                    "refresh_clipboard": True,
                    "timeout_ms": 15000,
                },
                "Ctrl+V using clipboard (refreshed from variable)",
            )
        )

    return steps
