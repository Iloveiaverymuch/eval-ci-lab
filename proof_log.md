# Proof Log — W05D2 Agent Regression Sentinel (deterministic gate)

Generated: 2026-06-22 15:41 UTC  |  promptfoo 0.121.17

## Healthy run (real config, fake supervisor, CI-safe)
result: 8 passed, 0 failed  |  exit=0 -> CI GREEN

## Regression runs — each must block the PR (non-zero exit)

| injected regression | result | exit | caught by |
|---|---|---|---|
| skip_analyst | 0/8 pass | 100 | bad trajectory: ["search_worker","writer_worker"] |
| no_finish | 0/8 pass | 100 | did not terminate cleanly (next!=FINISH or no report) |
| loop | 0/8 pass | 100 | step budget exceeded: 7 > 5 |
| empty_report | 6/8 pass | 100 | Expected output to contain "## Key Findings" |
