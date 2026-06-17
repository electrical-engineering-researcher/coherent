#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coherent_repro.checker import S1Checker
from coherent_repro.examples import SERIAL_TO_PARALLEL_SPEC
from coherent_repro.s1 import serial_to_parallel_reference_vhdl

checker = S1Checker(max_iterations=3)
result = checker.run_feedback_loop(
    original_spec=SERIAL_TO_PARALLEL_SPEC,
    initial_vhdl=serial_to_parallel_reference_vhdl(),
    workdir=Path("examples/checker_workdir"),
)
print("Passed:", result.passed)
print("Stage:", result.stage)
for d in result.diagnostics:
    print(d.to_prompt_block())
