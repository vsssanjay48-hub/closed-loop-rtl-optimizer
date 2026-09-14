# Terminal Recording Guide — Nebula Round 1 Video

Two recording segments needed, matching `Nebula_Video_Script.md`:
- **1:35–2:20** — real tool speed (Yosys + Icarus Verilog)
- **2:20–3:20** — the case study (the rejected fix)

Both use files already in `rtl_agent_starter.zip` under `demo/` and the new
`demo_case_study.py` at the project root. Do a dry run of both, off-camera,
before you record for real.

---

## Where to record

**Use the same terminal you already had OSS CAD Suite (Yosys/Icarus Verilog)
working in** — not the VS Code PowerShell terminal from your earlier
screenshot, which didn't have `bash` and isn't the environment your tools
are actually installed in. Use the OSS CAD Suite command prompt you used for
your very first toolchain log.

**Screen recording tool (pick one):**
- **OBS Studio** (free, Windows/Mac/Linux) — most reliable, lets you record
  just the terminal window or full screen with your face cam as a
  picture-in-picture source in the same recording.
- **Windows Game Bar** (`Win + G`) — already built into Windows, quick and
  good enough if you don't want to install anything.
- **ShareX** (free, Windows) — lightweight alternative if OBS feels heavy.

**Before you hit record:**
1. Resize the terminal window large, and increase the font size to at least
   18–20pt — small terminal text is the single most common reason a judge
   can't follow a recorded demo.
2. Widen the window so command output doesn't wrap mid-number.
3. `cd` into a clean working directory first and run `clear` (or `cls` on
   Windows cmd) so the terminal is empty before you start talking.
4. Do one full silent dry run of each command below to confirm it completes
   without errors on your machine, before recording the take you'll actually
   use.

---

## Segment 1 (1:35–2:20) — real tool speed

From inside the unzipped `rtl_agent/demo/` folder:

```bash
cd rtl_agent/demo
```

**Yosys synthesis** (say the line from the script while this runs, then let
the real output sit on screen):

```bash
yosys -p "read_verilog priority_encoder.v; synth -top priority_encoder; stat"
```

Look for this in the output — that's your real, on-screen cell count:

```
Number of cells:                 21
```

**Icarus Verilog exhaustive regression:**

```bash
iverilog -o sim.vvp priority_encoder.v priority_encoder_tb.v
vvp sim.vvp
```

You're watching for the line `TEST PASSED` — that's the 256-case exhaustive
result the script refers to.

**On timing:** don't try to hit a specific number. If you want a visible
wall-clock reading on screen instead of just letting it flash by, prefix
either command with `time` (Mac/Linux) or wrap it the way `tools.py` does
internally — but the honest move is to just say what your own terminal
shows, whatever that number is. Don't quote 1.55s or 0.37s on camera; those
were measured on a different machine and are not yours to claim.

---

## Segment 2 (2:20–3:20) — the case study (the rejected fix)

From the `rtl_agent/` project root (one level up from `demo/`):

```bash
cd ..
python demo_case_study.py
```

This runs the real orchestrator against `priority_encoder.v` — real Yosys,
real Icarus Verilog, real accept/reject decision. Only the LLM diagnosis and
the EQY equivalence result are stand-ins (announced out loud by the script
itself, matching what you say in the video).

**What you'll see, in order:**
1. A printed note announcing the LLM/EQY stub, out loud, before anything else
2. Real baseline cell count: `21`
3. Real regression result: `PASS`
4. Stubbed equivalence result: `PASS`
5. Real re-measured cell count after the proposed fix: `61`
6. Final decision: `REJECTED`, with the real reason printed

**Before recording this one:** run it once silently first. It writes a
`demo_run_logs/` folder — delete that folder before your real take so the
run is clean, not resuming from a previous state:

```bash
rm -rf demo_run_logs      # or: rmdir /s demo_run_logs   (Windows cmd)
```

---

## One thing to say honestly if asked

If a judge asks why the demo shows a stubbed LLM call: the direct answer is
the same one already in your report and script — no funded API key yet, so
the diagnosis/refactor steps use fixed, hand-written stand-ins, and
everything else (synthesis, regression, the reject decision) is completely
real. Don't improvise a different explanation in the moment; use the one
you already committed to in the script.
