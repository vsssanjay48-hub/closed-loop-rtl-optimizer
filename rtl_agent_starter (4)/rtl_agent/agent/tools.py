"""
Thin wrappers around the actual EDA tools. This is the layer that turns your
manual "run iverilog, then yosys" workflow into something the agent can call
programmatically and parse the results of.

Windows-hardened version:
- Uses Path.as_posix() so backslashes don't corrupt Yosys/OpenSTA Tcl scripts.
- Strips carriage returns (\r) before regex matching.
- Explicitly handles subprocess output encodings and Windows batch resolution.
"""

from __future__ import annotations
import re
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ToolResult:
    ok: bool
    stdout: str
    stderr: str


def run_iverilog(rtl_path: str, testbench_path: str, work_dir: Path) -> ToolResult:
    """Compile RTL + testbench, then run it with vvp. This is your
    'syntax + regression gate' in one call -- iverilog fails loudly on
    syntax errors, and vvp's output tells you if the testbench passed."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    vvp_out = (work_dir / "sim.vvp").resolve().as_posix()
    rtl_clean = Path(rtl_path).resolve().as_posix()
    tb_clean = Path(testbench_path).resolve().as_posix()

    compile_cmd = ["iverilog", "-o", vvp_out, rtl_clean, tb_clean]
    compiled = subprocess.run(
        compile_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    if compiled.returncode != 0:
        return ToolResult(ok=False, stdout=compiled.stdout, stderr=compiled.stderr)

    ran = subprocess.run(
        ["vvp", vvp_out],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    # Convention: your testbenches should print "TEST PASSED" or "TEST FAILED"
    # on a line by itself -- much easier to grep than parsing $finish codes.
    clean_out = ran.stdout.replace("\r", "")
    ok = "TEST PASSED" in clean_out and "TEST FAILED" not in clean_out
    return ToolResult(ok=ok, stdout=ran.stdout, stderr=ran.stderr)


def run_yosys(rtl_path: str, liberty_path: str | None, work_dir: Path) -> ToolResult:
    """Synthesize and dump stats. Passing a liberty file maps to real cells
    instead of the generic $_MUX_/$_NOT_/$_OR_ primitives your last run
    stopped at -- this is what fixes the 'No timing paths found' warning."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    netlist_out = (work_dir / "synth_netlist.v").resolve().as_posix()
    json_out = (work_dir / "synth_netlist.json").resolve().as_posix()
    rtl_clean = Path(rtl_path).resolve().as_posix()

    script_lines = [
        f"read_verilog {rtl_clean}",
        "hierarchy -auto-top",
        "proc; opt; fsm; opt; memory; opt",
    ]
    if liberty_path:
        lib_clean = Path(liberty_path).resolve().as_posix()
        script_lines += [
            "techmap",
            f"dfflibmap -liberty {lib_clean}",
            f"abc -liberty {lib_clean}",
        ]
    else:
        script_lines += ["techmap", "opt"]
    script_lines += [f"write_verilog {netlist_out}", f"write_json {json_out}", "stat"]

    ys_script = work_dir / "run.ys"
    ys_script.write_text("\n".join(script_lines), encoding="utf-8")

    result = subprocess.run(
        ["yosys", "-s", ys_script.resolve().as_posix()],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    return ToolResult(ok=result.returncode == 0, stdout=result.stdout, stderr=result.stderr)


def compute_fanout(netlist_json_path: str) -> dict:
    """Real per-net fanout from the Yosys JSON netlist written alongside the
    Verilog output in run_yosys(). Counts how many cell input ports each net
    bit drives -- high-fanout nets add capacitive delay independent of logic
    depth (Section G.1 of the study guide), and this is what actually
    measures it instead of estimating it."""
    import json as _json

    data = _json.loads(Path(netlist_json_path).read_text(encoding="utf-8"))
    if not data.get("modules"):
        return {"max_fanout": None, "avg_fanout": None, "net_count": 0}

    module = next(iter(data["modules"].values()))
    fanout: dict = {}
    for cell in module.get("cells", {}).values():
        for port, direction in cell.get("port_directions", {}).items():
            if direction == "input":
                for bit in cell["connections"][port]:
                    fanout[bit] = fanout.get(bit, 0) + 1

    if not fanout:
        return {"max_fanout": None, "avg_fanout": None, "net_count": 0}

    values = list(fanout.values())
    return {
        "max_fanout": max(values),
        "avg_fanout": round(sum(values) / len(values), 2),
        "net_count": len(values),
    }


def parse_yosys_stats(stdout: str) -> dict:
    """Pull cell count out of a yosys 'stat' dump. Matches Yosys's actual
    output format ("Number of cells:                 21"), not a guessed
    format -- an earlier version of this regex was never checked against
    real Yosys output and silently matched nothing, always returning 0.
    Extend this to also grab per-cell-type breakdowns once mapped to a
    real liberty library."""
    clean_out = stdout.replace("\r", "")
    m = re.search(r"Number of cells:\s*(\d+)", clean_out, re.IGNORECASE)
    return {"cell_count": int(m.group(1)) if m else None}


def run_opensta(netlist_path: str, sdc_path: str, liberty_path: str, work_dir: Path) -> ToolResult:
    """Real static timing analysis. Requires: a synthesized netlist (from
    run_yosys with a liberty file), an SDC defining your clocks (including
    the 5 masters + their generated/divided clocks), and that same liberty
    file for cell delays. This is what gives you a trustworthy WNS/Fmax --
    Yosys's built-in `stat`/`sta` pass is not a substitute."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    lib_clean = Path(liberty_path).resolve().as_posix()
    net_clean = Path(netlist_path).resolve().as_posix()
    sdc_clean = Path(sdc_path).resolve().as_posix()

    tcl = work_dir / "sta.tcl"
    tcl.write_text(
        f"""
read_liberty {lib_clean}
read_verilog {net_clean}
link_design
read_sdc {sdc_clean}
report_checks -path_delay max -format full_clock
report_wns
report_tns
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["sta", "-exit", tcl.resolve().as_posix()],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    return ToolResult(ok=result.returncode == 0, stdout=result.stdout, stderr=result.stderr)


def parse_opensta_report(stdout: str) -> dict:
    clean_out = stdout.replace("\r", "")
    wns = re.search(r"wns\s+(-?\d+\.?\d*)", clean_out, re.IGNORECASE)
    tns = re.search(r"tns\s+(-?\d+\.?\d*)", clean_out, re.IGNORECASE)
    return {
        "wns_ns": float(wns.group(1)) if wns else None,
        "tns_ns": float(tns.group(1)) if tns else None,
    }