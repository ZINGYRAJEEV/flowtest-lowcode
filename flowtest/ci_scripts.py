"""
Generate Jenkins / Azure Pipelines / shell scripts to run a FlowTest suite in CI.

Preferred CI path: run from Git-committed suite.json under tests/
  python -m flowtest.cli run-suite-file --path tests/<project>/<suite>/suite.json
"""

from __future__ import annotations

from typing import Any


def generate_cli_command(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> str:
    if suite_path:
        return " ".join(
            [
                "python -m flowtest.cli run-suite-file",
                f'--path "{suite_path}"',
                f'--env-name "{env_name}"',
                f"--user {user}",
            ]
        )
    parts = [
        "python -m flowtest.cli run-suite",
        f'--suite "{suite}"',
        f'--env-name "{env_name}"',
        f"--user {user}",
    ]
    if project_id:
        parts.append(f"--project-id {project_id}")
    return " ".join(parts)


def generate_shell_script(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> str:
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""#!/usr/bin/env bash
# FlowTest CI runner — suite: {suite} | env: {env_name}
# Steps source: {suite_path or "(SQLite DB — prefer exporting suite.json to Git)"}
set -euo pipefail

echo "==> Installing dependencies"
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium

echo "==> Running FlowTest suite: {suite}"
{cmd}

echo "==> Suite finished"
"""


def generate_powershell_script(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> str:
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""# FlowTest CI runner — suite: {suite} | env: {env_name}
# Steps source: {suite_path or "(SQLite DB — prefer exporting suite.json to Git)"}
$ErrorActionPreference = "Stop"

Write-Host "==> Installing dependencies"
python -m pip install -r requirements.txt
python -m playwright install chromium

Write-Host "==> Running FlowTest suite: {suite}"
{cmd}
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}

Write-Host "==> Suite finished"
"""


def generate_jenkinsfile(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    agent_label: str = "any",
    suite_path: str | None = None,
) -> str:
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""// Jenkins declarative pipeline — FlowTest suite: {suite}
pipeline {{
  agent {{ label '{agent_label}' }}

  options {{
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 60, unit: 'MINUTES')
  }}

  environment {{
    FLOWTEST_SUITE = '{suite}'
    FLOWTEST_ENV = '{env_name}'
    FLOWTEST_SUITE_PATH = '{suite_path or ""}'
    PYTHONUNBUFFERED = '1'
  }}

  stages {{
    stage('Checkout') {{
      steps {{
        checkout scm
      }}
    }}

    stage('Setup') {{
      steps {{
        sh '''
          python -m pip install -r requirements.txt
          python -m playwright install --with-deps chromium
        '''
      }}
    }}

    stage('Run FlowTest suite') {{
      steps {{
        sh '''
          {cmd}
        '''
      }}
    }}
  }}

  post {{
    always {{
      archiveArtifacts artifacts: 'flowtest_data/artifacts/**/*', allowEmptyArchive: true
    }}
    failure {{
      echo "FlowTest suite '${{env.FLOWTEST_SUITE}}' failed on env '${{env.FLOWTEST_ENV}}'"
    }}
    success {{
      echo "FlowTest suite '${{env.FLOWTEST_SUITE}}' passed"
    }}
  }}
}}
"""


def generate_azure_pipelines(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    pool_vm_image: str = "ubuntu-latest",
    suite_path: str | None = None,
) -> str:
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""# Azure Pipelines — FlowTest suite: {suite}
# Test steps come from Git: {suite_path or "export suite.json under tests/ first"}
trigger:
  - main
  - master

pr:
  - main
  - master

pool:
  vmImage: {pool_vm_image}

variables:
  FLOWTEST_SUITE: '{suite}'
  FLOWTEST_ENV: '{env_name}'
  FLOWTEST_SUITE_PATH: '{suite_path or ""}'
  PYTHONUNBUFFERED: '1'

stages:
  - stage: FlowTest
    displayName: FlowTest suite ({suite})
    jobs:
      - job: run_suite
        displayName: Run suite
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: '3.11'
              addToPath: true

          - script: |
              python -m pip install --upgrade pip
              python -m pip install -r requirements.txt
              python -m playwright install --with-deps chromium
            displayName: Install dependencies

          - script: |
              {cmd}
            displayName: Run FlowTest suite '{suite}'
            env:
              FLOWTEST_USER: {user}

          - task: PublishPipelineArtifact@1
            condition: always()
            inputs:
              targetPath: flowtest_data/artifacts
              artifact: flowtest-artifacts
              publishLocation: pipeline
"""


def generate_github_actions(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> str:
    """Bonus: GitHub Actions workflow (often used alongside Jenkins/Azure)."""
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""# GitHub Actions — FlowTest suite: {suite}
name: FlowTest — {suite}

on:
  push:
    branches: [main, master]
  pull_request:
  workflow_dispatch:

jobs:
  flowtest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install -r requirements.txt
          python -m playwright install --with-deps chromium
      - name: Run suite
        run: {cmd}
      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: flowtest-artifacts
          path: flowtest_data/artifacts/
"""


def generate_flowtest_cli_txt(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> str:
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""# FlowTest CLI command
# NOTE: "flowtest.cli" is a Python module inside this project (flowtest/cli.py).
# It is NOT a separate binary. Run it with: python -m flowtest.cli ...
#
# Suite: {suite}
# Environment: {env_name}
# Steps file (commit to Git): {suite_path or "(not set — using SQLite DB)"}
# Project ID: {project_id or "(any)"}

{cmd}
"""


def generate_flowtest_cli_sh(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> str:
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""#!/usr/bin/env bash
# flowtest-cli.sh — runnable wrapper for: python -m flowtest.cli
# Place this file in the FlowTest project root (same folder as requirements.txt), then:
#   chmod +x flowtest-cli.sh && ./flowtest-cli.sh
set -euo pipefail
cd "$(dirname "$0")"
echo "Running FlowTest CLI (suite={suite}, env={env_name})"
{cmd}
"""


def generate_flowtest_cli_cmd(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> str:
    cmd = generate_cli_command(suite, env_name, project_id, user, suite_path)
    return f"""@echo off
REM flowtest-cli.cmd — runnable wrapper for: python -m flowtest.cli
REM Place this file in the FlowTest project root (same folder as requirements.txt), then double-click or run:
REM   flowtest-cli.cmd
cd /d "%~dp0"
echo Running FlowTest CLI (suite={suite}, env={env_name})
{cmd}
if errorlevel 1 exit /b %errorlevel%
"""


def generate_all_ci_scripts(
    suite: str,
    env_name: str,
    project_id: str | None = None,
    project_name: str = "",
    test_ids: list[str] | None = None,
    test_names: list[str] | None = None,
    user: str = "runner",
    suite_path: str | None = None,
) -> dict[str, str]:
    meta = {
        "suite": suite,
        "environment": env_name,
        "project_id": project_id or "",
        "project_name": project_name,
        "suite_path": suite_path or "",
        "user": user,
        "tests": [
            {"id": i, "name": n}
            for i, n in zip(test_ids or [], test_names or [])
        ],
        "cli": generate_cli_command(suite, env_name, project_id, user, suite_path),
        "note": (
            "Commit tests/<project>/<suite>/suite.json to Git. "
            "Azure uses: python -m flowtest.cli run-suite-file --path <suite.json>"
        ),
    }
    import json

    kw = dict(suite=suite, env_name=env_name, project_id=project_id, user=user, suite_path=suite_path)
    return {
        "flowtest-cli.txt": generate_flowtest_cli_txt(**kw),
        "flowtest-cli.sh": generate_flowtest_cli_sh(**kw),
        "flowtest-cli.cmd": generate_flowtest_cli_cmd(**kw),
        "cli.txt": generate_cli_command(suite, env_name, project_id, user, suite_path) + "\n",
        "run-suite.sh": generate_shell_script(**kw),
        "run-suite.ps1": generate_powershell_script(**kw),
        "Jenkinsfile": generate_jenkinsfile(**kw),
        "azure-pipelines.yml": generate_azure_pipelines(**kw),
        "flowtest-ci.yml": generate_github_actions(**kw),
        "suite-manifest.json": json.dumps(meta, indent=2),
        "README-CI.txt": (
            "FlowTest CI exports\n"
            "===================\n\n"
            "WHERE TEST STEPS LIVE FOR GIT\n"
            "-----------------------------\n"
            f"  {suite_path or 'tests/<project>/<suite>/suite.json'}\n\n"
            "Export from UI (CI / Pipelines) or:\n"
            f'  python -m flowtest.cli export-suite --suite "{suite}"'
            + (f' --project-name "{project_name}"' if project_name else "")
            + "\n\n"
            "Azure / local run (reads steps from that JSON file):\n\n"
            f"  {generate_cli_command(suite, env_name, project_id, user, suite_path)}\n\n"
            "Commit the tests/ folder + azure-pipelines.yml. Do NOT rely on flowtest_data/flowtest.db in CI.\n"
        ),
    }
