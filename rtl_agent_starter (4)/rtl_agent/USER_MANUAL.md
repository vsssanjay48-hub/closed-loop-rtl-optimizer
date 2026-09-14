# User Manual — RTL Refactoring Agent
### Nebula@BITS-Goa × Astera Labs

This manual covers everything in the codebase except the 5-domain input RTL
itself — that's the one piece you build separately, following Section C of
the blueprint. Everything here assumes that RTL (and its testbenches) exist
and just need to be pointed at.

---

## 1. What's in this codebase

| File | What it does | New in this update? |
|---|---|---|
| `agent/tools.py` | Runs iverilog/vvp and Yosys, parses their output, extracts real per-net fanout | **Fanout extraction added; a real cell-count parsing bug was found and fixed — see Section 12** |
| `agent/cdc_lint.py` | Structural (rule-based) CDC checker | — |
| `agent/prompts.py` | The two-stage LLM prompt templates | — |
| `agent/llm_stages.py` | The actual Stage-1/Stage-2 LLM calls | — |
| `agent/state.py` | Per-attempt run logging (`ModuleRun`, `Attempt`) | Extended with equivalence fields |
| `agent/orchestrator.py` | The closed loop for one module | **Now gates on EQY, not just regression** |
| `agent/sdc_gen.py` | Generates the SDC for your 5 masters + generated clocks | **New** |
| `agent/eqy_check.py` | Formal equivalence checking via SymbiYosys/EQY | **New** |
| `agent/openroad_snapshot.py` | Once-per-version placed/routed PPA snapshot | **New** |
| `agent/benchmark.py` | Runs the agent across many broken cases, with repeats | **New** |
| `agent/report_gen.py` | Turns run logs into report-ready markdown tables | **New** |
| `agent/run_all.py` | One command: real design → benchmark → report data | **New** |

---

## 2. Install

```bash
pip install anthropic
export ANTHROPIC_API_KEY=your_key_here

# Confirm your existing OSS CAD Suite tools are on PATH
iverilog -V
yosys -V
sta -help          # OpenSTA — install separately if not already present
eqy --help          # SymbiYosys/EQY — ships with recent OSS CAD Suite builds;
                     # if missing, install SymbiYosys from YosysHQ separately
```

OpenROAD is only needed once you reach the final PPA snapshot (Section 7
below), not for day-to-day loop runs — you can build and test everything
else without it installed yet.

---

## 3. Before running anything: EQY sanity check

Formal equivalence checking is new to this build and easy to silently
misconfigure. Confirm it actually works on your machine before trusting any
real result from it:

```python
from pathlib import Path
from agent.eqy_check import sanity_check_self_equivalence

ok = sanity_check_self_equivalence("path/to/any_module.v", "top_module_name", Path("/tmp/eqy_sanity"))
print("EQY sanity check:", "PASS" if ok else "FAIL -- fix your EQY install before trusting real runs")
```

This equivalence-checks a design against itself. It should always pass. If
it doesn't, the problem is your EQY install or `.eqy` syntax version, not
your RTL — see the note at the top of `eqy_check.py`.

---

## 4. Generating your SDC

Don't hand-write the SDC for 10+ clocks. Define the clock list once in
Python and generate it:

```python
from agent.sdc_gen import ClockSpec, GeneratedClockSpec, write_sdc

clocks = [
    ClockSpec("clk_a", "clk_a", 7.0),    # period in ns -- keep these mutually
    ClockSpec("clk_b", "clk_b", 11.3),   # "irrational-looking" relative to each
    ClockSpec("clk_c", "clk_c", 5.9),    # other so nothing lines up by accident
    ClockSpec("clk_d", "clk_d", 13.7),
    ClockSpec("clk_e", "clk_e", 9.1),
]
generated = [
    GeneratedClockSpec("clk_a_div2", "clk_a_div2", "clk_a", 2),
    GeneratedClockSpec("clk_b_div3", "clk_b_div3", "clk_b", 3),   # odd ratio
    GeneratedClockSpec("clk_c_div4", "clk_c_div4", "clk_c", 4),
    GeneratedClockSpec("clk_d_div5", "clk_d_div5", "clk_d", 5),   # odd ratio
    GeneratedClockSpec("clk_e_div6", "clk_e_div6", "clk_e", 6),
]
write_sdc("design.sdc", clocks, generated)
```

