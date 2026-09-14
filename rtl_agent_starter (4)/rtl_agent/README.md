# RTL Refactoring Agent — Starter Codebase

This is the closed-loop agent from Section B of the blueprint, extended to
cover the full deliverable list from the official Tools & Resources brief:
formal equivalence checking (EQY), a once-per-version OpenROAD PPA
snapshot, a repeated-trial benchmark runner, and a report-data generator.

**See `USER_MANUAL.md` for full setup, usage, and troubleshooting.** This
README is just the file inventory and quick orientation.

## Setup

```bash
pip install anthropic
export ANTHROPIC_API_KEY=your_key_here

# Confirm your existing toolchain is on PATH (from your OSS CAD Suite setup)
iverilog -V
yosys -V
sta -help          # OpenSTA, once you install it — see Section 1 of the blueprint's Session 2
```

## Running it on one module

```bash
python -m agent.orchestrator path/to/module.v path/to/module_tb.v \
    --top module_name \
    --liberty path/to/sky130_fd_sc_hd.lib \
    --sdc path/to/module.sdc \
    --out-dir run_logs
```

Without `--liberty`/`--sdc` it still runs — synthesis and CDC lint work, but
timing numbers stay unavailable (matching the "No timing paths found" state
your last log was in). Add `--no-eqy` to skip formal equivalence checking
while debugging the loop itself — but don't submit results generated that
way without saying so; the brief names formal equivalence explicitly.

**Testbench convention:** your testbench must print `TEST PASSED` or
`TEST FAILED` on its own line — that's what `tools.run_iverilog()` greps for
to decide accept/reject.

Full usage — the benchmark runner, the OpenROAD snapshot, the report-data
generator, and the one-command `run_all.py` driver — is in
**`USER_MANUAL.md`**.

## What each file is

| File | Role |
|---|---|
| `agent/tools.py` | Subprocess wrappers around iverilog/vvp, yosys, OpenSTA |
| `agent/cdc_lint.py` | Structural (rule-based, not formal) CDC checker |
| `agent/sdc_gen.py` | Generates the multi-clock SDC from a Python clock list |
| `agent/eqy_check.py` | Formal equivalence checking (SymbiYosys/EQY) |
| `agent/openroad_snapshot.py` | Once-per-version placed/routed PPA snapshot |
| `agent/prompts.py` | The two-stage prompt templates |
| `agent/llm_stages.py` | The actual LLM calls — Stage 1 diagnose, Stage 2 refactor, self-heal |
| `agent/state.py` | Per-module run log data model (`ModuleRun`, `Attempt`) |
| `agent/orchestrator.py` | The closed loop — now gates on regression **and** EQY |
| `agent/benchmark.py` | Runs the loop across many broken cases, with repeats |
| `agent/report_gen.py` | Turns run logs into report-ready markdown tables |
| `agent/run_all.py` | One command: real design → benchmark → report data |

## How this maps back to the blueprint

- **Stage 1 / Stage 2 split** (Section B, stages 5–6): `llm_stages.stage1_diagnose()`
  and `stage2_refactor()` are separate calls with separate system prompts —
  Stage 2 never sees the STA report, only one diagnosis at a time.
- **Self-healing** (Section B, stage 8): `llm_stages.self_heal_retry()`, called
  from `orchestrator.run_module()` up to `MAX_RETRIES_PER_DIAGNOSIS` times.
- **Regression + formal equivalence gate** (Section B, stage 7, extended):
  `orchestrator._verify()` now runs iverilog regression **and** EQY. An
  attempt is only accepted if both pass — a testbench pass alone is not
  enough, which directly answers the "formal equivalence verification
  report" deliverable added in the later brief.
- **Failure logging / "what extra input was needed"** (Section F): every
  `Attempt` records `failure_reason` and `extra_input_needed` even when it
  fails — pulled automatically into `report_gen.py`'s failure-analysis
  table. Right now those messages are hand-written heuristics in the
  orchestrator; a good next step is asking the LLM itself, after a failed
  attempt, "what context would have helped you fix this" and logging *that*
  instead.
- **Success rate with repeats** (Section A.2): `benchmark.py` runs each
  case multiple times, not once — a single pass/fail per issue isn't a
  defensible statistic given LLM non-determinism.

## Known limitations to state plainly in your write-up

- `cdc_lint.py` is structural pattern-matching, not a formal CDC tool. It
  catches missing synchronizers on directly-named signals; it will not catch
  reconvergence (Section G.4) or crossings hidden behind non-obvious signal
  renaming.
- The "regressed >50%" area guard in `orchestrator.py` is a placeholder
  sanity check, not a real PPA policy — replace with an actual area/WNS
  trade-off rule once you have real OpenSTA numbers to weigh against.
- `_extract_domain_map` in `cdc_lint.py` takes the *first* assignment to a
  signal as its domain — fine for the simple always-block style used in the
  Section C sub-blocks, but will misattribute domain on more complex
  multiply-driven signals.

## Next step after this runs cleanly on one module

Loop `orchestrator.run_module()` over every sub-block of the Penta-Domain
Fabric, aggregate the `ModuleRun` logs, and that aggregate is your Session 5
success-rate statistic and failure-case report.
