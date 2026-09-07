# FlowTest suite: UI Coverage

Project: **TUI**

## Run locally / in Azure Pipelines

```bash
python -m flowtest.cli run-suite-file --path "tests/tui/ui-coverage/suite.json" --env-name "TUI Prod"
```

Commit this folder to Git. The pipeline picks up `suite.json` (test steps live here).
