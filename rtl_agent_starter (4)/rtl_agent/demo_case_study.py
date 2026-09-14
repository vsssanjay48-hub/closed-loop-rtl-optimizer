"""
Camera-ready demo of the real orchestrator run used in the video script's
2:20-3:20 segment. This calls the REAL orchestrator, REAL Yosys, and REAL
iverilog -- only the LLM diagnosis/refactor calls and the EQY result are
stubbed, because no API key is funded yet and EQY isn't installed. That
stub is announced out loud by the script itself, so nothing is hidden on
camera.

Run this from inside rtl_agent/ with:
    python demo_case_study.py

Before recording:
  - Resize your terminal to a large, readable font (18-20pt minimum)
  - Widen the terminal window so long lines don't wrap awkwardly
  - Run it once off-camera first to confirm it completes cleanly on your
    machine, then run it again for the actual recording
"""

import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

from agent import orchestrator, tools, llm_stages, eqy_check


def narrate(text, pause=1.2):
    print(text)
    time.sleep(pause)


def main():
    narrate("=" * 70, 0.3)
    narrate("NEBULA CASE STUDY -- real synthesis + regression, real gate logic")
    narrate("=" * 70)
    narrate("")
    narrate("NOTE (said out loud, not hidden): the LLM diagnosis/refactor calls")
    narrate("below are STUBBED -- no funded API key yet. Everything else --")
    narrate("Yosys synthesis, Icarus Verilog regression, and the accept/reject")
    narrate("decision -- is real, running on this machine, right now.")
    narrate("")
    time.sleep(1)

    canned_diagnosis = [{
        "issue": "deep_if_else",
        "target_line": 9,
        "signal": "pos",
        "recommendation": "case_statement",
        "severity": "high",
    }]
    refactored_path = Path(__file__).parent / "demo" / "priority_encoder_refactored.v"
    canned_refactor = refactored_path.read_text()

    with mock.patch.object(llm_stages, "stage1_diagnose", return_value=canned_diagnosis), \
         mock.patch.object(llm_stages, "stage2_refactor", return_value=canned_refactor), \
         mock.patch.object(eqy_check, "check_equivalence",
                            return_value=eqy_check.EquivalenceResult(
                                True, True, "PASS (stubbed -- EQY not installed)", "/tmp")):

        narrate("--> Stage 1-4: synthesizing baseline, running structural CDC lint...")
        run = orchestrator.run_module(
            str(Path(__file__).parent / "demo" / "priority_encoder.v"),
            str(Path(__file__).parent / "demo" / "priority_encoder_tb.v"),
            "priority_encoder",
            out_dir="demo_run_logs",
        )

    narrate("")
    narrate(f"Baseline cell count (real Yosys):  {run.baseline_metrics.cell_count}")
    a = run.attempts[0]
    narrate(f"Proposed fix -- functional regression:  {'PASS' if a.regression_ok else 'FAIL'} (real iverilog)")
    narrate(f"Proposed fix -- formal equivalence:      {'PASS' if a.equivalence_ok else 'FAIL'} (stubbed)")
    if a.metrics_after:
        narrate(f"Proposed fix -- cell count after:        {a.metrics_after.cell_count}")
    narrate("")
    narrate(f"FINAL DECISION: {'ACCEPTED' if a.accepted else 'REJECTED'}")
    narrate(f"Reason: {a.failure_reason or 'improvement confirmed'}")
    narrate("")
    narrate("=" * 70)


if __name__ == "__main__":
    main()
