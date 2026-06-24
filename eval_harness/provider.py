"""
Promptfoo Python provider for the W04 LangGraph supervisor.

Promptfoo calls `call_api(prompt, options, context)` and expects a dict:
    { "output": <str>, "metadata": {...}, "tokenUsage": {...} }

We return the final report as `output` and the full trajectory under `metadata`,
so the deterministic assertions in promptfooconfig.yaml can check:
  - tools called + order   -> metadata.worker_sequence
  - termination / no loops -> metadata.terminated, metadata.step_count
  - token budget           -> metadata.total_tokens (tokenUsage.total)
  - final output contains  -> output

Execution mode:
  - RUN_REAL_SUPERVISOR=1 AND OPENAI_API_KEY present -> run the real W04 graph.
  - otherwise -> deterministic fake (CI-safe, no network, no spend).

The real supervisor is imported by path injection — ZERO changes to W04 code.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path

from trajectory import worker_sequence, step_count, terminated, final_answer

# Path to the W04 langgraph-lab package. Overridable via env for portability/CI.
# This file lives at: AI Formation/W05/D2/eval-ci-lab/eval_harness/provider.py
#   parents[0]=eval_harness [1]=eval-ci-lab [2]=D2 [3]=W05 [4]=AI Formation
# The W04 lab lives at:  AI Formation/W04/D2/langgraph-lab
_DEFAULT_W04 = (
    Path(__file__).resolve().parents[4]
    / "W04" / "D2" / "langgraph-lab"
)
W04_LAB_PATH = Path(os.environ.get("W04_LAB_PATH", str(_DEFAULT_W04)))


def _run_real(question: str) -> tuple[dict, int]:
    """Run the actual compiled W04 supervisor graph. Returns (final_state, total_tokens)."""
    if str(W04_LAB_PATH) not in sys.path:
        sys.path.insert(0, str(W04_LAB_PATH))

    from langchain_core.messages import HumanMessage
    from langchain_core.callbacks import UsageMetadataCallbackHandler
    from supervisor import app  # compiled graph from W04, untouched

    cb = UsageMetadataCallbackHandler()
    final_state = app.invoke(
        {
            "messages": [HumanMessage(content=question)],
            "next": "",
            "final_answer": "",
            "search_iterations": 0,
        },
        config={"recursion_limit": 20, "callbacks": [cb]},
    )
    # UsageMetadataCallbackHandler aggregates per-model usage; sum totals.
    total = 0
    for usage in getattr(cb, "usage_metadata", {}).values():
        total += usage.get("total_tokens", 0)
    return final_state, total


def _run_fake(question: str) -> tuple[dict, int]:
    from fake_supervisor import run_fake
    final_state = run_fake(question)
    # Deterministic token estimate so the budget assertion is meaningful offline:
    # ~ proportional to number of worker steps.
    total = step_count(final_state) * 400
    return final_state, total


def _use_real() -> bool:
    return os.environ.get("RUN_REAL_SUPERVISOR") == "1" and bool(
        os.environ.get("OPENAI_API_KEY")
    )


def call_api(prompt: str, options=None, context=None):
    """Promptfoo entry point."""
    question = prompt
    # Promptfoo may pass vars in context; prefer an explicit 'question' var if present.
    if context and isinstance(context, dict):
        question = context.get("vars", {}).get("question", prompt)

    try:
        if _use_real():
            final_state, total_tokens = _run_real(question)
            mode = "real"
        else:
            final_state, total_tokens = _run_fake(question)
            mode = "fake"
    except Exception as e:  # provider errors must surface as a failing case, not a crash
        return {
            "error": f"supervisor invocation failed: {type(e).__name__}: {e}",
        }

    seq = worker_sequence(final_state)
    return {
        "output": final_answer(final_state),
        "metadata": {
            "mode": mode,
            "worker_sequence": seq,
            "step_count": step_count(final_state),
            "terminated": terminated(final_state),
            "search_iterations": final_state.get("search_iterations", 0),
            "total_tokens": total_tokens,
        },
        "tokenUsage": {"total": total_tokens},
    }
