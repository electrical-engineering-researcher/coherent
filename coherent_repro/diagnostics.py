"""Diagnostics passed back to the LLM repair module."""
from __future__ import annotations

import re
from typing import List
from .schemas import Diagnostic


def parse_ghdl_log(log: str, module_hint: str | None = None) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    for line in log.splitlines():
        if "width" in line.lower() and "match" in line.lower():
            etype = "width_mismatch"
        elif "no declaration" in line.lower() or "undeclared" in line.lower():
            etype = "undeclared_identifier"
        elif "port" in line.lower() and "map" in line.lower():
            etype = "port_map_error"
        else:
            etype = "compile_error"
        m = re.search(r":(\d+):", line)
        diagnostics.append(Diagnostic(error_type=etype, tool="ghdl", message=line, module=module_hint, line=int(m.group(1)) if m else None, raw_log=log))
    return diagnostics or [Diagnostic("compile_error", "ghdl", "Compilation failed but no parsable diagnostic was found.", module=module_hint, raw_log=log)]


def simulation_mismatch(expected: str, observed: str, time: str, signal: str) -> Diagnostic:
    return Diagnostic(
        error_type="simulation_mismatch",
        tool="testbench",
        message=f"Signal {signal} mismatch: expected {expected}, observed {observed} at {time}.",
        expected=expected,
        observed=observed,
        time=time,
    )


def make_repair_prompt(original_spec: str, current_design: str, diagnostics: List[Diagnostic]) -> str:
    diag_block = "\n\n".join(d.to_prompt_block() for d in diagnostics)
    return f"""You are repairing a VHDL design. Modify only the affected module unless the diagnostic proves that an interface change is necessary.

Original specification:
{original_spec}

Current VHDL design:
```vhdl
{current_design}
```

Diagnostics:
{diag_block}

Return only the corrected VHDL code and preserve all correct modules and port names.
"""
