"""
Turns the raw artifacts (per-module ModuleRun JSON logs, the benchmark
summary, and an optional OpenROAD before/after comparison) into markdown
tables ready to paste into the 10-12 page report. This generates DATA, not
prose -- the sentences around these tables are written by hand later, per
plan. Re-run this any time the logs change; never hand-edit its output.
"""

from __future__ import annotations
import json
from pathlib import Path


def _fmt(v, suffix=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.3g}{suffix}"
    return f"{v}{suffix}"


def module_ppa_table(run_logs_dir: str) -> str:
    """Before/after PPA table, one row per module, pulled straight from
    each ModuleRun's baseline_metrics and the metrics_after of its last
    accepted attempt."""
    rows = ["| Module | Status | Cells (before→after) | WNS ns (before→after) | Attempts |",
            "|---|---|---|---|---|"]
    for run_file in sorted(Path(run_logs_dir).glob("*.run.json")):
        data = json.loads(run_file.read_text())
        baseline = data["baseline_metrics"]
        accepted = next((a for a in reversed(data["attempts"]) if a["accepted"]), None)
        after = accepted["metrics_after"] if accepted else None

        cells_before = _fmt(baseline.get("cell_count"))
        cells_after = _fmt(after.get("cell_count")) if after else "—"
        wns_before = _fmt(baseline.get("wns_ns"))
        wns_after = _fmt(after.get("wns_ns")) if after else "—"

        rows.append(
            f"| {data['module_path']} | {data['final_status']} | "
            f"{cells_before} → {cells_after} | {wns_before} → {wns_after} | "
            f"{len(data['attempts'])} |"
        )
    return "\n".join(rows)


def benchmark_success_table(benchmark_summary_path: str) -> str:
    summary = json.loads(Path(benchmark_summary_path).read_text())
    rows = ["| Issue category | Success rate | N (cases × repeats) |", "|---|---|---|"]
    for cat, stats in summary["per_category"].items():
        rows.append(f"| {cat} | {stats['success_rate_pct']}% | {stats['n']} |")
    rows.append(f"| **Overall** | **{summary['overall_success_rate_pct']}%** | "
                f"**{summary['total_cases']} × {summary['repeats_per_case']}** |")
    return "\n".join(rows)


def failure_analysis_table(run_logs_dir: str, benchmark_logs_dir: str | None = None) -> str:
    """Every attempt that was NOT accepted, with its recorded failure reason
    and the agent's own note on what extra input might have converged it --
    this is the direct answer to the brief's "analysis on the failed cases"
    requirement, sourced from real logs rather than written after the fact."""
    rows = ["| Module | Issue | Failure reason | Extra input needed |", "|---|---|---|---|"]
    search_dirs = [Path(run_logs_dir)]
    if benchmark_logs_dir:
        search_dirs.append(Path(benchmark_logs_dir))

    seen = set()
    for d in search_dirs:
        for run_file in d.rglob("*.run.json"):
            if run_file in seen:
                continue
            seen.add(run_file)
            data = json.loads(run_file.read_text())
            for attempt in data["attempts"]:
                if not attempt["accepted"] and attempt.get("failure_reason"):
                    issue = attempt["diagnosis"].get("issue", "unknown")
                    reason = attempt["failure_reason"].replace("|", "/")
                    extra = attempt.get("extra_input_needed", "").replace("|", "/")
                    rows.append(f"| {Path(data['module_path']).name} | {issue} | {reason} | {extra} |")
    if len(rows) == 2:
        rows.append("| _(no failed attempts logged yet)_ | | | |")
    return "\n".join(rows)


def equivalence_summary(run_logs_dir: str) -> str:
    """Counts how many accepted changes were backed by a formal EQY PASS
    vs. a regression-only accept (e.g. runs done with --no-eqy) -- this is
    the evidence for the "formal equivalence verification report"
    deliverable specifically."""
    checked = proven = 0
    for run_file in Path(run_logs_dir).glob("*.run.json"):
        data = json.loads(run_file.read_text())
        for attempt in data["attempts"]:
            if attempt["accepted"]:
                if attempt.get("equivalence_checked"):
                    checked += 1
                    if attempt.get("equivalence_ok"):
                        proven += 1
    total_accepted = sum(
        1 for run_file in Path(run_logs_dir).glob("*.run.json")
        for a in json.loads(run_file.read_text())["attempts"] if a["accepted"]
    )
    return (
        f"- Accepted changes total: {total_accepted}\n"
        f"- Accepted changes with EQY formal equivalence attempted: {checked}\n"
        f"- Accepted changes with EQY PASS (proven equivalent): {proven}\n"
    )


def generate_report_data(run_logs_dir: str, benchmark_summary_path: str | None,
                          out_path: str = "report_data.md") -> None:
    sections = [
        "# Report Data — auto-generated, do not hand-edit\n",
        "Regenerate with `python -m agent.report_gen` after any new run.\n",
        "## Module-level PPA (before → after)\n",
        module_ppa_table(run_logs_dir), "\n",
        "## Formal Equivalence Coverage\n",
        equivalence_summary(run_logs_dir), "\n",
    ]
    if benchmark_summary_path and Path(benchmark_summary_path).exists():
        sections += [
            "## Benchmark Success Rate\n",
            benchmark_success_table(benchmark_summary_path), "\n",
        ]
    sections += [
        "## Failure Case Analysis\n",
        failure_analysis_table(run_logs_dir,
                                str(Path(benchmark_summary_path).parent) if benchmark_summary_path else None),
        "\n",
    ]
    Path(out_path).write_text("\n".join(sections))
    print(f"Wrote {out_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate report data tables from run logs.")
    parser.add_argument("--run-logs-dir", default="run_logs")
    parser.add_argument("--benchmark-summary", default="run_logs/benchmark/benchmark_summary.json")
    parser.add_argument("--out", default="report_data.md")
    args = parser.parse_args()
    generate_report_data(args.run_logs_dir, args.benchmark_summary, args.out)


if __name__ == "__main__":
    main()
