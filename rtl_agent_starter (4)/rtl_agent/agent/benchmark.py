"""
Benchmark suite runner. Answers the brief's "success rate based on the
issues seen in the RTL/netlist" requirement -- one lucky run on one module
is an anecdote, not a statistic. This runs the full agent loop across every
case in a benchmark directory, repeated N times each (LLM output is
non-deterministic), and aggregates a real success rate with variance.

Expected directory layout:
    benchmark_cases/
        deep_if_else_01/
            case.v          <- deliberately broken RTL
            case_tb.v        <- testbench, TEST PASSED / TEST FAILED convention
            meta.json        <- {"top": "module_name", "issue_category": "deep_if_else"}
        missing_sync_02/
            ...
"""

from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict

from . import orchestrator


def discover_cases(benchmark_dir: Path) -> list[dict]:
    cases = []
    for case_dir in sorted(p for p in benchmark_dir.iterdir() if p.is_dir()):
        meta_path = case_dir / "meta.json"
        rtl_path = case_dir / "case.v"
        tb_path = case_dir / "case_tb.v"
        if not (meta_path.exists() and rtl_path.exists() and tb_path.exists()):
            print(f"  [skip] {case_dir.name}: missing case.v / case_tb.v / meta.json")
            continue
        meta = json.loads(meta_path.read_text())
        cases.append({
            "name": case_dir.name,
            "rtl_path": str(rtl_path),
            "tb_path": str(tb_path),
            "top": meta["top"],
            "issue_category": meta.get("issue_category", "unknown"),
        })
    return cases


def run_benchmark(benchmark_dir: str, repeats: int = 3, liberty: str | None = None,
                   sdc: str | None = None, out_dir: str = "run_logs/benchmark",
                   use_eqy: bool = True) -> dict:
    cases = discover_cases(Path(benchmark_dir))
    if not cases:
        raise ValueError(f"No valid cases found in {benchmark_dir} -- check the layout in this module's docstring.")

    results_by_case: dict[str, list[bool]] = defaultdict(list)
    category_results: dict[str, list[bool]] = defaultdict(list)
    all_runs = []

    for case in cases:
        for rep in range(repeats):
            run_out_dir = f"{out_dir}/{case['name']}/rep_{rep}"
            run = orchestrator.run_module(
                case["rtl_path"], case["tb_path"], case["top"],
                liberty=liberty, sdc=sdc, out_dir=run_out_dir, use_eqy=use_eqy,
            )
            converged = run.final_status == "converged"
            results_by_case[case["name"]].append(converged)
            category_results[case["issue_category"]].append(converged)
            all_runs.append({
                "case": case["name"], "category": case["issue_category"],
                "rep": rep, "converged": converged, "attempts": len(run.attempts),
            })
            print(f"  [{case['name']} rep {rep}] {'PASS' if converged else 'FAIL'}")

    def rate(results: list[bool]) -> float:
        return round(100.0 * sum(results) / len(results), 1) if results else 0.0

    summary = {
        "total_cases": len(cases),
        "repeats_per_case": repeats,
        "overall_success_rate_pct": rate([r for results in results_by_case.values() for r in results]),
        "per_case": {name: {"success_rate_pct": rate(results), "n": len(results)}
                     for name, results in results_by_case.items()},
        "per_category": {cat: {"success_rate_pct": rate(results), "n": len(results)}
                          for cat, results in category_results.items()},
        "raw_runs": all_runs,
    }

    out_path = Path(out_dir) / "benchmark_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run the benchmark suite across all deliberately-broken cases.")
    parser.add_argument("benchmark_dir")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--liberty", default=None)
    parser.add_argument("--sdc", default=None)
    parser.add_argument("--out-dir", default="run_logs/benchmark")
    parser.add_argument("--no-eqy", action="store_true")
    args = parser.parse_args()

    summary = run_benchmark(
        args.benchmark_dir, args.repeats, args.liberty, args.sdc, args.out_dir,
        use_eqy=not args.no_eqy,
    )
    print(f"\nOverall success rate: {summary['overall_success_rate_pct']}% "
          f"across {summary['total_cases']} cases x {summary['repeats_per_case']} repeats")


if __name__ == "__main__":
    main()
