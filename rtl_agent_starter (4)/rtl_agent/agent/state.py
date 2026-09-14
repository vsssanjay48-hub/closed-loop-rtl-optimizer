"""
Data model for one module's optimization run.

Everything the agent does gets recorded here. This is what makes the loop
auditable and replayable -- and it's also the raw material for Section F's
"failed case -> what extra input was needed" analysis, since every attempt
(successful or not) is kept, not just the final result.
"""

from __future__ import annotations
import json
import time
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Metrics:
    cell_count: Optional[int] = None
    wns_ns: Optional[float] = None          # worst negative slack, nanoseconds
    tns_ns: Optional[float] = None
    fmax_mhz: Optional[float] = None
    logic_depth: Optional[int] = None


@dataclass
class Attempt:
    attempt_num: int
    diagnosis: dict                          # raw Stage-1 JSON
    refactor_prompt: str                      # what was actually sent to Stage-2
    refactored_rtl: str                       # what Stage-2 returned
    syntax_ok: bool = False
    regression_ok: bool = False
    equivalence_checked: bool = False          # whether EQY was actually run for this attempt
    equivalence_ok: bool = False               # EQY formal PASS -- required for acceptance when enabled
    equivalence_report: str = ""               # raw EQY output, kept for the report's verification section
    error_log: str = ""                       # iverilog / simulation error text, if any
    metrics_after: Optional[Metrics] = None
    accepted: bool = False
    failure_reason: str = ""                  # human-readable, filled in on reject
    extra_input_needed: str = ""              # the agent's own guess at what would help
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModuleRun:
    module_path: str
    baseline_metrics: Metrics
    attempts: list[Attempt] = field(default_factory=list)
    final_status: str = "pending"             # pending | converged | reverted
    best_rtl: str = ""                        # last known-good RTL (starts as original)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2, default=str)

    def save(self, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        name = Path(self.module_path).stem
        (out_dir / f"{name}.run.json").write_text(self.to_json())
