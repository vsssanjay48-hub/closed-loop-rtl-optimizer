"""
Formal equivalence checking via EQY (the SymbiYosys equivalence-checking
frontend). This is what turns "the testbench passed" into "the two designs
are provably identical in behavior" -- a testbench only proves correctness
for the vectors it happens to exercise; EQY proves it (within the solver's
reach) for all reachable states. The brief's deliverable list names a
"formal equivalence verification report" explicitly, so this is not
optional polish -- it is the second half of the accept/reject gate,
alongside the iverilog regression in tools.py.

Install: SymbiYosys ships with the OSS CAD Suite; confirm with `eqy --help`.
The exact .eqy section syntax has shifted between versions -- if this
script's generated config is rejected, run `eqy --help` locally and adjust
the [gold]/[gate]/[strategy] blocks below to match your installed version
before assuming the equivalence check itself is broken.
"""

from __future__ import annotations
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class EquivalenceResult:
    equivalent: bool
    ran_ok: bool                  # did the eqy process itself complete without crashing
    report_text: str
    log_path: str


def _write_eqy_script(original_path: str, candidate_path: str, top_module: str, work_dir: Path) -> Path:
    script = f"""\
[options]
--force

[gold]
read_verilog -sv {original_path}
prep -top {top_module}

[gate]
read_verilog -sv {candidate_path}
prep -top {top_module}

[strategy sat]
depth 5
engine_sat
"""
    script_path = work_dir / "check.eqy"
    script_path.write_text(script)
    return script_path


def check_equivalence(original_path: str, candidate_path: str, top_module: str,
                       work_dir: Path) -> EquivalenceResult:
    """Formally compare original_path (gold) against candidate_path (gate).
    Returns equivalent=True only on an explicit PASS -- anything ambiguous
    (timeout, solver inconclusive, tool crash) is treated as NOT equivalent,
    since a refactor should never be accepted on an unproven claim."""
    script_path = _write_eqy_script(original_path, candidate_path, top_module, work_dir)
    eqy_work_dir = work_dir / "eqy_run"

    try:
        result = subprocess.run(
            ["eqy", "-f", str(script_path), "-d", str(eqy_work_dir)],
            capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired as e:
        return EquivalenceResult(
            equivalent=False, ran_ok=False,
            report_text=f"EQY timed out after 180s -- treated as non-equivalent (unproven). "
                        f"Consider this module for --depth increase or a bounded/inductive strategy change.",
            log_path=str(eqy_work_dir),
        )

    combined = result.stdout + result.stderr
    # EQY prints "PASS" on success, "FAIL" (with a counterexample) or an
    # error on failure. Match conservatively -- an explicit PASS line only.
    equivalent = bool(re.search(r"\bPASS\b", combined)) and not re.search(r"\bFAIL\b", combined)

    return EquivalenceResult(
        equivalent=equivalent,
        ran_ok=result.returncode == 0 or equivalent,
        report_text=combined,
        log_path=str(eqy_work_dir),
    )


def sanity_check_self_equivalence(module_path: str, top_module: str, work_dir: Path) -> bool:
    """Equivalence-checks a design against itself -- should trivially PASS.
    Run this once when you first install EQY, before trusting any real
    result from it. If this fails, the tool/environment is broken, not
    your RTL."""
    result = check_equivalence(module_path, module_path, top_module, work_dir)
    return result.equivalent
