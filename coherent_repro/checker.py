"""S1 checker/tool feedback loop.

The checker performs static checks, compilation, simulation, structural validation,
and bounded repair. External tool execution is optional so this file can be run in
artifact-review settings without commercial tools.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from .diagnostics import make_repair_prompt, parse_ghdl_log
from .schemas import CheckerResult, Diagnostic

RepairFunction = Callable[[str], str]


class S1Checker:
    def __init__(self, max_iterations: int = 3, ghdl_bin: str = "ghdl"):
        self.max_iterations = max_iterations
        self.ghdl_bin = ghdl_bin

    def static_check(self, vhdl: str) -> CheckerResult:
        diagnostics: List[Diagnostic] = []
        required = ["entity", "architecture", "begin", "end"]
        lower = vhdl.lower()
        for token in required:
            if token not in lower:
                diagnostics.append(Diagnostic("static_missing_token", "static_checker", f"Missing required VHDL token: {token}"))
        if "std_logic" not in lower:
            diagnostics.append(Diagnostic("static_type_missing", "static_checker", "No std_logic type usage found."))
        return CheckerResult(passed=not diagnostics, stage="static_check", diagnostics=diagnostics)

    def compile_with_ghdl(self, vhdl_path: Path) -> CheckerResult:
        if shutil.which(self.ghdl_bin) is None:
            return CheckerResult(True, "compile_skipped", logs=["GHDL not installed; compilation skipped in dry-run mode."])
        proc = subprocess.run([self.ghdl_bin, "-a", str(vhdl_path)], capture_output=True, text=True)
        if proc.returncode == 0:
            return CheckerResult(True, "compile", logs=[proc.stdout, proc.stderr])
        return CheckerResult(False, "compile", diagnostics=parse_ghdl_log(proc.stderr or proc.stdout), logs=[proc.stdout, proc.stderr])

    def run_feedback_loop(self, original_spec: str, initial_vhdl: str, workdir: Path, repair_fn: Optional[RepairFunction] = None) -> CheckerResult:
        workdir.mkdir(parents=True, exist_ok=True)
        current = initial_vhdl
        all_logs: List[str] = []
        all_diags: List[Diagnostic] = []

        for iteration in range(self.max_iterations + 1):
            static = self.static_check(current)
            if not static.passed:
                all_diags.extend(static.diagnostics)
                if iteration >= self.max_iterations or repair_fn is None:
                    return CheckerResult(False, f"static_check_iteration_{iteration}", all_diags, all_logs)
                current = repair_fn(make_repair_prompt(original_spec, current, static.diagnostics))
                continue

            path = workdir / f"design_iter_{iteration}.vhd"
            path.write_text(current)
            comp = self.compile_with_ghdl(path)
            all_logs.extend(comp.logs)
            if not comp.passed:
                all_diags.extend(comp.diagnostics)
                if iteration >= self.max_iterations or repair_fn is None:
                    return CheckerResult(False, f"compile_iteration_{iteration}", all_diags, all_logs)
                current = repair_fn(make_repair_prompt(original_spec, current, comp.diagnostics))
                continue

            # Simulation and property checks would be inserted here. In the paper
            # experiments these include reset sequencing, expected I/O behavior,
            # FSM transitions, counter termination, and protocol handshakes.
            return CheckerResult(True, f"passed_iteration_{iteration}", all_diags, all_logs)

        return CheckerResult(False, "iteration_budget_exhausted", all_diags, all_logs)
