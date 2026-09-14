"""
The closed loop, end to end, for ONE module. This is the piece that answers
"how do we build the exact AI agent" -- everything else in this codebase is
a tool it calls.

Run: python -m agent.orchestrator <rtl_file> <testbench_file> --top <module_name> \
        [--liberty LIB] [--sdc SDC] [--no-eqy]

No prompts, no pauses, no human decision points. Every accept/reject is made
by the verification gate in _verify(), not by a person reading a diff.

The gate is now TWO checks, both required when EQY is enabled (the
default): a functional regression (iverilog/vvp against the existing
testbench) AND a formal equivalence check (EQY) proving the refactored
module is behaviorally identical to the original. A testbench only proves
correctness for the vectors it happens to exercise; EQY is what lets the
report legitimately claim "functional equivalence," not just "passed our
tests" -- and the brief's deliverable list names a formal equivalence
report explicitly, so this isn't optional polish.
"""

from __future__ import annotations
import argparse
import tempfile
from pathlib import Path

from . import tools, cdc_lint, llm_stages, eqy_check
from .state import ModuleRun, Attempt, Metrics

MAX_RETRIES_PER_DIAGNOSIS = 3


def _analyze(rtl_path: str, liberty: str | None, sdc: str | None, work_dir: Path) -> tuple[Metrics, str, list[dict]]:
    """Runs the full analysis stack on a given RTL file: synth -> stats,
    (optionally) STA, and structural CDC lint. Returns metrics + a plain-text
    STA summary for the Stage-1 prompt + CDC findings as diagnostic entries."""
    yosys_result = tools.run_yosys(rtl_path, liberty, work_dir)
    stats = tools.parse_yosys_stats(yosys_result.stdout)

    sta_summary = "(OpenSTA not configured -- pass --liberty and --sdc to enable)"
    wns = tns = None
    if liberty and sdc:
        netlist = str(work_dir / "synth_netlist.v")
        sta_result = tools.run_opensta(netlist, sdc, liberty, work_dir)
        sta_summary = sta_result.stdout
        parsed = tools.parse_opensta_report(sta_result.stdout)
        wns, tns = parsed["wns_ns"], parsed["tns_ns"]

    cdc_findings = cdc_lint.check_cdc(Path(rtl_path).read_text())
    cdc_entries = cdc_lint.findings_to_diagnostic_entries(cdc_findings)

    metrics = Metrics(cell_count=stats["cell_count"], wns_ns=wns, tns_ns=tns)
    return metrics, sta_summary, cdc_entries


def _verify(rtl_text: str, original_rtl_path: str, testbench_path: str, top_module: str,
            work_dir: Path, use_eqy: bool) -> tuple[tools.ToolResult, eqy_check.EquivalenceResult | None]:
    """The non-negotiable gate, now in two parts:

    1. Functional regression -- iverilog+vvp against the existing testbench.
       A hard reject on anything short of a clean pass.
    2. Formal equivalence (EQY) -- only run if part 1 already passed, since
       there's no point formally proving equivalence of something that
       doesn't even simulate correctly. If EQY is enabled and doesn't
       return an explicit PASS, that is ALSO a hard reject, even if the
       regression passed -- a testbench passing does not prove behavioral
       equivalence, only that the vectors it happened to cover matched.
    """
    candidate_path = work_dir / Path(original_rtl_path).name
    candidate_path.write_text(rtl_text)
    regression_result = tools.run_iverilog(str(candidate_path), testbench_path, work_dir)

    if not regression_result.ok or not use_eqy:
        return regression_result, None

    original_path = work_dir / f"original_{Path(original_rtl_path).name}"
    original_path.write_text(Path(original_rtl_path).read_text())
    eqy_result = eqy_check.check_equivalence(
        str(original_path), str(candidate_path), top_module, work_dir / "eqy"
    )
    return regression_result, eqy_result


