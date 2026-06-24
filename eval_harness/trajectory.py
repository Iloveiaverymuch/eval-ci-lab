"""
Trajectory reconstruction + token capture for the W04 LangGraph supervisor.

The supervisor tags every worker AIMessage with `name=<worker>`. That tag IS the
observable trajectory: reading the ordered list of names from final_state["messages"]
gives us the exact sequence of workers that ran. We use this for the path/order and
termination assertions. Token usage is captured with a LangChain callback so we never
touch the W04 code.

This module is import-safe with no API keys: the callback and reconstruction logic are
pure functions over a final state dict.
"""

from __future__ import annotations
from typing import Any


# Worker names we expect the supervisor to emit, in canonical order.
WORKERS = ("search_worker", "analyst_worker", "writer_worker")


def worker_sequence(final_state: dict) -> list[str]:
    """Ordered list of worker names that produced messages, e.g.
    ['search_worker', 'analyst_worker', 'writer_worker'].
    Reconstructed purely from the message tags — this is the trajectory."""
    seq = []
    for m in final_state.get("messages", []):
        name = getattr(m, "name", None)
        if name in WORKERS:
            seq.append(name)
    return seq


def step_count(final_state: dict) -> int:
    """Total worker invocations (length of the trajectory). Used for the
    no-infinite-loop / termination assertion."""
    return len(worker_sequence(final_state))


def terminated(final_state: dict) -> bool:
    """A run terminated cleanly iff the supervisor's last routing decision was FINISH
    AND a writer_worker message exists (i.e. it produced the deliverable)."""
    next_val = final_state.get("next", "")
    wrote_report = "writer_worker" in worker_sequence(final_state)
    return next_val == "FINISH" and wrote_report


def final_answer(final_state: dict) -> str:
    """The final deliverable string (last message content)."""
    msgs = final_state.get("messages", [])
    if not msgs:
        return ""
    return getattr(msgs[-1], "content", "") or ""
