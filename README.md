# Agent Regression Sentinel — Deterministic CI Eval Gate (W05D2)

A CI gate that **blocks a PR** when the W04 LangGraph supervisor regresses on its
*trajectory* or *output* — not just its final answer. This is the spine of the
Agent Regression Sentinel MVP.

> Stack decision (W05D1): **Promptfoo** primary (CI-native, OSS, repo-resident config),
> calibration to live in **Langfuse**. This day builds the deterministic gate.
> LLM-as-judge is deliberately **not** here yet — gate first, judge second (D3).

## What it checks (per frozen case)

| # | Criterion | Source of truth | Catches |
|---|-----------|-----------------|---------|
| 1 | Tools called + order | `metadata.worker_sequence` (ordered subsequence) | wrong routing, skipped specialist |
| 2 | Termination / no loops | `metadata.terminated` + `step_count ≤ 5` | non-termination, routing loops |
| 3 | Token budget | `metadata.total_tokens ≤ 8000` | "right answer, expensive path" |
| 4 | Output contains | required report sections in `output` | empty/malformed deliverable |

Assertions 1–3 apply to every case via `defaultTest`; assertion 4 is added to the
cases where output content matters.

## Architecture

```
promptfooconfig.yaml ──► file://eval_harness/provider.py
                              │
                              ├─ RUN_REAL_SUPERVISOR=1 + OPENAI_API_KEY
                              │     └─► imports W04/D2/langgraph-lab/supervisor (UNCHANGED)
                              │         runs compiled graph, captures tokens via callback
                              │
                              └─ otherwise (CI default)
                                    └─► deterministic fake supervisor (no network, no spend)

provider returns:  output=<final report str>   context.metadata={worker_sequence, step_count, terminated, total_tokens}
                                                         ▲
                          javascript asserts read context.metadata (verified empirically)
```

Key design choices:
- **Zero changes to W04 code** — the real supervisor is imported by path injection
  (`W04_LAB_PATH`); tokens captured with a LangChain `UsageMetadataCallbackHandler`.
- **CI-safe by default** — runs a deterministic fake supervisor so the gate's own
  logic is proven on every PR for **free**. Real runs are opt-in (nightly / secrets).
- **Ordered-subsequence trajectory check**, not strict equality — a legitimate extra
  search loop (`analyst → NEEDS_MORE → search`) must NOT trip the gate. Avoids false reds.

## Run locally

```bash
pip install -r requirements.txt
npx promptfoo@latest eval -c promptfooconfig.yaml      # green: exit 0
npx promptfoo@latest view                              # inspect results UI

# prove it goes red (inject a regression into the fake supervisor):
FAKE_BROKEN=loop        npx promptfoo@latest eval -c promptfooconfig.yaml   # step budget -> exit 100
FAKE_BROKEN=skip_analyst npx promptfoo@latest eval -c promptfooconfig.yaml  # trajectory  -> exit 100
FAKE_BROKEN=no_finish   npx promptfoo@latest eval -c promptfooconfig.yaml   # termination -> exit 100
FAKE_BROKEN=empty_report npx promptfoo@latest eval -c promptfooconfig.yaml  # output      -> exit 100
```

## Proof (this is the demoable artifact)

| Scenario | Pass/Fail | CLI exit | Caught by |
|----------|-----------|----------|-----------|
| healthy | 8/8 pass | 0 | — |
| `skip_analyst` | 0/8 | 100 | trajectory: `["search_worker","writer_worker"]` |
| `no_finish` | 0/8 | 100 | termination: next != FINISH |
| `loop` | 0/8 | 100 | step budget: 7 > 5 |
| `empty_report` | 6/8 | 100 | output: missing `## Key Findings` (only the 2 content-checked cases) |

`empty_report` failing **only** the 2 cases with `contains` checks (not all 8) shows
the gate is targeted — no false positives.

## CI

`.github/workflows/eval-gate.yml` runs the gate on every PR to `main`. promptfoo's
non-zero exit fails the job; make it a **required status check** in branch protection
to actually block merges.

## Files

```
W05/D2/
├── promptfooconfig.yaml          # the gate: providers, assertions, frozen cases
├── eval_harness/
│   ├── provider.py               # promptfoo Python provider (real | fake)
│   ├── trajectory.py             # reconstruct path/termination from message tags
│   └── fake_supervisor.py        # deterministic fixture + regression injection
├── .github/workflows/eval-gate.yml
├── requirements.txt
└── README.md
```

## Next (D3)

Add one **Haiku LLM-as-judge** assertion (faithfulness / task-completion), scoped to
merge-to-main, then **calibrate** it against human labels in Langfuse (Cohen's κ ≥ 0.7)
before it's allowed to gate.
