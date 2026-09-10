# CI gate: verify AI-touched changes with FlowTest golden suite.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
$env:PYTHONPATH = "$Root"

$Suite = if ($env:FLOWTEST_VERIFY_SUITE) { $env:FLOWTEST_VERIFY_SUITE } else { "tests/flowtest/ai-verify/suite.json" }
$EnvName = if ($env:FLOWTEST_VERIFY_ENV) { $env:FLOWTEST_VERIFY_ENV } else { "Example Org" }
$Workers = if ($env:FLOWTEST_VERIFY_WORKERS) { $env:FLOWTEST_VERIFY_WORKERS } else { "2" }

$args = @(
  "-m", "flowtest.cli", "verify-gate",
  "--path", $Suite,
  "--env-name", $EnvName,
  "--workers", $Workers,
  "--continue-on-fail"
)
if ($env:FLOWTEST_DIFF_FILE) {
  $args += @("--diff-file", $env:FLOWTEST_DIFF_FILE)
}
if ($env:FLOWTEST_FAIL_ON_WARN -eq "1") {
  $args += "--fail-on-warn"
}

python @args
exit $LASTEXITCODE