This also writes `set_clock_groups -asynchronous`, grouping each master with
its own generated clock and marking every other group as asynchronous to
it — this is what stops OpenSTA from reporting spurious "violations" on the
CDC paths that your synchronizers (not timing closure) are responsible for.

---

## 5. Running the agent on one module

```bash
python -m agent.orchestrator path/to/module.v path/to/module_tb.v \
    --top module_name \
    --liberty path/to/sky130_fd_sc_hd.lib \
    --sdc design.sdc \
    --out-dir run_logs
```

**Testbench convention (required):** your testbench must print exactly
`TEST PASSED` or `TEST FAILED` on its own line. This is what the regression
gate greps for — a testbench that just exits without printing either is
treated as a failure, not a pass, by design (a silent exit should never be
read as success).

**What "accepted" means now:** a fix is only accepted if BOTH:
1. Functional regression passes (`iverilog`/`vvp` against your testbench), **and**
2. EQY formally proves the new RTL is behaviorally equivalent to the original.

If your testbench passes but EQY can't prove equivalence, the change is
**rejected anyway** — this is deliberate. A passing testbench only proves
correctness for the vectors it happens to exercise; it doesn't prove general
equivalence. If you see this rejection a lot, it usually means your
testbench has a coverage gap, not that the agent is being overly strict.

To disable EQY temporarily (e.g. while debugging the loop itself, before
EQY is installed): add `--no-eqy`. Don't submit results generated this way
without noting it — the brief asks for formal equivalence specifically.

---

## 6. Running the benchmark suite (your success-rate number)

Build a benchmark directory like this:

```
benchmark_cases/
    deep_if_else_01/
        case.v            <- deliberately broken RTL
        case_tb.v          <- testbench (TEST PASSED / TEST FAILED convention)
        meta.json           <- {"top": "module_name", "issue_category": "deep_if_else"}
    missing_sync_02/
        ...
```

Aim for 10–15 cases spread across categories: deep if-else, missing
synchronizer, unbalanced pipeline, wrong divider ratio, dead logic, bad FSM
encoding. Then run:

```bash
python -m agent.benchmark benchmark_cases --repeats 3 \
    --liberty sky130_fd_sc_hd.lib --sdc design.sdc \
    --out-dir run_logs/benchmark
```

`--repeats 3` matters — LLM output varies run to run, and a single-pass
"it worked once" is not a defensible success-rate statistic. This produces
`run_logs/benchmark/benchmark_summary.json` with overall, per-case, and
per-category success rates.

---

## 7. OpenROAD snapshot (run this exactly twice, total)

Once your final RTL is settled, get real placed-and-routed PPA numbers —
not just Yosys estimates — for the report:

```python
from pathlib import Path
from agent.openroad_snapshot import run_openroad_snapshot, compare_snapshots

baseline = run_openroad_snapshot("path/to/orfs", "sky130hd", "design_name", "baseline", Path("run_logs/openroad"))
final = run_openroad_snapshot("path/to/orfs", "sky130hd", "design_name", "final", Path("run_logs/openroad"))
print(compare_snapshots(baseline, final))
```

This assumes an OpenROAD-flow-scripts (ORFS) layout. **Check `make help` in
your actual ORFS checkout first** — target names and the metrics JSON path
shift between versions, and the wrapper's docstring says exactly what to
adjust if it doesn't match.

Do not run this inside the per-iteration loop — it's a full P&R flow and
will dominate your turn-around-time budget for no benefit over Yosys+OpenSTA
during iteration. Baseline once, final once, done.

---

## 8. Running everything in one command

Once your real 5-domain design and your benchmark suite both exist:

