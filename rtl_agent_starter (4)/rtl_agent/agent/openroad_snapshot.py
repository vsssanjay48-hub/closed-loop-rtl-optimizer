"""
OpenROAD place-and-route snapshot -- run ONCE on the baseline design and
ONCE on the final optimized design, never inside the per-iteration loop.
Full P&R takes minutes even on a small design; running it per LLM attempt
would blow your turn-around-time budget for no benefit, since Yosys+OpenSTA
already give fast, good-enough feedback for the iterative work.

This wrapper assumes an OpenROAD-flow-scripts (ORFS) style layout:
    <orfs_root>/flow/designs/<platform>/<design_name>/config.mk
and that config.mk points at the RTL/SDC you want snapshotted. Adjust
DESIGN_NAME/PLATFORM/ORFS_ROOT below to match your actual setup -- the
exact `make` targets and metrics file location can shift between ORFS
versions, so confirm against `make help` in your ORFS checkout before
trusting this blindly.
"""

from __future__ import annotations
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PPASnapshot:
    label: str                     # "baseline" or "final"
    ran_ok: bool
    area_um2: float | None
    worst_slack_ns: float | None
    total_power_mw: float | None
    raw_log: str
    metrics_path: str | None


def run_openroad_snapshot(orfs_root: str, platform: str, design_name: str,
                           label: str, out_dir: Path) -> PPASnapshot:
    """Drives the ORFS make flow through synth -> floorplan -> place ->
    cts -> route -> finish, then reads the metrics JSON ORFS produces at
    the end. This is intentionally the full flow, not just synthesis --
    the brief lists OpenROAD explicitly, which implies real placed/routed
    numbers, not another synthesis-only estimate."""
    flow_dir = Path(orfs_root) / "flow"
    targets = ["synth", "floorplan", "place", "cts", "route", "finish"]

    log_chunks = []
    ran_ok = True
    for target in targets:
        result = subprocess.run(
            ["make", target,
             f"DESIGN_NAME={design_name}", f"PLATFORM={platform}"],
            cwd=str(flow_dir), capture_output=True, text=True,
        )
        log_chunks.append(f"--- make {target} ---\n{result.stdout}\n{result.stderr}")
        if result.returncode != 0:
            ran_ok = False
            break

    metrics_path = flow_dir / "reports" / platform / design_name / "base" / "metrics.json"
    area = slack = power = None
    if metrics_path.exists():
        try:
            data = json.loads(metrics_path.read_text())
            # Key names vary by ORFS version -- these are the common ones;
            # print the raw JSON in the report if these lookups miss, so
            # nothing silently reports as None without a trace.
            area = data.get("finish__design__instance__area")
            slack = data.get("finish__timing__setup__ws")
            power = data.get("finish__power__total")
        except (json.JSONDecodeError, OSError):
            pass

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{label}_openroad_log.txt").write_text("\n".join(log_chunks))

    return PPASnapshot(
        label=label, ran_ok=ran_ok, area_um2=area, worst_slack_ns=slack,
        total_power_mw=power, raw_log="\n".join(log_chunks)[-4000:],
        metrics_path=str(metrics_path) if metrics_path.exists() else None,
    )


def compare_snapshots(baseline: PPASnapshot, final: PPASnapshot) -> dict:
    """Simple delta table for the report -- handles missing values
    gracefully rather than crashing if one metric key didn't resolve."""
    def delta(a, b):
        if a is None or b is None:
            return None
        return round(b - a, 4)

    return {
        "area_um2": {"baseline": baseline.area_um2, "final": final.area_um2,
                     "delta": delta(baseline.area_um2, final.area_um2)},
        "worst_slack_ns": {"baseline": baseline.worst_slack_ns, "final": final.worst_slack_ns,
                           "delta": delta(baseline.worst_slack_ns, final.worst_slack_ns)},
        "total_power_mw": {"baseline": baseline.total_power_mw, "final": final.total_power_mw,
                           "delta": delta(baseline.total_power_mw, final.total_power_mw)},
    }
