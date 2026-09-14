"""
The single entry point for "run everything." This is what makes the whole
system genuinely one command, matching the brief's fully-automated / no
human-in-the-loop requirement at the top level, not just inside one module.

Usage:
    python -m agent.run_all --design-dir path/to/five_domain_design \
        --benchmark-dir path/to/benchmark_cases \
        --liberty path/to/sky130.lib --sdc path/to/design.sdc \
        --repeats 3

Expects design-dir to contain matched pairs: <name>.v / <name>_tb.v, plus
a manifest.json mapping each pair to its top-module name:
    {"domain_a_sampler": "domain_a_sampler", "domain_b_uart": "domain_b_uart", ...}
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

from . import orchestrator, benchmark, report_gen


def run_design_modules(design_dir: str, liberty: str | None, sdc: str | None,
                        out_dir: str, use_eqy: bool) -> list[str]:
    manifest_path = Path(design_dir) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"{manifest_path} not found -- see this module's docstring for the expected "
            f"{{module_name: top_module}} manifest format."
        )
    manifest = json.loads(manifest_path.read_text())

    run_paths = []
    for module_name, top_module in manifest.items():
        rtl_path = Path(design_dir) / f"{module_name}.v"
        tb_path = Path(design_dir) / f"{module_name}_tb.v"
        if not (rtl_path.exists() and tb_path.exists()):
            print(f"  [skip] {module_name}: missing .v or _tb.v")
            continue
        print(f"[running] {module_name} (top={top_module})")
        run = orchestrator.run_module(
            str(rtl_path), str(tb_path), top_module,
            liberty=liberty, sdc=sdc, out_dir=out_dir, use_eqy=use_eqy,
        )
        print(f"  -> {run.final_status}, {len(run.attempts)} attempt(s)")
        run_paths.append(str(Path(out_dir) / f"{module_name}.run.json"))
    return run_paths


def main():
    parser = argparse.ArgumentParser(description="Run the full closed-loop pipeline end to end.")
    parser.add_argument("--design-dir", required=True, help="Directory of the real 5-domain design modules")
    parser.add_argument("--benchmark-dir", default=None, help="Directory of deliberately-broken benchmark cases")
    parser.add_argument("--liberty", default=None)
    parser.add_argument("--sdc", default=None)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out-dir", default="run_logs")
    parser.add_argument("--no-eqy", action="store_true")
    parser.add_argument("--report-out", default="report_data.md")
    args = parser.parse_args()
    use_eqy = not args.no_eqy

    print("=== Stage 1: running the agent on the real design modules ===")
    run_design_modules(args.design_dir, args.liberty, args.sdc, args.out_dir, use_eqy)

    benchmark_summary_path = None
    if args.benchmark_dir:
        print("\n=== Stage 2: running the benchmark suite ===")
        summary = benchmark.run_benchmark(
            args.benchmark_dir, repeats=args.repeats, liberty=args.liberty, sdc=args.sdc,
            out_dir=f"{args.out_dir}/benchmark", use_eqy=use_eqy,
        )
        benchmark_summary_path = f"{args.out_dir}/benchmark/benchmark_summary.json"
        print(f"  Overall benchmark success rate: {summary['overall_success_rate_pct']}%")

    print("\n=== Stage 3: generating report data tables ===")
    report_gen.generate_report_data(args.out_dir, benchmark_summary_path, args.report_out)

    print(f"\nDone. Report data at {args.report_out}. "
          f"Remaining manual steps: OpenROAD baseline/final snapshot (agent/openroad_snapshot.py, "
          f"run once, not part of this loop) and writing the report prose around these tables.")


if __name__ == "__main__":
    main()
