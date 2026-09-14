"""
Structural CDC lint. Deliberately simple and rule-based -- this is not a
formal CDC signoff tool, and the write-up should say so explicitly (see
Section E of the blueprint: "state this limitation plainly rather than
overclaiming coverage").

What it actually does: builds a map of {signal -> clock domain it's
registered in}, then flags any signal that is read by an always-block
clocked on a *different* domain without passing through a name pattern
that indicates a synchronizer (e.g. `_sync0`, `_sync1`, `_ff1`, `_ff2`,
or a module instance named like `*sync*` / `*fifo*`).

This catches the obvious, common mistake (a raw crossing with no
synchronizer at all) which is exactly the kind of thing an LLM refactor
can introduce by accident while "simplifying" logic. It will not catch
subtle reconvergence -- flag that as a known gap, not a solved problem.
"""

from __future__ import annotations
import re
from dataclasses import dataclass


SYNC_HINT_PATTERN = re.compile(r"(sync\d?|_ff1|_ff2|fifo)", re.IGNORECASE)
ALWAYS_BLOCK = re.compile(
    r"always\s*@\s*\(\s*posedge\s+(\w+)[^)]*\)\s*(?:begin)?(.*?)(?=always\s*@|\Z)",
    re.DOTALL,
)
ASSIGN_LHS = re.compile(r"(\w+)\s*<=")
ASSIGN_PAIR = re.compile(r"(\w+)\s*<=\s*(\w+)\s*;")
IDENTIFIER = re.compile(r"\b([A-Za-z_]\w*)\b")


def _first_stage_is_synchronized(sig: str, body: str) -> bool:
    """A crossing is considered synchronized if the FIRST register that
    directly samples `sig` inside this always block has a sync-hinted name
    (e.g. `captured_sync1 <= captured;`). This matters because the raw
    crossing signal itself is never expected to carry a sync-sounding name
    -- only its destination flop is. Checking the signal's own name (the
    naive approach) produces a false positive on every correctly-built
    synchronizer, which is worse than missing a real bug."""
    for lhs, rhs in ASSIGN_PAIR.findall(body):
        if rhs == sig and SYNC_HINT_PATTERN.search(lhs):
            return True
    return False


@dataclass
class CDCFinding:
    signal: str
    driving_clock: str
    consuming_clock: str
    note: str


def _extract_domain_map(rtl_text: str) -> dict[str, str]:
    """signal_name -> clock it is registered on (first assignment wins)."""
    domain_map: dict[str, str] = {}
    for clk, body in ALWAYS_BLOCK.findall(rtl_text):
        for lhs in ASSIGN_LHS.findall(body):
            domain_map.setdefault(lhs, clk)
    return domain_map


def check_cdc(rtl_text: str) -> list[CDCFinding]:
    domain_map = _extract_domain_map(rtl_text)
    findings: list[CDCFinding] = []

    for clk, body in ALWAYS_BLOCK.findall(rtl_text):
        used_signals = set(IDENTIFIER.findall(body)) - {clk}
        for sig in used_signals:
            driving_clk = domain_map.get(sig)
            if driving_clk and driving_clk != clk:
                if SYNC_HINT_PATTERN.search(sig) or _first_stage_is_synchronized(sig, body):
                    continue  # already synchronized, or is itself a synchronizer stage
                findings.append(CDCFinding(
                    signal=sig,
                    driving_clock=driving_clk,
                    consuming_clock=clk,
                    note=(
                        f"'{sig}' is registered on '{driving_clk}' but read inside an "
                        f"always block clocked on '{clk}' with no recognizable "
                        f"synchronizer naming (expected e.g. '{sig}_sync1'). "
                        "Likely missing a 2-FF synchronizer or async FIFO."
                    ),
                ))
    return findings


def findings_to_diagnostic_entries(findings: list[CDCFinding]) -> list[dict]:
    """Shape CDC findings the same way as Stage-1 LLM diagnostic entries,
    so both feed the refactor prompt through one uniform interface."""
    return [
        {
            "issue": "unsynchronized_cdc",
            "signal": f.signal,
            "driving_clock": f.driving_clock,
            "consuming_clock": f.consuming_clock,
            "recommendation": "insert_2ff_or_async_fifo",
            "note": f.note,
        }
        for f in findings
    ]
