# Video Script — Nebula@BITS-Goa Round 1 Submission
### Solo submission. Target runtime: 4:00–4:30. Face cam small corner throughout; main frame is diagrams/screen/terminal from the report.

Read this out loud once, with a stopwatch, before recording. If you're over
4:30 on the first read, cut from Section 6 (verification recap) first — it's
the most already-implied by the case study, not the newest information.

---

## 0:00–0:20 — Hook (face cam full-frame, no overlay yet)

**Don't open with "timing closure is hard."** Every other submission's video
will open with that. Open with the one thing that makes a judge sit up:

> "I built an AI agent that rewrites RTL to fix timing violations — and
> partway through testing it, I caught it making a fix worse, not better.
> I didn't catch that by reviewing the code by hand. My own system caught
> it, automatically, and rejected its own fix. That's what this video is
> actually about."

**Tip:** Say this directly to camera, no slides yet. It's a hook precisely
because it's counter to what every other pitch will claim ("our AI made it
better!"). A judge who has watched five "it just works" videos in a row
will remember the one that opens with a real failure caught in the act.

---

## 0:20–0:45 — Problem statement (face cam shrinks to corner; text overlay of the brief's constraints)

> "The brief asked for something specific: a design with five independent
> asynchronous clock domains, generated clocks off each, real clock-domain
> crossings, mixed divider ratios, at least 50,000 cells — and a solution
> that's fully automated, with no human approving any individual fix."

**On screen:** bullet list of the five design constraints (pull directly
from Section 2 of the report).

---

## 0:45–1:35 — Architecture walkthrough (screen share: `architecture_diagram.png`)

> "Here's the pipeline I built. It's nine stages, and every arrow is code,
> not a person. It synthesizes the design, gets real timing numbers, and
> runs a structural check for clock-domain crossings that timing analysis
> alone can't see. Then — and this is the part that matters — it diagnoses
> a problem *before* it touches any code. A separate model call only sees
> that one diagnosis and makes one targeted fix. Nothing gets rewritten
> blind."

**On screen:** the architecture diagram, cursor/pointer tracing stages 1
through 9 as you narrate. Pause half a beat on stage 7 ("Regression + EQY
gate") — say its name clearly, since it's the stage the rest of the video
depends on.

**Tip:** Don't read every box's label out loud — narrate the *shape* of the
flow (ingest → measure → diagnose → fix → prove → decide) and let the
diagram carry the detail. Reading all nine boxes verbatim is where scripts
like this usually drag.

---

## 1:35–2:20 — Real evidence, not slides (screen share: actual terminal)

This is the segment that separates your video from one built entirely out
of slides. Show a real terminal window, not a screenshot pasted into a
deck.

> "Everything I'm showing you right now is real — actual tools, actually
> installed, actually run by me. Here's Yosys synthesizing a test module —
> watch the cell count on screen. Here's the same module's testbench —
> 256 exhaustive test cases, every one passing."

**On screen (burn in as bold on-screen text, not just spoken):**
- Whatever wall-clock time your terminal actually shows for the Yosys run
- Whatever wall-clock time your terminal actually shows for the iverilog + vvp run
- `Number of cells: 21`

**Important:** Do not hardcode a specific timing number in your overlay
before recording. Run the commands in the "Recording Guide" doc once,
read what your own machine actually reports, and use that. Machine speed
varies — using your own real number is honest; copying a number from
someone else's machine (or from an earlier draft of this script) is not,
even if it was itself a real measurement somewhere else.

---

## 2:20–3:20 — The case study: the rejected fix (screen share: `case_a_comparison.png`)

This is your centerpiece. Give it the most time and the most energy.

> "Here's what actually happened. The agent correctly diagnosed a deep
> if-else chain as a timing bottleneck, and rewrote it into a case
> statement — which is the textbook fix. It passed every functional test.
> But when I re-measured it after synthesis, the 'fix' had actually gone
> from 21 cells to 61 — nearly triple. My system has a rule: if a
> change makes things meaningfully worse, even if it's functionally
> correct, reject it. So it did. Automatically. I didn't review that diff
> myself before it was rejected — the system already had."

**On screen:** the bar chart (21 vs 61 cells) side by side with the
pass/fail ledger (regression: PASS, formal equivalence: PASS, PPA guard:
FAIL → rejected).

> "This is the actual point of the project. An agent that only checks
> 'does it still work' isn't safe to run unsupervised. Mine also checks
> 'did this actually help' — and it's willing to say no to its own fix."

**Tip:** Slow down here. This is the one part of the video least likely to
appear in any other submission — a real, admitted rejection, shown with
real numbers. Don't rush past it to get to more "positive" content; this
*is* your strongest content.

---

## 3:20–3:45 — Verification, briefly (face cam corner, quick text overlay)

> "Every accepted fix has to clear two independent proofs: a functional
> regression, and a formal equivalence check — not just 'passes our
> tests,' but proven, mathematically, to behave identically to the
> original. If either fails, the system feeds the exact error back to
> itself and retries, up to a fixed limit, before giving up and
> reverting."

**On screen:** small text overlay: "Regression + Formal Equivalence (EQY),
both required."

**Tip:** This is the one section you can compress hardest if you're running
long — the case study already implied most of this. Two sentences is enough.

---

## 3:45–4:05 — Honest status: what's missing and why (face cam corner, text overlay)

State the API key limitation directly, first, not as a footnote buried in
softer language. This is a solo, self-funded project — say so plainly.

> "I want to be upfront about what's not finished yet, and why: this
> submission does not yet call a language model for real. I haven't
> funded an API key, so the diagnosis and rewrite steps you didn't see me
> run live are still using fixed, stand-in responses I wrote myself, not
> live model output. Everything else — the synthesis, the regression, the
> rejection you just watched — is completely real, run on real tools, by
> me, on my own machine. The API key is the one piece standing between
> this and a fully live run, and it's next."

**On screen:** small text overlay: "LLM calls: not yet funded (API key
pending). Everything else on screen: real, measured."

