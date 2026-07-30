"""
FlowTest — Low-code / no-code test automation platform (MVP).

Covers Phase-1 requirements: visual step builder, UI + API tests,
environments, on-demand/CLI execution, reporting, and basic RBAC.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from flowtest.executor import execute_test_safe
from flowtest.models import Environment, Project, TestCase, TestStep, new_id, utc_now
from flowtest.steps_library import STEP_LIBRARY, default_config, get_step_def, steps_by_category
from flowtest.storage import (
    add_audit,
    authenticate,
    delete_environment,
    delete_project,
    delete_test,
    export_test_json,
    get_environment,
    get_project,
    get_run,
    get_test,
    import_test_dict,
    init_db,
    list_audit,
    list_environments,
    list_projects,
    list_runs,
    list_tests,
    list_users,
    run_stats,
    save_environment,
    save_project,
    save_test,
    update_user_role,
)

init_db()

# Install Playwright Chromium once per process (required on Streamlit Cloud)
try:
    from flowtest.browser_setup import ensure_playwright_chromium

    ensure_playwright_chromium()
except Exception:
    # Don't block the whole UI if browsers aren't needed yet (API-only use)
    pass

st.set_page_config(
    page_title="FlowTest",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500&display=swap');

:root {
  --ft-bg: #fffcfb;
  --ft-bg-soft: #f7f4f2;
  --ft-bg-muted: #f3eeea;
  --ft-bg-blush: #fff8f6;
  --ft-ink: #241e1b;
  --ft-muted: #756055;
  --ft-line: rgba(36, 30, 27, 0.10);
  --ft-accent: #f83b66;
  --ft-accent-soft: #ffc6d3;
  --ft-accent-mid: #ff9db3;
  --ft-success: #1ebe57;
  --ft-shadow: 0 12px 40px -16px rgba(36, 30, 27, 0.18);
  --ft-shadow-lg: 0 20px 50px -20px rgba(36, 30, 27, 0.22);
  --ft-radius: 16px;
}

/* Fonts — scoped; do NOT style all label/span/div (breaks Streamlit expanders) */
.stApp, .stApp p, .stApp .stMarkdown, .block-container {
  font-family: 'DM Sans', system-ui, sans-serif;
}

.stApp {
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(248, 59, 102, 0.08), transparent 55%),
    radial-gradient(900px 420px at 100% 0%, rgba(255, 198, 211, 0.35), transparent 50%),
    linear-gradient(180deg, #fffcfb 0%, #f7f4f2 100%) !important;
  color: var(--ft-ink);
}

/* Hide default chrome noise */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

.block-container {
  padding-top: 1.5rem !important;
  padding-bottom: 3rem !important;
  max-width: 1180px;
  position: relative;
  z-index: 1;
}

/* Brand / page headers */
.ft-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}
.ft-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(145deg, #f83b66 0%, #ff9db3 100%);
  color: #fff;
  display: grid;
  place-items: center;
  font-family: 'Playfair Display', Georgia, serif !important;
  font-weight: 700;
  font-size: 1.15rem;
  box-shadow: var(--ft-shadow);
}
.hero-title {
  font-family: 'Playfair Display', Georgia, serif !important;
  font-size: clamp(1.85rem, 3vw, 2.45rem);
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
  color: var(--ft-ink);
  margin: 0 0 0.45rem 0;
}
.hero-sub {
  font-size: 1.02rem;
  color: var(--ft-muted);
  margin: 0 0 1.5rem 0;
  max-width: 42rem;
  line-height: 1.55;
}
.ft-kicker {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ft-accent);
  margin-bottom: 0.35rem;
}

/* Cards / panels */
.ft-card {
  background: rgba(255, 252, 251, 0.92);
  border: 1px solid var(--ft-line);
  border-radius: var(--ft-radius);
  padding: 1.25rem 1.35rem;
  box-shadow: var(--ft-shadow);
  backdrop-filter: blur(8px);
}
.ft-panel {
  background: linear-gradient(180deg, #fffcfb 0%, #fff8f6 100%);
  border: 1px solid var(--ft-line);
  border-radius: var(--ft-radius);
  padding: 1.5rem;
  box-shadow: var(--ft-shadow);
}

/* Metric polish */
div[data-testid="stMetric"] {
  background: #fffcfb;
  border: 1px solid var(--ft-line);
  border-radius: 14px;
  padding: 0.9rem 1rem;
  box-shadow: 0 1px 2px rgba(36,30,27,0.04);
}
div[data-testid="stMetric"] label { color: var(--ft-muted) !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-family: 'Playfair Display', Georgia, serif !important;
  color: var(--ft-ink) !important;
}

/* Sidebar — warm dark; contain overflow so nav text never bleeds into main */
section[data-testid="stSidebar"],
div[data-testid="stSidebar"] {
  background:
    radial-gradient(600px 280px at 20% 0%, rgba(248, 59, 102, 0.22), transparent 60%),
    linear-gradient(180deg, #241e1b 0%, #3a2f2a 100%) !important;
  border-right: 1px solid rgba(255,255,255,0.06);
  overflow-x: hidden !important;
  z-index: 100 !important;
}
section[data-testid="stSidebar"] > div {
  overflow-x: hidden !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] label {
  color: #f3eeea !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] {
  overflow: hidden !important;
  width: 100% !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label {
  padding: 0.45rem 0.65rem !important;
  border-radius: 10px !important;
  margin-bottom: 0.15rem !important;
  overflow: hidden !important;
  white-space: nowrap !important;
  text-overflow: ellipsis !important;
  max-width: 100% !important;
  width: 100% !important;
  box-sizing: border-box !important;
  position: relative !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
  background: rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: rgba(248, 59, 102, 0.22) !important;
  box-shadow: inset 3px 0 0 #f83b66;
}

div[data-testid="stAppViewContainer"] > .main {
  position: relative;
  z-index: 1;
  isolation: isolate;
}

/* Buttons */
.stButton > button {
  border-radius: 999px !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em;
  border: 1px solid transparent !important;
  transition: transform .15s ease, box-shadow .15s ease, background .15s ease !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #f83b66 0%, #ff6b8a 100%) !important;
  color: #fff !important;
  box-shadow: 0 10px 24px -12px rgba(248, 59, 102, 0.7) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px -12px rgba(248, 59, 102, 0.85) !important;
}
.stButton > button[kind="secondary"],
.stButton > button:not([kind="primary"]) {
  background: #fffcfb !important;
  color: var(--ft-ink) !important;
  border: 1px solid var(--ft-line) !important;
}
div[data-testid="stSidebar"] .stButton > button {
  background: rgba(255,255,255,0.08) !important;
  color: #fffcfb !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] > div,
.stNumberInput input, .stMultiSelect [data-baseweb="select"] > div {
  border-radius: 12px !important;
  border-color: var(--ft-line) !important;
  background: #fffcfb !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--ft-accent) !important;
  box-shadow: 0 0 0 3px rgba(248, 59, 102, 0.15) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.35rem;
  background: var(--ft-bg-muted);
  padding: 0.35rem;
  border-radius: 999px;
}
.stTabs [data-baseweb="tab"] {
  border-radius: 999px !important;
  padding: 0.45rem 1rem !important;
  font-weight: 600;
  color: var(--ft-muted);
}
.stTabs [aria-selected="true"] {
  background: #fffcfb !important;
  color: var(--ft-ink) !important;
  box-shadow: 0 1px 3px rgba(36,30,27,0.08);
}

/* Expanders — prevent ghost/overlapping label text */
div[data-testid="stExpander"] {
  background: #fffcfb !important;
  border: 1px solid var(--ft-line) !important;
  border-radius: 14px !important;
  margin-bottom: 0.55rem !important;
  overflow: hidden !important;
  position: relative !important;
  z-index: 1 !important;
  isolation: isolate;
  box-shadow: 0 1px 2px rgba(36,30,27,0.04);
}
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] summary {
  position: relative !important;
  overflow: hidden !important;
  background: #fffcfb !important;
}
div[data-testid="stExpander"] summary p,
div[data-testid="stExpander"] summary span {
  position: static !important;
  color: var(--ft-ink) !important;
  background: transparent !important;
}
div[data-testid="stAlert"] {
  border-radius: 14px !important;
}

/* Dataframes */
div[data-testid="stDataFrame"] {
  border: 1px solid var(--ft-line);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: var(--ft-shadow);
}

/* Login hero */
.ft-login-wrap {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 1.5rem;
  align-items: stretch;
  margin-top: 1rem;
}
@media (max-width: 900px) {
  .ft-login-wrap { grid-template-columns: 1fr; }
}
.ft-login-hero {
  background:
    linear-gradient(160deg, rgba(248,59,102,0.12), transparent 45%),
    linear-gradient(180deg, #241e1b 0%, #3a2f2a 100%);
  color: #fffcfb;
  border-radius: 22px;
  padding: 2.25rem 2rem;
  min-height: 420px;
  box-shadow: var(--ft-shadow-lg);
  position: relative;
  overflow: hidden;
}
.ft-login-hero h1 {
  font-family: 'Playfair Display', Georgia, serif !important;
  font-size: 2.4rem;
  line-height: 1.15;
  margin: 0.6rem 0 0.75rem;
  color: #fffcfb !important;
}
.ft-login-hero p { color: rgba(255,252,251,0.78); font-size: 1.05rem; line-height: 1.55; }
.ft-login-hero ul { margin: 1.5rem 0 0; padding-left: 1.1rem; color: rgba(255,252,251,0.85); }
.ft-login-hero li { margin-bottom: 0.45rem; }
.ft-pill {
  display: inline-block;
  padding: 0.28rem 0.7rem;
  border-radius: 999px;
  background: rgba(248,59,102,0.2);
  color: #ffc6d3;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.ft-login-form {
  background: #fffcfb;
  border: 1px solid var(--ft-line);
  border-radius: 22px;
  padding: 1.75rem 1.5rem;
  box-shadow: var(--ft-shadow);
}
.ft-section-label {
  font-family: 'Playfair Display', Georgia, serif !important;
  font-size: 1.15rem;
  color: var(--ft-ink);
  margin: 0.25rem 0 0.75rem;
}
.ft-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--ft-line), transparent);
  margin: 1.25rem 0;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- Auth helpers ----------

PERMISSIONS = {
    "Admin": {"view", "edit", "run", "admin"},
    "Editor": {"view", "edit", "run"},
    "Runner": {"view", "run"},
    "Viewer": {"view"},
}


def can(action: str) -> bool:
    user = st.session_state.get("user")
    if not user:
        return False
    return action in PERMISSIONS.get(user.role, set())


def page_header(title: str, subtitle: str = "", kicker: str = "FlowTest") -> None:
    st.markdown(
        f"""
        <div class="ft-kicker">{kicker}</div>
        <p class="hero-title">{title}</p>
        <p class="hero-sub">{subtitle}</p>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> bool:
    if st.session_state.get("user"):
        return True

    left, right = st.columns([1.2, 0.9], gap="large")
    with left:
        st.markdown(
            """
            <div class="ft-login-hero">
              <span class="ft-pill">Quality engineering</span>
              <h1>Build tests that feel effortless.</h1>
              <p>Low-code automation for UI, API, and data checks — with recording, suites, and CI scripts your team can trust.</p>
              <ul>
                <li>Visual step builder &amp; browser recorder</li>
                <li>Environments, suites, and role-based access</li>
                <li>Jenkins &amp; Azure Pipelines export</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="ft-section-label">Welcome back</div>', unsafe_allow_html=True)
        st.caption("Sign in to continue to your workspace.")
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password", value="admin123")
        if st.button("Sign in", type="primary", use_container_width=True):
            user = authenticate(username.strip(), password)
            if user:
                st.session_state.user = user
                add_audit(user.username, "login", "user", user.id)
                st.rerun()
            st.error("Invalid credentials")
        st.markdown('<div class="ft-divider"></div>', unsafe_allow_html=True)
        st.caption(
            "Demo · `admin/admin123` · `editor/editor123` · `viewer/viewer123` · `runner/runner123`"
        )
    return False


# ---------- Pages ----------


def page_dashboard():
    page_header("Dashboard", "Pass/fail trends, inventory, and recent activity.", "Overview")
    stats = run_stats()
    a, b, c, d = st.columns(4)
    a.metric("Projects", stats["projects"])
    b.metric("Tests", stats["tests"])
    c.metric("Runs", stats["total_runs"])
    d.metric("Pass rate", f"{stats['pass_rate']}%")

    runs = list_runs(limit=50)
    if runs:
        df = pd.DataFrame(
            [
                {
                    "started_at": r.started_at,
                    "status": r.status,
                    "test": r.test_name,
                    "env": r.environment_name,
                    "ms": r.duration_ms,
                }
                for r in runs
            ]
        )
        fig = px.histogram(df, x="status", color="status", title="Recent run outcomes")
        fig.update_layout(
            height=320,
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_family="DM Sans",
            font_color="#241e1b",
            title_font_family="Playfair Display",
        )
        fig.update_traces(marker_color="#f83b66")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No runs yet. Open **Test Builder**, then run a test.")


def page_projects():
    page_header("Projects & suites", "Organize work by product area, then group tests into suites.", "Workspace")
    projects = list_projects()

    if can("edit"):
        with st.expander("Create project", expanded=not projects):
            name = st.text_input("Project name")
            desc = st.text_area("Description")
            tags = st.text_input("Tags (comma-separated)", value="web")
            if st.button("Create project", type="primary") and name.strip():
                p = Project(
                    id=new_id("prj_"),
                    name=name.strip(),
                    description=desc.strip(),
                    tags=[t.strip() for t in tags.split(",") if t.strip()],
                )
                save_project(p)
                add_audit(st.session_state.user.username, "create", "project", p.id, p.name)
                st.success(f"Created {p.name}")
                st.rerun()

    if not projects:
        st.warning("No projects yet.")
        return

    for p in projects:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"### {p.name}")
            c1.caption(p.description or "—")
            c1.write(f"Tags: {', '.join(p.tags) or '—'}")
            tests = list_tests(p.id)
            c2.metric("Tests", len(tests))
            if can("edit") and c3.button("Delete", key=f"del_prj_{p.id}"):
                delete_project(p.id)
                add_audit(st.session_state.user.username, "delete", "project", p.id, p.name)
                st.rerun()
            if tests:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "ID": t.id,
                                "Suite": t.suite,
                                "Name": t.name,
                                "Steps": len(t.steps),
                                "Version": t.version,
                                "Tags": ", ".join(t.tags),
                            }
                            for t in tests
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


def _render_step_editor(step: TestStep, idx: int) -> TestStep:
    meta = get_step_def(step.type)
    label = meta["label"] if meta else step.type
    open_key = f"step_open_{step.id}"
    title = f"{idx + 1}. [{step.type}] {step.name or label}"

    # Use bordered container instead of expander — avoids Streamlit label ghosting/overlap bugs
    with st.container(border=True):
        head_l, head_r = st.columns([5.5, 1])
        with head_l:
            st.markdown(f"**{title}**")
            if step.notes:
                st.caption(step.notes)
        with head_r:
            toggled = st.toggle(
                "Edit",
                value=bool(st.session_state.get(open_key, False)),
                key=f"tog_{step.id}",
                label_visibility="visible",
            )
            st.session_state[open_key] = toggled

        if st.session_state.get(open_key, False):
            step.name = st.text_input("Step name", value=step.name, key=f"nm_{step.id}")
            step.enabled = st.checkbox("Enabled", value=step.enabled, key=f"en_{step.id}")
            step.notes = st.text_input("Notes / annotation", value=step.notes, key=f"nt_{step.id}")
            if meta:
                st.caption(meta["description"])
                for field in meta["fields"]:
                    key = field["key"]
                    fkey = f"{step.id}_{key}"
                    kind = field.get("kind", "text")
                    current = step.config.get(key, field.get("default", ""))
                    if kind == "bool":
                        step.config[key] = st.checkbox(field["label"], value=bool(current), key=fkey)
                    elif kind == "number":
                        step.config[key] = st.number_input(
                            field["label"], value=int(current or 0), key=fkey
                        )
                    elif kind == "select":
                        opts = field.get("options", [])
                        ix = opts.index(current) if current in opts else 0
                        step.config[key] = st.selectbox(field["label"], opts, index=ix, key=fkey)
                    elif kind == "textarea":
                        step.config[key] = st.text_area(
                            field["label"], value=str(current or ""), key=fkey
                        )
                    elif kind == "json":
                        raw = st.text_area(field["label"], value=str(current or "{}"), key=fkey)
                        try:
                            step.config[key] = (
                                json.loads(raw) if raw.strip().startswith("{") else raw
                            )
                        except json.JSONDecodeError:
                            step.config[key] = raw
                            st.warning("Invalid JSON — stored as string")
                    else:
                        step.config[key] = st.text_input(
                            field["label"], value=str(current or ""), key=fkey
                        )
            else:
                step.config = json.loads(
                    st.text_area(
                        "Config JSON",
                        value=json.dumps(step.config, indent=2),
                        key=f"cfg_{step.id}",
                    )
                )
    return step


def page_builder():
    page_header(
        "Test Builder",
        "Assemble low-code steps, record a browser session, then save and run.",
        "Authoring",
    )

    projects = list_projects()
    if not projects:
        st.warning("Create a project first.")
        return

    pc1, pc2 = st.columns([2, 2])
    project = pc1.selectbox("Project", projects, format_func=lambda p: p.name)
    tests = list_tests(project.id)
    mode = pc2.radio("Mode", ["Edit existing", "Create new"], horizontal=True)

    if mode == "Create new":
        if not can("edit"):
            st.error("Editors and Admins can create tests.")
            return
        name = st.text_input("Test name", value="New test flow")
        suite = st.text_input("Suite", value="Default")
        description = st.text_area("Description", value="")
        tags = st.text_input("Tags", value="ui")
        if "draft_steps" not in st.session_state:
            st.session_state.draft_steps = []
        steps: list[TestStep] = st.session_state.draft_steps
        test = TestCase(
            id=new_id("tst_"),
            project_id=project.id,
            name=name,
            description=description,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            steps=steps,
            suite=suite,
            created_by=st.session_state.user.username,
        )
        editing_new = True
    else:
        if not tests:
            st.info("No tests in this project. Switch to Create new.")
            return
        selected = st.selectbox("Test", tests, format_func=lambda t: f"{t.suite} / {t.name} (v{t.version})")
        test = get_test(selected.id) or selected
        editing_new = False
        if "edit_test_id" not in st.session_state or st.session_state.edit_test_id != test.id:
            st.session_state.edit_test_id = test.id
            st.session_state.draft_steps = [
                TestStep(s.id, s.type, s.name, dict(s.config), s.enabled, s.notes) for s in test.steps
            ]
        test.steps = st.session_state.draft_steps

    # ----- Session recorder (FR-1) -----
    st.markdown("#### Record browser session")
    from flowtest.browser_setup import can_record_headed, is_streamlit_cloud

    if not can_record_headed():
        st.warning(
            "**Recording is not available on Streamlit Cloud.** "
            "Cloud apps have no desktop browser window for you to interact with.\n\n"
            "1. Run locally: `streamlit run app.py` → record steps → **Save** the test  \n"
            "2. Or export suite to `tests/` and push to Git  \n"
            "3. On [Streamlit Cloud](https://lowcodetestautomation.streamlit.app/) you can "
            "**run** saved tests headlessly (Playwright Chromium installs automatically)."
        )
    else:
        st.caption(
            "Opens a real browser. Click, type, and navigate as usual. "
            "**To add an assertion:** highlight text on the page, then click **Assert selection** "
            "in the recorder banner (or press **A**). Click **Finish recording** when done."
        )
    if can("edit") and can_record_headed():
        envs_for_rec = list_environments()
        rc1, rc2, rc3 = st.columns([2.2, 1.4, 1])
        with rc1:
            default_start = ""
            if envs_for_rec:
                default_start = envs_for_rec[0].base_url or "https://example.com"
            record_url = st.text_input(
                "Start URL",
                value=st.session_state.get("record_url", default_start or "https://example.com"),
                key="record_url_input",
                help="Page to open when recording starts.",
            )
            st.session_state.record_url = record_url
        with rc2:
            replace_base = st.toggle(
                "Use {{BASE_URL}} for start URL",
                value=True,
                help="If the start URL matches an environment base URL, store navigation as {{BASE_URL}}.",
            )
            rec_env = None
            if replace_base and envs_for_rec:
                rec_env = st.selectbox(
                    "Base environment",
                    envs_for_rec,
                    format_func=lambda e: e.name,
                    key="record_env",
                )
        with rc3:
            replace_mode = st.selectbox(
                "After recording",
                ["Append steps", "Replace all steps"],
                key="record_replace_mode",
            )
            st.write("")
            start_rec = st.button("● Start recording", type="primary", use_container_width=True)

        if start_rec:
            if not (record_url or "").strip():
                st.error("Enter a start URL first.")
            else:
                base_for_replace = rec_env.base_url if (replace_base and rec_env) else None
                with st.spinner(
                    "Recording… A browser window should open. "
                    "Interact with the site, then click **Finish recording** in the dark banner "
                    "(or close the browser window)."
                ):
                    try:
                        from flowtest.recorder import record_browser_session_safe, steps_from_recording

                        result = record_browser_session_safe(
                            start_url=record_url.strip(),
                            replace_base_url=base_for_replace,
                            max_seconds=900,
                        )
                        recorded = steps_from_recording(result)
                        if not recorded:
                            st.warning(
                                "No steps were captured. Try again and interact with the page "
                                "before finishing."
                            )
                        else:
                            if replace_mode == "Replace all steps":
                                st.session_state.draft_steps = recorded
                            else:
                                st.session_state.draft_steps.extend(recorded)
                            add_audit(
                                st.session_state.user.username,
                                "record",
                                "test",
                                getattr(test, "id", ""),
                                f"{len(recorded)} steps from {result.get('start_url')}",
                            )
                            st.success(
                                f"Recorded **{len(recorded)}** step(s) from "
                                f"`{result.get('start_url')}` — review and save below."
                            )
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Recording failed: {exc}")
                        st.info(
                            "A Chromium window should open on your desktop. "
                            "If it does not, run `playwright install chromium`. "
                            "Click **Finish recording** in the dark banner when done."
                        )
    elif can("edit") and is_streamlit_cloud():
        st.caption("Use the step library below to edit tests, or record on your local machine.")
    elif not can("edit"):
        st.info("Editors and Admins can record sessions.")

    st.markdown("#### Step library")
    grouped = steps_by_category()
    cats = list(grouped.keys())
    tabs = st.tabs([c.upper() for c in cats])
    for tab, cat in zip(tabs, cats):
        with tab:
            for meta in grouped[cat]:
                cols = st.columns([4, 1])
                cols[0].markdown(f"**{meta['label']}** — {meta['description']}")
                if can("edit") and cols[1].button("Add", key=f"add_{meta['type']}_{editing_new}"):
                    st.session_state.draft_steps.append(
                        TestStep(
                            id=new_id("stp_"),
                            type=meta["type"],
                            name=meta["label"],
                            config=default_config(meta["type"]),
                        )
                    )
                    st.rerun()

    st.markdown("#### Flow steps")
    if not st.session_state.draft_steps:
        st.info("Add steps from the library above.")
    else:
        for i, step in enumerate(list(st.session_state.draft_steps)):
            st.session_state.draft_steps[i] = _render_step_editor(step, i)
            b1, b2, b3, b4 = st.columns(4)
            if can("edit") and b1.button("↑ Up", key=f"up_{step.id}") and i > 0:
                steps = st.session_state.draft_steps
                steps[i - 1], steps[i] = steps[i], steps[i - 1]
                st.rerun()
            if can("edit") and b2.button("↓ Down", key=f"dn_{step.id}") and i < len(st.session_state.draft_steps) - 1:
                steps = st.session_state.draft_steps
                steps[i + 1], steps[i] = steps[i], steps[i + 1]
                st.rerun()
            if can("edit") and b3.button("Duplicate", key=f"dup_{step.id}"):
                clone = TestStep(
                    id=new_id("stp_"),
                    type=step.type,
                    name=step.name + " (copy)",
                    config=dict(step.config),
                    enabled=step.enabled,
                    notes=step.notes,
                )
                st.session_state.draft_steps.insert(i + 1, clone)
                st.rerun()
            if can("edit") and b4.button("Remove", key=f"rm_{step.id}"):
                st.session_state.draft_steps.pop(i)
                st.rerun()

    st.markdown("#### Save / run / export")
    envs = list_environments()
    env = st.selectbox(
        "Environment",
        envs,
        format_func=lambda e: f"{e.name} ({e.base_url})",
    ) if envs else None
    headless = st.toggle("Headless browser", value=True)
    stop_on_fail = st.toggle("Stop on first failure", value=True)

    c1, c2, c3, c4 = st.columns(4)
    if can("edit") and c1.button("Save test", type="primary"):
        test.steps = st.session_state.draft_steps
        if editing_new:
            if mode == "Create new":
                test.name = name
                test.suite = suite
                test.description = description
                test.tags = [t.strip() for t in tags.split(",") if t.strip()]
            save_test(test, bump_version=False)
            add_audit(st.session_state.user.username, "create", "test", test.id, test.name)
            st.session_state.edit_test_id = test.id
            st.success(f"Saved {test.name} ({test.id})")
        else:
            save_test(test, bump_version=True)
            add_audit(st.session_state.user.username, "update", "test", test.id, f"v{test.version}")
            st.success(f"Updated {test.name} → v{test.version}")
        st.rerun()

    if can("run") and c2.button("▶ Run now"):
        test.steps = st.session_state.draft_steps
        with st.spinner("Executing test…"):
            run = execute_test_safe(
                test,
                env,
                triggered_by=st.session_state.user.username,
                trigger="manual",
                headless=headless,
                stop_on_fail=stop_on_fail,
            )
        add_audit(st.session_state.user.username, "run", "test", test.id, run.status)
        st.session_state.last_run_id = run.id
        if run.status == "PASS":
            st.success(f"PASS in {run.duration_ms} ms — run {run.id}")
        else:
            st.error(f"{run.status} in {run.duration_ms} ms — run {run.id}")
            if run.error:
                st.code(run.error)

    if not editing_new and can("edit") and c3.button("Delete test"):
        delete_test(test.id)
        add_audit(st.session_state.user.username, "delete", "test", test.id, test.name)
        st.session_state.pop("edit_test_id", None)
        st.session_state.draft_steps = []
        st.rerun()

    c4.download_button(
        "Export JSON",
        data=export_test_json(TestCase(
            id=test.id,
            project_id=test.project_id,
            name=test.name if not editing_new or mode != "Create new" else name,
            description=test.description if not editing_new or mode != "Create new" else description,
            tags=test.tags,
            steps=st.session_state.draft_steps,
            suite=test.suite if not editing_new or mode != "Create new" else suite,
        )),
        file_name=f"{test.id or 'test'}.json",
        mime="application/json",
    )

    if can("edit"):
        with st.expander("Import test JSON into this project"):
            uploaded = st.file_uploader("JSON file", type=["json"])
            if uploaded and st.button("Import"):
                data = json.loads(uploaded.read().decode("utf-8"))
                imported = import_test_dict(data, project.id, st.session_state.user.username)
                add_audit(st.session_state.user.username, "import", "test", imported.id, imported.name)
                st.success(f"Imported {imported.name}")
                st.rerun()

    if st.session_state.get("last_run_id"):
        run = get_run(st.session_state.last_run_id)
        if run:
            st.markdown("#### Last run detail")
            st.write(f"**{run.status}** · {run.test_name} · {run.environment_name} · {run.duration_ms} ms")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Step": s.step_name,
                            "Type": s.step_type,
                            "Status": s.status,
                            "Detail": s.detail,
                            "ms": s.duration_ms,
                        }
                        for s in run.step_results
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
            for s in run.step_results:
                if s.screenshot:
                    st.image(s.screenshot, caption=f"{s.step_name} screenshot", width=480)


def page_environments():
    page_header(
        "Environments",
        "Per-environment base URL and variable overrides — use {{VAR}} in steps.",
        "Config",
    )
    envs = list_environments()
    for env in envs:
        with st.container(border=True):
            st.markdown(f"### {env.name}")
            if can("edit"):
                env.base_url = st.text_input("Base URL", value=env.base_url, key=f"bu_{env.id}")
                raw = st.text_area(
                    "Variables (JSON)",
                    value=json.dumps(env.variables, indent=2),
                    key=f"vars_{env.id}",
                )
                b1, b2 = st.columns(2)
                if b1.button("Save", key=f"save_env_{env.id}"):
                    try:
                        env.variables = json.loads(raw)
                        save_environment(env)
                        add_audit(st.session_state.user.username, "update", "environment", env.id, env.name)
                        st.success("Saved")
                    except json.JSONDecodeError:
                        st.error("Invalid JSON")
                if b2.button("Delete", key=f"del_env_{env.id}"):
                    delete_environment(env.id)
                    st.rerun()
            else:
                st.write(f"Base URL: `{env.base_url}`")
                st.json(env.variables)

    if can("edit"):
        with st.expander("Add environment"):
            name = st.text_input("Name", key="new_env_name")
            base = st.text_input("Base URL", key="new_env_base", value="https://example.com")
            vars_raw = st.text_area("Variables JSON", value='{"API_BASE": "https://httpbin.org"}', key="new_env_vars")
            if st.button("Create environment") and name.strip():
                env = Environment(
                    id=new_id("env_"),
                    name=name.strip(),
                    base_url=base.strip(),
                    variables=json.loads(vars_raw),
                )
                save_environment(env)
                add_audit(st.session_state.user.username, "create", "environment", env.id, env.name)
                st.rerun()


def page_runs():
    page_header(
        "Runs & reports",
        "Inspect outcomes, step details, screenshots, and export CSV for stakeholders.",
        "Insights",
    )
    runs = list_runs(limit=200)
    if not runs:
        st.info("No runs yet.")
        return

    df = pd.DataFrame(
        [
            {
                "Run ID": r.id,
                "Test": r.test_name,
                "Status": r.status,
                "Env": r.environment_name,
                "Trigger": r.trigger,
                "By": r.triggered_by,
                "Started": r.started_at,
                "Duration ms": r.duration_ms,
            }
            for r in runs
        ]
    )
    status_filter = st.multiselect("Filter status", sorted(df["Status"].unique()), default=list(df["Status"].unique()))
    view = df[df["Status"].isin(status_filter)]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button(
        "Export CSV",
        data=view.to_csv(index=False),
        file_name="flowtest_runs.csv",
        mime="text/csv",
    )

    run_id = st.selectbox("Inspect run", [r.id for r in runs], format_func=lambda rid: next(f"{x.status} · {x.test_name} · {x.id}" for x in runs if x.id == rid))
    run = get_run(run_id)
    if run:
        st.write(f"**{run.status}** · {run.test_name} · env `{run.environment_name}` · {run.duration_ms} ms · trigger `{run.trigger}`")
        if run.error:
            st.error(run.error)
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Step": s.step_name,
                        "Type": s.step_type,
                        "Status": s.status,
                        "Detail": s.detail,
                        "ms": s.duration_ms,
                    }
                    for s in run.step_results
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        for s in run.step_results:
            if s.screenshot:
                st.image(s.screenshot, caption=s.step_name, width=520)


def page_ci_pipelines():
    page_header(
        "CI / Pipelines",
        "Export suite steps to Git (`tests/.../suite.json`), then generate Azure/Jenkins scripts that run them.",
        "Delivery",
    )

    projects = list_projects()
    if not projects:
        st.warning("Create a project and tests first.")
        return

    envs = list_environments()
    if not envs:
        st.warning("Create an environment first.")
        return

    # Build suite inventory
    all_tests = list_tests()
    suites_map: dict[tuple[str, str], list] = {}
    for t in all_tests:
        suites_map.setdefault((t.project_id, t.suite), []).append(t)

    if not suites_map:
        st.info("No suites yet. Create tests in Test Builder (each test has a Suite field).")
        return

    project_by_id = {p.id: p for p in projects}
    suite_options = []
    for (pid, suite), tests in sorted(
        suites_map.items(),
        key=lambda x: (
            project_by_id[x[0][0]].name if x[0][0] in project_by_id else "",
            x[0][1],
        ),
    ):
        pname = project_by_id[pid].name if pid in project_by_id else pid
        suite_options.append(
            {
                "key": f"{pid}::{suite}",
                "label": f"{pname} / {suite} ({len(tests)} tests)",
                "project_id": pid,
                "project_name": pname,
                "suite": suite,
                "tests": tests,
            }
        )

    c1, c2 = st.columns(2)
    selected = c1.selectbox(
        "Test suite",
        suite_options,
        format_func=lambda o: o["label"],
    )
    env = c2.selectbox("Environment", envs, format_func=lambda e: f"{e.name} ({e.base_url})")

    c3, c4 = st.columns(2)
    ci_user = c3.text_input("CI user (audit)", value="runner")
    agent_hint = c4.text_input("Jenkins agent label", value="any")

    st.markdown("#### Suite contents")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": t.id,
                    "Name": t.name,
                    "Steps": len(t.steps),
                    "Tags": ", ".join(t.tags),
                    "Version": t.version,
                }
                for t in selected["tests"]
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    from flowtest.ci_scripts import (
        generate_all_ci_scripts,
        generate_cli_command,
        generate_jenkinsfile,
    )
    from flowtest.suite_io import export_suite_to_files, suite_file
    from pathlib import Path
    import io
    import zipfile

    # Git-friendly path where Azure will read test steps
    suite_json_path = suite_file(selected["project_name"], selected["suite"])
    suite_path_rel = suite_json_path.as_posix()
    # Prefer path relative to project root for pipelines
    try:
        suite_path_rel = suite_json_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        pass

    st.markdown("#### Where test steps live for Git")
    st.success(
        f"Commit this file (and its folder): `{suite_path_rel}`  \n"
        "That JSON holds every step. Azure Pipelines should **not** use `flowtest_data/flowtest.db`."
    )

    exp1, exp2 = st.columns(2)
    if exp1.button("Export suite steps to tests/ (for Git)", type="primary", key="btn_export_suite_git"):
        out = export_suite_to_files(
            project_name=selected["project_name"],
            suite=selected["suite"],
            tests=selected["tests"],
            environment_name=env.name,
            project_id=selected["project_id"],
        )
        add_audit(
            st.session_state.user.username,
            "export_suite_git",
            "suite",
            selected["project_id"],
            str(out),
        )
        st.session_state.suite_export_path = str(out)
        st.success(f"Exported steps to `{out}` — push the `tests/` folder to Git.")
        st.rerun()
    if suite_json_path.is_file():
        exp2.info(f"Already on disk: `{suite_path_rel}`")
    else:
        exp2.warning("Not exported yet — click the button first, then commit `tests/`.")

    scripts = generate_all_ci_scripts(
        suite=selected["suite"],
        env_name=env.name,
        project_id=selected["project_id"],
        project_name=selected["project_name"],
        test_ids=[t.id for t in selected["tests"]],
        test_names=[t.name for t in selected["tests"]],
        user=ci_user.strip() or "runner",
        suite_path=suite_path_rel,
    )
    scripts["Jenkinsfile"] = generate_jenkinsfile(
        selected["suite"],
        env.name,
        selected["project_id"],
        ci_user.strip() or "runner",
        agent_label=agent_hint.strip() or "any",
        suite_path=suite_path_rel,
    )

    cli_cmd = generate_cli_command(
        selected["suite"],
        env.name,
        selected["project_id"],
        ci_user.strip() or "runner",
        suite_path=suite_path_rel,
    )

    st.markdown("#### FlowTest CLI (runs from suite.json)")
    st.info(
        "Azure / Jenkins run this command after checkout. Steps are read from the committed "
        f"`{suite_path_rel}` file — not from the local SQLite DB."
    )
    st.code(cli_cmd, language="bash")

    cli_dl1, cli_dl2, cli_dl3 = st.columns(3)
    cli_dl1.download_button(
        "Download flowtest-cli.cmd",
        data=scripts["flowtest-cli.cmd"],
        file_name="flowtest-cli.cmd",
        mime="text/plain",
        use_container_width=True,
        key="dl_flowtest_cli_cmd_live",
        type="primary",
    )
    cli_dl2.download_button(
        "Download flowtest-cli.sh",
        data=scripts["flowtest-cli.sh"],
        file_name="flowtest-cli.sh",
        mime="text/x-shellscript",
        use_container_width=True,
        key="dl_flowtest_cli_sh_live",
    )
    cli_dl3.download_button(
        "Download flowtest-cli.txt",
        data=scripts["flowtest-cli.txt"],
        file_name="flowtest-cli.txt",
        mime="text/plain",
        use_container_width=True,
        key="dl_flowtest_cli_txt_live",
    )

    def _zip_bytes(files: dict[str, str]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return buf.getvalue()

    if st.button("Generate CI scripts", type="primary"):
        # Always refresh suite.json so Git + Azure have current steps
        out = export_suite_to_files(
            project_name=selected["project_name"],
            suite=selected["suite"],
            tests=selected["tests"],
            environment_name=env.name,
            project_id=selected["project_id"],
        )
        st.session_state.suite_export_path = str(out)
        st.session_state.ci_scripts = scripts
        st.session_state.ci_suite_label = selected["label"]
        safe_suite = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in selected["suite"])
        export_dir = Path("flowtest_data") / "ci_exports" / safe_suite
        export_dir.mkdir(parents=True, exist_ok=True)
        for name, content in scripts.items():
            (export_dir / name).write_text(content, encoding="utf-8")
        zip_path = export_dir / "flowtest-ci-bundle.zip"
        zip_path.write_bytes(_zip_bytes(scripts))
        st.session_state.ci_export_dir = str(export_dir.resolve())
        st.session_state.ci_zip_bytes = _zip_bytes(scripts)
        add_audit(
            st.session_state.user.username,
            "generate_ci",
            "suite",
            selected["project_id"],
            f"{selected['suite']} @ {env.name} → {out}",
        )
        st.success(
            f"Exported steps to `{out}` and generated CI scripts. "
            f"Commit **`tests/`** + **`azure-pipelines.yml`** to Git."
        )
        st.rerun()

    generated = st.session_state.get("ci_scripts")
    if generated:
        st.markdown(f"#### Downloads — {st.session_state.get('ci_suite_label', 'suite')}")
        export_path = st.session_state.get("ci_export_dir")
        if export_path:
            st.info(
                f"On disk: `{export_path}`  \n"
                f"Look for **flowtest-cli.cmd**, **flowtest-cli.sh**, **flowtest-cli.txt**"
            )

        zip_data = st.session_state.get("ci_zip_bytes") or _zip_bytes(generated)
        st.download_button(
            "Download all as ZIP (flowtest-ci-bundle.zip)",
            data=zip_data,
            file_name="flowtest-ci-bundle.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_ci_zip",
            type="primary",
        )

        d0a, d0b, d0c = st.columns(3)
        d0a.download_button(
            "flowtest-cli.cmd",
            data=generated.get("flowtest-cli.cmd", scripts["flowtest-cli.cmd"]),
            file_name="flowtest-cli.cmd",
            mime="text/plain",
            use_container_width=True,
            key="dl_flowtest_cli_cmd",
        )
        d0b.download_button(
            "flowtest-cli.sh",
            data=generated.get("flowtest-cli.sh", scripts["flowtest-cli.sh"]),
            file_name="flowtest-cli.sh",
            mime="text/x-shellscript",
            use_container_width=True,
            key="dl_flowtest_cli_sh",
        )
        d0c.download_button(
            "flowtest-cli.txt",
            data=generated.get("flowtest-cli.txt", scripts["flowtest-cli.txt"]),
            file_name="flowtest-cli.txt",
            mime="text/plain",
            use_container_width=True,
            key="dl_flowtest_cli_txt",
        )

        d1, d2, d3 = st.columns(3)
        d1.download_button(
            "Jenkinsfile",
            data=generated["Jenkinsfile"],
            file_name="Jenkinsfile",
            mime="text/plain",
            use_container_width=True,
            key="dl_jenkins",
        )
        d2.download_button(
            "azure-pipelines.yml",
            data=generated["azure-pipelines.yml"],
            file_name="azure-pipelines.yml",
            mime="text/yaml",
            use_container_width=True,
            key="dl_azure",
        )
        d3.download_button(
            "GitHub Actions workflow",
            data=generated["flowtest-ci.yml"],
            file_name="flowtest-ci.yml",
            mime="text/yaml",
            use_container_width=True,
            key="dl_gha",
        )

        d4, d5, d6 = st.columns(3)
        d4.download_button(
            "run-suite.sh",
            data=generated["run-suite.sh"],
            file_name="run-suite.sh",
            mime="text/x-shellscript",
            use_container_width=True,
            key="dl_sh",
        )
        d5.download_button(
            "run-suite.ps1",
            data=generated["run-suite.ps1"],
            file_name="run-suite.ps1",
            mime="text/plain",
            use_container_width=True,
            key="dl_ps1",
        )
        d6.download_button(
            "suite-manifest.json",
            data=generated["suite-manifest.json"],
            file_name="suite-manifest.json",
            mime="application/json",
            use_container_width=True,
            key="dl_manifest",
        )

        preview = st.selectbox(
            "Preview file",
            [
                "flowtest-cli.cmd",
                "flowtest-cli.sh",
                "flowtest-cli.txt",
                "README-CI.txt",
                "Jenkinsfile",
                "azure-pipelines.yml",
                "flowtest-ci.yml",
                "run-suite.sh",
                "run-suite.ps1",
                "suite-manifest.json",
            ],
        )
        lang = {
            "flowtest-cli.cmd": "batch",
            "flowtest-cli.sh": "bash",
            "flowtest-cli.txt": "bash",
            "README-CI.txt": "text",
            "Jenkinsfile": "groovy",
            "azure-pipelines.yml": "yaml",
            "flowtest-ci.yml": "yaml",
            "run-suite.sh": "bash",
            "run-suite.ps1": "powershell",
            "suite-manifest.json": "json",
        }.get(preview, "text")
        st.code(generated.get(preview, scripts.get(preview, "")), language=lang)

        with st.expander("How to use with Git + Azure"):
            st.markdown(
                f"""
1. Click **Export suite steps to tests/** (or **Generate CI scripts**) — this writes:
   `{suite_path_rel}`
2. Commit and push the `tests/` folder (and `azure-pipelines.yml` if you use it).
3. Azure Pipeline runs:

```bash
{cli_cmd}
```

That command reads **steps from the JSON file in Git**, not from `flowtest_data/flowtest.db`.

`flowtest.cli` lives at `flowtest/cli.py` in the repo — you do not download that module separately.
                """
            )


def page_admin():
    page_header(
        "Users, roles & audit",
        "Govern access with Admin, Editor, Runner, and Viewer roles.",
        "Governance",
    )
    if not can("admin"):
        st.warning("Admin only.")
        st.markdown("#### Audit log (read-only for non-admins is hidden)")
        return

    users = list_users()
    st.markdown("#### Users")
    for u in users:
        cols = st.columns([2, 2, 2])
        cols[0].write(f"**{u.username}** — {u.display_name}")
        role = cols[1].selectbox(
            "Role",
            ["Admin", "Editor", "Runner", "Viewer"],
            index=["Admin", "Editor", "Runner", "Viewer"].index(u.role),
            key=f"role_{u.id}",
        )
        if cols[2].button("Update role", key=f"upd_{u.id}"):
            update_user_role(u.id, role)
            add_audit(st.session_state.user.username, "role_change", "user", u.id, f"{u.username}→{role}")
            st.success("Updated")
            st.rerun()

    st.markdown("#### Audit log")
    audit = list_audit(100)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "When": a.created_at,
                    "Actor": a.actor,
                    "Action": a.action,
                    "Entity": f"{a.entity_type}:{a.entity_id}",
                    "Detail": a.detail,
                }
                for a in audit
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### CI / CLI trigger")
    st.code(
        "python -m flowtest.cli list-tests\n"
        "python -m flowtest.cli run --test-id <ID> --env-name Staging --user runner",
        language="bash",
    )


def page_monkey():
    """Optional exploratory monkey tool (kept from earlier work)."""
    page_header(
        "Monkey explorer",
        "Exploratory chaos testing — assess a URL and generate coverage cases.",
        "Explore",
    )
    try:
        import importlib
        import monkey_engine as me

        me = importlib.reload(me)
    except Exception as exc:
        st.error(f"Monkey engine unavailable: {exc}")
        return

    url = st.text_input("URL", value="https://example.com")
    headless = st.toggle("Headless", value=True, key="monk_headless")
    if st.button("Assess & generate", type="primary"):
        with st.spinner("Assessing…"):
            try:
                assessment = me.assess_webpage_safe(url, headless=headless)
                cases = me.generate_monkey_test_cases(assessment, max_coverage=True)
                st.session_state.monk_assessment = assessment
                st.session_state.monk_cases = cases
                st.success(f"{len(assessment.elements)} elements · {len(cases)} cases")
            except Exception as exc:
                st.error(me.format_exception(exc))

    assessment = st.session_state.get("monk_assessment")
    cases = st.session_state.get("monk_cases") or []
    if assessment and cases:
        st.dataframe(me.cases_to_dataframe(cases), use_container_width=True, hide_index=True)
        pick = st.multiselect("Run cases", [c.id for c in cases], default=[c.id for c in cases[:3]])
        if can("run") and st.button("Run selected monkey cases") and pick:
            to_run = [c for c in cases if c.id in pick]
            results = me.execute_selected_cases_safe(to_run, assessment.url, headless=headless)
            st.session_state.monk_results = results
        results = st.session_state.get("monk_results") or []
        if results:
            st.dataframe(
                pd.DataFrame(
                    [{"ID": r.test_id, "Name": r.test_name, "Status": r.status, "ms": r.duration_ms} for r in results]
                ),
                use_container_width=True,
                hide_index=True,
            )


# ---------- Shell ----------

if not require_login():
    st.stop()

user = st.session_state.user
with st.sidebar:
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:0.7rem;margin:0.35rem 0 1rem;">
          <div style="width:38px;height:38px;border-radius:12px;background:linear-gradient(145deg,#f83b66,#ff9db3);
            display:grid;place-items:center;font-family:Playfair Display,Georgia,serif;font-weight:700;color:#fff;">F</div>
          <div>
            <div style="font-family:Playfair Display,Georgia,serif;font-size:1.25rem;line-height:1.1;color:#fffcfb;">FlowTest</div>
            <div style="font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;opacity:0.7;">Low-code quality lab</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{user.display_name} · **{user.role}**")
    st.markdown("---")
    pages = [
        "Dashboard",
        "Projects",
        "Test Builder",
        "Environments",
        "Runs & Reports",
        "CI / Pipelines",
        "Monkey Explorer",
        "Admin",
    ]
    page = st.radio("Navigate", pages, label_visibility="collapsed")
    st.markdown("---")
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()

if page == "Dashboard":
    page_dashboard()
elif page == "Projects":
    page_projects()
elif page == "Test Builder":
    page_builder()
elif page == "Environments":
    page_environments()
elif page == "Runs & Reports":
    page_runs()
elif page == "CI / Pipelines":
    page_ci_pipelines()
elif page == "Monkey Explorer":
    page_monkey()
elif page == "Admin":
    page_admin()
