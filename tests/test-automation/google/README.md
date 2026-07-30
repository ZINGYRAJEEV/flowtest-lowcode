# FlowTest suite: google

Project: **Test automation**

## Run locally / in Azure Pipelines

```bash
python -m flowtest.cli run-suite-file --path "tests/test-automation/google/suite.json" --env-name "Staging"
```

Commit this folder to Git. The pipeline picks up `suite.json` (test steps live here).
