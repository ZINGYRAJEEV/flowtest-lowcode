# FlowTest

Low-code / no-code test automation platform (MVP) aligned to the FlowTest requirements:

- Visual/low-code **Test Builder** (step library: UI, API, assertions, data/ETL, flow, advanced JS)
- **Projects / suites / tags**
- **Environments** with `{{VAR}}` substitution
- On-demand execution + **CLI** for CI (`python -m flowtest.cli`)
- **Runs & reports** (step results, screenshots, CSV export)
- Optional **Monkey Explorer** for exploratory chaos coverage

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

Opens with **no login** (open access for now).

## CI / Pipelines

In the app: **CI / Pipelines** → select suite + environment → **Generate CI scripts**.

Downloads:
- `Jenkinsfile`
- `azure-pipelines.yml`
- `run-suite.sh` / `run-suite.ps1`
- GitHub Actions workflow (bonus)

CLI equivalent:

```bash
python -m flowtest.cli list-suites
python -m flowtest.cli run-suite --suite Smoke --env-name Staging --project-id <ID>
```


### Record locally (headed Playwright)

In **Test Builder**:

1. Enter a **Start URL**
2. Click **Start recording** — a Chromium window opens with a FlowTest banner
3. Click, type, select, and navigate normally
4. **Assertions:** highlight text on the page → click **Assert selection** (or press **A**)
5. Click **Finish recording** in the banner (or close the window)
6. Generated steps appear in the flow (append or replace) — edit, save, and run

### Record for Streamlit Cloud (Chrome extension) — enabled

Cloud cannot open a desktop browser for interactive Playwright recording. Recording is enabled via the Chrome extension:

1. In the Cloud app (**Test Builder**) click **Download Chrome recorder**, or use the `chrome-extension/` folder from this repo
2. Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → select `chrome-extension/`
3. Open your app under test → extension popup → **Start** → interact → **Finish**
4. **Copy JSON** or **Download**
5. In FlowTest → **Import recording** → paste/upload → Save
6. **Run** the test on Cloud headlessly

See `chrome-extension/README.md`.

Recorded actions map to: `ui.goto`, `ui.click`, `ui.click_by_text`, `ui.fill`, `ui.select_by_text`, `assert.text_contains`.


```bash
python -m flowtest.cli list-tests
python -m flowtest.cli list-envs
python -m flowtest.cli run --test-id <ID> --env-name Staging --user runner
```

## Layout

```
app.py                 # Streamlit UI
flowtest/
  models.py
  storage.py           # SQLite
  steps_library.py
  executor.py          # Playwright + httpx + SQL
  cli.py
monkey_engine.py       # Exploratory monkey tool
flowtest_data/         # DB + artifacts (created at runtime)
```

## Requirements coverage (MVP)

| Area | Status |
|------|--------|
| FR-2/3 Step library + form config + advanced JS | Done |
| FR-5 Variables / env overrides | Done |
| FR-6 Assertions (UI + API + row count) | Done |
| FR-7 On-demand + CLI trigger | Done |
| FR-9 Environments | Done |
| FR-10 Screenshots on failure | Done |
| FR-12 Projects / suites / tags | Done |
| FR-13 Version bump on save | Done |
| FR-15 Import/export JSON | Done |
| FR-16/17 Dashboard + run detail | Done |
| FR-20/21/22 Basic SQL + compare counts | Done (SQLite; Postgres/MySQL optional) |
| FR-24/25 RBAC + audit | Done |
| FR-1 Recorder / true drag-drop canvas | Deferred (reorder via Up/Down) |
| FR-8 Parallel browsers | Deferred |
| FR-18 Slack/email | Deferred |
| AI self-healing / mobile | Out of Phase 1 |
