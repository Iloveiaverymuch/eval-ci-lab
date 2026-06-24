"""
Deterministic fake supervisor — no LLM, no network.

Why this exists:
- The CI gate must prove its OWN logic on every PR without burning API keys or
  hitting OpenAI/Tavily. A real supervisor run costs money and is non-deterministic.
- This fake reproduces the *shape* of a real final_state (tagged messages, `next`,
  `search_iterations`) so the trajectory/termination/budget assertions exercise real
  code paths.
- It is also the seam we use to inject a deliberate regression (BROKEN_MODE) to prove
  the gate goes red.

The real supervisor is used when RUN_REAL_SUPERVISOR=1 and API keys are present
(see provider.py). Otherwise this fake runs.
"""

from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class _Msg:
    """Mimics a LangChain AIMessage just enough for trajectory reconstruction."""
    content: str
    name: str | None = None


# A canned, deterministic "report" so `contains` assertions are stable.
_CANNED_REPORT = """## Executive Summary
This is a deterministic fixture report produced by the fake supervisor.

## Key Findings
- Finding A
- Finding B

## Analysis
Trade-offs considered.

## Conclusion
Done."""


def run_fake(question: str) -> dict:
    """Return a final_state dict matching the real supervisor's schema.

    Regression injection: set FAKE_BROKEN to one of:
      - "skip_analyst" : drop analyst_worker from the path (wrong trajectory)
      - "no_finish"    : never emit FINISH (termination failure)
      - "loop"         : exceed the step budget (infinite-loop-style regression)
      - "empty_report" : final answer missing required sections (output regression)
    Unset / "" = healthy canonical run.
    """
    broken = os.environ.get("FAKE_BROKEN", "")

    messages = [_Msg(content=question)]  # HumanMessage stand-in (no name)

    if broken == "skip_analyst":
        messages += [
            _Msg(content="search findings", name="search_worker"),
            _Msg(content=_CANNED_REPORT, name="writer_worker"),
        ]
        return {"messages": messages, "next": "FINISH", "search_iterations": 1}

    if broken == "no_finish":
        messages += [
            _Msg(content="search findings", name="search_worker"),
            _Msg(content="analysis SUFFICIENT", name="analyst_worker"),
            _Msg(content=_CANNED_REPORT, name="writer_worker"),
        ]
        return {"messages": messages, "next": "writer_worker", "search_iterations": 1}

    if broken == "loop":
        # 7 worker steps — over budget, simulates a routing loop
        messages += [
            _Msg(content="s", name="search_worker"),
            _Msg(content="a NEEDS_MORE", name="analyst_worker"),
            _Msg(content="s", name="search_worker"),
            _Msg(content="a NEEDS_MORE", name="analyst_worker"),
            _Msg(content="s", name="search_worker"),
            _Msg(content="a NEEDS_MORE", name="analyst_worker"),
            _Msg(content=_CANNED_REPORT, name="writer_worker"),
        ]
        return {"messages": messages, "next": "FINISH", "search_iterations": 3}

    if broken == "empty_report":
        messages += [
            _Msg(content="search findings", name="search_worker"),
            _Msg(content="analysis SUFFICIENT", name="analyst_worker"),
            _Msg(content="(report generation failed)", name="writer_worker"),
        ]
        return {"messages": messages, "next": "FINISH", "search_iterations": 1}

    # healthy canonical run: search -> analyst -> writer -> FINISH
    messages += [
        _Msg(content="search findings on the topic", name="search_worker"),
        _Msg(content="coverage is adequate SUFFICIENT", name="analyst_worker"),
        _Msg(content=_CANNED_REPORT, name="writer_worker"),
    ]
    return {"messages": messages, "next": "FINISH", "search_iterations": 1}
