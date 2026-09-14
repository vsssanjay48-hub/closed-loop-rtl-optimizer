"""
Programmatic SDC generation for the 5-master / 10+-clock design.

Writing an SDC by hand for 5 unrelated masters plus their generated clocks
is exactly the kind of thing that goes stale silently when you rename a
signal. This module makes the clock list the single source of truth --
change it here, regenerate, done.

OpenSTA (and any real STA tool) needs two things it cannot infer on its
own: (1) that a net is a clock at all, and (2) for a generated clock,
which master it's derived from and at what divide ratio -- otherwise it
will treat every register on that net as if it were on an unrelated,
unconstrained clock, and you'll get meaningless timing numbers.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ClockSpec:
    name: str            # SDC clock name, e.g. "clk_a"
    port: str             # RTL port/net name the clock is defined on
    period_ns: float      # full period in nanoseconds
    uncertainty_ns: float = 0.05   # clock jitter/skew margin -- keep nonzero, real designs never have zero


@dataclass
class GeneratedClockSpec:
    name: str              # SDC clock name, e.g. "clk_a_div2"
    port: str              # net the generated clock appears on
    source_port: str       # the master clock port it's derived from
    divide_by: int         # integer divide ratio (2, 3, 4, 5, 6, ...)
    edge_shift: str = ""   # optional -edges override for odd ratios; leave "" for default


def generate_sdc(clocks: list[ClockSpec], generated: list[GeneratedClockSpec]) -> str:
    lines: list[str] = [
        "# Auto-generated SDC -- do not hand-edit, regenerate from sdc_gen.py",
        "# Five independent master clocks, deliberately unrelated periods,",
        "# plus their generated (divided) clocks.",
        "",
    ]

    for c in clocks:
        lines.append(f"create_clock -name {c.name} -period {c.period_ns} [get_ports {c.port}]")
        lines.append(f"set_clock_uncertainty {c.uncertainty_ns} [get_clocks {c.name}]")
        lines.append("")

    for g in generated:
        if g.edge_shift:
            lines.append(
                f"create_generated_clock -name {g.name} -source [get_ports {g.source_port}] "
                f"-edges {{{g.edge_shift}}} [get_ports {g.port}]"
            )
        else:
            lines.append(
                f"create_generated_clock -name {g.name} -source [get_ports {g.source_port}] "
                f"-divide_by {g.divide_by} [get_ports {g.port}]"
            )
        lines.append("")

    # Because the 5 masters are genuinely asynchronous to each other, any
    # path crossing between their clock groups must be excluded from
    # single-clock setup/hold analysis -- that is exactly what the CDC
    # synchronizers exist to handle, not STA. Group each master (plus its
    # own generated clocks) separately and mark cross-group paths false.
    lines.append("# Async clock groups -- paths BETWEEN groups are handled by CDC")
    lines.append("# synchronizers (see cdc_lint.py), not by timing closure, so they")
    lines.append("# are excluded here rather than reported as spurious violations.")
    master_names = [c.name for c in clocks]
    group_clauses = []
    for master in master_names:
        members = [master] + [g.name for g in generated if g.source_port ==
                               next(c.port for c in clocks if c.name == master)]
        group_clauses.append("[get_clocks {" + " ".join(members) + "}]")
    lines.append("set_clock_groups -asynchronous \\")
    lines.append("    " + " \\\n    ".join(group_clauses))
    lines.append("")

    return "\n".join(lines)


def write_sdc(path: str, clocks: list[ClockSpec], generated: list[GeneratedClockSpec]) -> None:
    with open(path, "w") as f:
        f.write(generate_sdc(clocks, generated))