```bash
python -m agent.run_all \
    --design-dir path/to/five_domain_design \
    --benchmark-dir path/to/benchmark_cases \
    --liberty sky130_fd_sc_hd.lib \
    --sdc design.sdc \
    --repeats 3 \
    --out-dir run_logs \
    --report-out report_data.md
```

`design-dir` needs a `manifest.json` mapping each `<name>.v`/`<name>_tb.v`
pair to its top-module name:

```json
{
    "domain_a_sampler": "domain_a_sampler",
    "domain_b_uart": "domain_b_uart_top",
    "domain_c_crc": "crc_engine"
}
```

This runs Stage 1 (real design modules) → Stage 2 (benchmark suite) →
Stage 3 (report data generation) in sequence, unattended. The only two
things left after this command finishes are the OpenROAD snapshot (Section
7 — deliberately separate, run twice manually) and writing the report prose
around the generated tables.

---

## 9. Reading the output — what each log actually tells you

Every module produces `run_logs/<module_name>.run.json`. Key fields per
attempt:

| Field | Meaning |
|---|---|
| `accepted` | Did this specific fix get kept |
| `regression_ok` | Did the testbench pass |
| `equivalence_checked` | Was EQY actually run for this attempt |
| `equivalence_ok` | Did EQY return an explicit PASS |
| `failure_reason` | Human-readable reason it was rejected, if it was |
| `extra_input_needed` | The agent's own note on what context might have helped — this is your Section F failure-analysis material |

`report_gen.py` reads these directly — if a table looks wrong, check the
underlying `.run.json` first; the generator doesn't compute anything the
raw log doesn't already contain.

---

## 10. Troubleshooting

| Symptom | Likely cause |
|---|---|
| OpenSTA reports no timing paths | No liberty file passed, or the module has no clocked registers |
| EQY sanity check fails on itself | EQY install/version issue — fix before trusting real results |
| Every attempt rejected with "EQY could not prove equivalence" but testbench passes | Testbench coverage gap on the changed state, or the diagnosis is telling the LLM to make a bigger change than it should |
| Benchmark case silently skipped | Missing one of `case.v` / `case_tb.v` / `meta.json` in that case's folder |
| `run_all.py` fails immediately | Missing `manifest.json` in `--design-dir`, or a name in it doesn't match an actual `.v`/`_tb.v` pair |
| Everything "converges" suspiciously fast | Check `--liberty`/`--sdc` are actually being passed — without them, STA is skipped and only cell-count regression is checked |

---

## 11. Fanout extraction

`run_yosys()` now also writes a JSON netlist (`synth_netlist.json`) alongside
the Verilog output. `tools.compute_fanout()` reads it and counts, per net
bit, how many cell input ports it drives:

```python
from agent.tools import compute_fanout
fanout = compute_fanout("synth_netlist.json")
# {'max_fanout': 6, 'avg_fanout': 1.93, 'net_count': 28}
```

High-fanout nets add capacitive delay independent of logic depth (see the
study guide's Section G.1) — this is what actually measures it, rather than
inferring it from cell count alone.

---

## 12. A real bug that was found and fixed here — read this before trusting old numbers

While verifying this codebase against real Yosys output (not hand-typed
mock strings), `parse_yosys_stats()` was found to be silently broken: its
regex expected the pattern `"<number> cells"`, but Yosys actually prints
`"Number of cells:                 <number>"` — the two never matched, so
**every previous cell-count reading from this function was `0`**, no matter
what the design actually synthesized to.

This was caught because a scenario was run against real installed tools
instead of only mocked ones — every prior test in this project's own
development history used mock return values shaped like `"21 cells"`, which
happened to match the broken regex and masked the bug completely. **Mocked
tests confirm your orchestration logic; they cannot confirm your parsing
code matches what the real tool actually prints.** Run at least one real,
unmocked pass through `tools.py` on your own machine before trusting any
number this codebase reports — this bug is fixed as of this update, but the
lesson generalizes to anything you add to `tools.py` later.

---

## 13. What this manual doesn't cover

- Writing the 5-domain RTL itself (Section C of the blueprint)
- Writing the report prose around `report_data.md`'s tables
- Editing the demo video
