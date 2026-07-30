# FlowTest suite: Default

Project: **google**

## Run locally / in Azure Pipelines

```bash
python -m flowtest.cli run-suite-file --path "tests/google/default/suite.json" --env-name "Staging"
```

Commit this folder to Git. The pipeline picks up `suite.json` (test steps live here).