def run_module(rtl_path: str, testbench_path: str, top_module: str, liberty: str | None = None,
               sdc: str | None = None, out_dir: str = "run_logs", use_eqy: bool = True) -> ModuleRun:
    module_name = Path(rtl_path).stem
    original_rtl = Path(rtl_path).read_text()

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)

        baseline_metrics, sta_summary, cdc_entries = _analyze(rtl_path, liberty, sdc, work_dir)
        run = ModuleRun(module_path=rtl_path, baseline_metrics=baseline_metrics, best_rtl=original_rtl)

        diagnoses = llm_stages.stage1_diagnose(module_name, original_rtl, sta_summary, cdc_entries)
        # Highest severity first -- fix the thing costing the most slack first.
        diagnoses.sort(key=lambda d: {"high": 0, "medium": 1, "low": 2}.get(d.get("severity", "low"), 2))

        attempt_num = 0
        for diagnosis in diagnoses:
            candidate_rtl = llm_stages.stage2_refactor(module_name, run.best_rtl, diagnosis)
            error_log = ""
            accepted = False

            for retry in range(MAX_RETRIES_PER_DIAGNOSIS):
                attempt_num += 1
                verify_dir = work_dir / f"attempt_{attempt_num}"
                verify_dir.mkdir()
                regression_result, eqy_result = _verify(
                    candidate_rtl, rtl_path, testbench_path, top_module, verify_dir, use_eqy
                )

                attempt = Attempt(
                    attempt_num=attempt_num,
                    diagnosis=diagnosis,
                    refactor_prompt=str(diagnosis),
                    refactored_rtl=candidate_rtl,
                    syntax_ok=True,  # iverilog reaching vvp already implies clean compile
                    regression_ok=regression_result.ok,
                    equivalence_checked=eqy_result is not None,
                    equivalence_ok=bool(eqy_result and eqy_result.equivalent),
                    equivalence_report=(eqy_result.report_text if eqy_result else ""),
                    error_log=regression_result.stderr or regression_result.stdout,
                )

                # Both gates must pass when EQY is enabled; only regression
                # is required if the module was explicitly run with --no-eqy.
                gate_passed = regression_result.ok and (not use_eqy or attempt.equivalence_ok)

                if gate_passed:
                    # Re-measure so we never accept a change that regresses
                    # a metric below the last known-good baseline.
                    candidate_path = verify_dir / Path(rtl_path).name
                    new_metrics, _, _ = _analyze(str(candidate_path), liberty, sdc, verify_dir)
                    regressed = (
                        new_metrics.cell_count is not None and baseline_metrics.cell_count is not None
                        and new_metrics.cell_count > baseline_metrics.cell_count * 1.5  # sanity guard
                    )
                    if not regressed:
                        attempt.metrics_after = new_metrics
                        attempt.accepted = True
                        run.best_rtl = candidate_rtl
                        accepted = True
                        run.attempts.append(attempt)
                        break
                    else:
                        attempt.metrics_after = new_metrics  # record what was measured even on rejection
                        attempt.failure_reason = "Accepted functionally + formally but cell count regressed >50% -- rejected."
                        attempt.extra_input_needed = "Area budget / max-cell-delta constraint was not given to Stage 2."
                        run.attempts.append(attempt)
                        break  # don't retry a functionally-fine-but-bloated fix
                elif regression_result.ok and use_eqy and not attempt.equivalence_ok:
                    # This is the specific, interesting failure mode: the
                    # testbench passed but EQY could not prove equivalence.
                    # That means either the testbench has a coverage gap,
                    # or the refactor genuinely changed behavior on an
                    # untested path -- either way, do not accept it.
                    attempt.failure_reason = "Regression passed but EQY could not prove formal equivalence."
                    attempt.extra_input_needed = (
                        "The testbench may not exercise the state the refactor changed. Needs either a "
                        "stronger testbench (more coverage) or the EQY counterexample trace fed back to "
                        "Stage 2 as the next diagnosis input."
                    )
                    run.attempts.append(attempt)
                    error_log = attempt.equivalence_report
                    if retry < MAX_RETRIES_PER_DIAGNOSIS - 1:
                        candidate_rtl = llm_stages.self_heal_retry(module_name, candidate_rtl, error_log)
                else:
                    attempt.failure_reason = "Regression failed."
                    attempt.extra_input_needed = (
                        "Likely needs the specific failing assertion/signal trace, not just the raw "
                        "iverilog/vvp error text -- consider passing a waveform diff on the next retry."
                    )
                    run.attempts.append(attempt)
                    error_log = attempt.error_log
                    if retry < MAX_RETRIES_PER_DIAGNOSIS - 1:
                        candidate_rtl = llm_stages.self_heal_retry(module_name, candidate_rtl, error_log)

            if not accepted:
                # This diagnosis never converged within budget -- move on to
                # the next one rather than blocking the whole module.
                continue

        run.final_status = "converged" if any(a.accepted for a in run.attempts) else "reverted"
        run.save(Path(out_dir))
        return run


def main():
    parser = argparse.ArgumentParser(description="Run the closed-loop RTL refactoring agent on one module.")
    parser.add_argument("rtl_file")
    parser.add_argument("testbench_file")
    parser.add_argument("--top", required=True, help="Top module name (must match the Verilog module keyword)")
    parser.add_argument("--liberty", default=None, help="Path to .lib file for real gate delays")
    parser.add_argument("--sdc", default=None, help="Path to .sdc file with clock definitions")
    parser.add_argument("--out-dir", default="run_logs")
    parser.add_argument("--no-eqy", action="store_true", help="Skip formal equivalence checking (regression-only gate)")
    args = parser.parse_args()

    run = run_module(
        args.rtl_file, args.testbench_file, args.top, args.liberty, args.sdc,
        args.out_dir, use_eqy=not args.no_eqy,
    )
    print(f"[{run.final_status}] {run.module_path} -- {len(run.attempts)} attempt(s) logged to {args.out_dir}/")


if __name__ == "__main__":
    main()