**Tip:** Say this plainly and once — do not apologize for it repeatedly or
hedge five different ways. One clear, direct sentence about what's missing
and why reads as honest and in control. Repeating the caveat three
different ways reads as anxious and undermines the strong material you
just showed.

---

## 4:05–4:25 — Close (face cam full-frame)

> "The reason this matters isn't that my agent writes good RTL — plenty of
> tools can propose a fix. It's that it knows when its own fix isn't
> actually good, and stops itself, with no one watching. That's the
> property a fully-automated system needs most, and it's the one thing in
> this video that isn't a projection — it already happened, on real
> hardware description language, in front of real tools. Thank you."

**Tip:** End on the claim you can actually defend, not a hype line. "Thank
you" immediately after — don't let energy trail off with a mumbled
sign-off.

---

## Delivery tips to make this stand out

- **Face cam small, corner, entire video** — not full-frame except the
  open and close. A judge watching many videos back to back will fatigue
  on talking-head-only content fast; diagrams and terminal output carry
  attention better once the hook has landed.
- **Burn in key numbers as on-screen text**, don't rely on voiceover alone
  — 21, 61, and 256/256, plus whatever real timing your own run shows. These are what get written down.
- **Use the real terminal, captured live**, not a screenshot dropped into
  a slide. Panelists can tell the difference, and it's your strongest
  evidence that this isn't vaporware.
- **Do not read the script verbatim on camera.** Know the beats (hook →
  architecture → real evidence → rejected case → honest status → close)
  and talk naturally through them. A read-aloud script sounds read-aloud,
  and judges notice.
- **Say "I," not "we," consistently** — this is a solo submission, and a
  judge noticing a mismatch between spoken "we" and a one-person team
  roster reads worse than just being direct about working alone.
- **State the API key limitation once, plainly, and move on.** Solo
  entrants without funded API access are a normal, explainable situation —
  treat it that way rather than over-apologizing for it.
- **Rehearse against a visible stopwatch at least twice** before the real
  recording. The rejected-fix segment (2:20–3:20) is the one place it's
  worth over-running slightly if you have to choose — it's your strongest
  material.
- **Caption the video** (even auto-captions cleaned up) — panelists
  sometimes watch a stack of these on mute first before deciding which to
  watch with sound.
- **Don't end with a limitations list.** One clean sentence, once, in the
  status section (3:45–4:05) is enough. Repeating caveats at the end
  undercuts the confident close.
