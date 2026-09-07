# FlowTest MCP server

Expose FlowTest to Cursor (and other MCP clients): list/run tests, import Chrome recordings, export suites.

## Install (local only)

```bash
pip install -r requirements-mcp.txt
```

Do **not** add this to Streamlit Cloud `requirements.txt`.

## Run manually

```bash
python -m flowtest.mcp_server
```

(Uses stdio — Cursor starts this for you when configured.)

## Cursor setup

This repo includes `.cursor/mcp.json`. After installing deps:

1. Reload Cursor / enable the **flowtest** MCP server when prompted
2. In chat, ask e.g. “List FlowTest projects” or “Run test tst_… on Staging”

If `cwd` resolution fails on your Cursor version, set an absolute path:

```json
{
  "mcpServers": {
    "flowtest": {
      "command": "python",
      "args": ["-m", "flowtest.mcp_server"],
      "cwd": "C:/Users/Rajeev Kumar/Desktop/webapptestautomation"
    }
  }
}
```

## Tools

| Tool | Purpose |
|------|---------|
| `list_projects` | Projects |
| `list_environments` | Envs / base URLs |
| `list_tests` / `get_test` | Inventory + full steps |
| `list_suites` | Suites + counts |
| `list_runs` / `get_run` | Recent runs + step report |
| `run_test` | Execute a saved test |
| `import_recording` | Chrome extension JSON → test |
| `export_suite` | Write `tests/.../suite.json` |
| `list_suite_files` | Existing exported suites |
| `desktop_list_windows` | Open window titles (Windows local) |
| `desktop_focus_window` | Bring app window to front |
| `desktop_click` / `desktop_type_text` / `desktop_send_keys` | Drive desktop UI |
| `desktop_screenshot` | Full-screen capture to artifacts |

Desktop tools need:

```bash
pip install -r requirements-desktop.txt
```

(Windows only; not available on Streamlit Cloud.)

## Example prompts

- “List all FlowTest tests and their step counts”
- “Get test `<id>` and suggest more stable selectors”
- “Import this recording JSON into project `<id>` as ‘Login smoke’”
- “Run that test on Staging and summarize failures”
- “Export suite Smoke for Git”
- “List desktop windows and focus Notepad”
- “Type Hello into Notepad and take a desktop screenshot”
