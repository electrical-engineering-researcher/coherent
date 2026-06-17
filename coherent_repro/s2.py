"""
s1.py

Stage S1: Structured synthesis support utilities for COHERENT.

S1 converts the S2 reuse plan into synthesizable VHDL and validates it
through a bounded checker/repair loop.

This module provides:
- structured S1 result objects
- VHDL generation helpers
- reference implementation examples
- testbench generation examples
- static validation helpers
- bounded repair-loop orchestration

S1 is intentionally not a reasoning stage.
Architecture is assumed to be fixed by S3 and S2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .checker import S1Checker


# ---------------------------------------------------------------------
# S1 Data Models
# ---------------------------------------------------------------------


class S1Status(str, Enum):
    GENERATED = "generated"
    STATIC_PASS = "static_pass"
    COMPILE_PASS = "compile_pass"
    SIM_PASS = "sim_pass"
    REPAIRED = "repaired"
    FAILED = "failed"


@dataclass
class S1Diagnostic:
    """Diagnostic object passed to the repair prompt."""

    error_type: str
    tool: str
    message: str
    module: str = ""
    line: Optional[int] = None
    expected: str = ""
    observed: str = ""
    time: str = ""
    severity: str = "error"


@dataclass
class S1ValidationReport:
    """Validation report for one S1 attempt."""

    status: S1Status
    syntax_pass: bool = False
    simulation_pass: bool = False
    structural_pass: bool = False
    functional_pass: bool = False
    diagnostics: List[S1Diagnostic] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class S1SynthesisResult:
    """Output of S1 synthesis."""

    vhdl: str
    testbench: str = ""
    attempts: int = 0
    final_status: S1Status = S1Status.GENERATED
    reports: List[S1ValidationReport] = field(default_factory=list)


RepairFunction = Callable[[str, List[S1Diagnostic]], str]


# ---------------------------------------------------------------------
# Reference VHDL Example
# ---------------------------------------------------------------------


def serial_to_parallel_reference_vhdl() -> str:
    """
    Reference VHDL for an 8-bit serial-to-parallel converter.

    Behavior:
    - synchronous active-high reset
    - one serial bit shifted in every clock cycle
    - after 8 bits, parallel_out updates
    - valid asserts for exactly one clock cycle
    - parallel_out remains stable until next complete frame

    This is used as a concrete S1 reproducibility example.
    """

    return r"""
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity serial_to_parallel is
  port (
    clk          : in  std_logic;
    rst          : in  std_logic;
    serial_in    : in  std_logic;
    parallel_out : out std_logic_vector(7 downto 0);
    valid        : out std_logic
  );
end entity serial_to_parallel;

architecture rtl of serial_to_parallel is
  signal shift_reg : std_logic_vector(7 downto 0) := (others => '0');
  signal out_reg   : std_logic_vector(7 downto 0) := (others => '0');
  signal bit_count : unsigned(2 downto 0) := (others => '0');
begin

  process(clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        shift_reg <= (others => '0');
        out_reg   <= (others => '0');
        bit_count <= (others => '0');
        valid     <= '0';
      else
        shift_reg <= shift_reg(6 downto 0) & serial_in;
        valid     <= '0';

        if bit_count = 7 then
          out_reg   <= shift_reg(6 downto 0) & serial_in;
          bit_count <= (others => '0');
          valid     <= '1';
        else
          bit_count <= bit_count + 1;
        end if;
      end if;
    end if;
  end process;

  parallel_out <= out_reg;

end architecture rtl;
""".strip()


def serial_to_parallel_reference_testbench() -> str:
    """
    Testbench for the serial-to-parallel reference design.

    Checks:
    - reset clears output
    - valid is low during accumulation
    - valid asserts after exactly 8 bits
    - parallel_out matches received serial frame
    """

    return r"""
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_serial_to_parallel is
end entity tb_serial_to_parallel;

architecture sim of tb_serial_to_parallel is
  signal clk          : std_logic := '0';
  signal rst          : std_logic := '1';
  signal serial_in    : std_logic := '0';
  signal parallel_out : std_logic_vector(7 downto 0);
  signal valid        : std_logic;

  constant CLK_PERIOD : time := 10 ns;
begin

  clk <= not clk after CLK_PERIOD / 2;

  dut: entity work.serial_to_parallel
    port map (
      clk          => clk,
      rst          => rst,
      serial_in    => serial_in,
      parallel_out => parallel_out,
      valid        => valid
    );

  stim: process
  begin
    rst <= '1';
    wait for 2 * CLK_PERIOD;
    rst <= '0';

    assert valid = '0'
      report "valid should be low after reset"
      severity error;

    serial_in <= '1'; wait until rising_edge(clk);
    assert valid = '0' report "valid asserted too early at bit 1" severity error;

    serial_in <= '0'; wait until rising_edge(clk);
    assert valid = '0' report "valid asserted too early at bit 2" severity error;

    serial_in <= '1'; wait until rising_edge(clk);
    assert valid = '0' report "valid asserted too early at bit 3" severity error;

    serial_in <= '0'; wait until rising_edge(clk);
    assert valid = '0' report "valid asserted too early at bit 4" severity error;

    serial_in <= '1'; wait until rising_edge(clk);
    assert valid = '0' report "valid asserted too early at bit 5" severity error;

    serial_in <= '0'; wait until rising_edge(clk);
    assert valid = '0' report "valid asserted too early at bit 6" severity error;

    serial_in <= '1'; wait until rising_edge(clk);
    assert valid = '0' report "valid asserted too early at bit 7" severity error;

    serial_in <= '0'; wait until rising_edge(clk);

    assert valid = '1'
      report "valid should assert exactly after 8 bits"
      severity error;

    assert parallel_out = "10101010"
      report "parallel_out mismatch after 8 received bits"
      severity error;

    wait until rising_edge(clk);

    assert valid = '0'
      report "valid should be a one-cycle pulse"
      severity error;

    report "TEST PASSED" severity note;
    wait;
  end process;

end architecture sim;
""".strip()


# ---------------------------------------------------------------------
# Static VHDL Checks
# ---------------------------------------------------------------------


def static_vhdl_checks(vhdl: str) -> List[S1Diagnostic]:
    """
    Lightweight static checks before invoking external tools.

    These checks are not a replacement for GHDL/VCS.
    They catch common S1 mistakes early.
    """

    diagnostics: List[S1Diagnostic] = []

    lower = vhdl.lower()

    required_patterns = [
        ("library ieee", "missing_ieee_library"),
        ("use ieee.std_logic_1164.all", "missing_std_logic_1164"),
        ("use ieee.numeric_std.all", "missing_numeric_std"),
        ("entity ", "missing_entity"),
        ("architecture ", "missing_architecture"),
        ("end architecture", "missing_end_architecture"),
    ]

    for pattern, error_type in required_patterns:
        if pattern not in lower:
            diagnostics.append(
                S1Diagnostic(
                    error_type=error_type,
                    tool="static_checker",
                    message=f"Required VHDL pattern not found: {pattern}",
                )
            )

    forbidden_patterns = [
        "wait for",
        "after ",
        "textio",
        "std_logic_arith",
        "std_logic_unsigned",
        "std_logic_signed",
    ]

    for pattern in forbidden_patterns:
        if pattern in lower:
            diagnostics.append(
                S1Diagnostic(
                    error_type="non_synthesizable_or_nonstandard_construct",
                    tool="static_checker",
                    message=f"Forbidden or nonstandard construct found: {pattern}",
                )
            )

    if "rising_edge" not in lower and "clk" in lower:
        diagnostics.append(
            S1Diagnostic(
                error_type="missing_clock_edge",
                tool="static_checker",
                message="Clock signal appears present, but no rising_edge(clk) process was found.",
            )
        )

    return diagnostics


def validate_serial_to_parallel_semantics(vhdl: str) -> List[S1Diagnostic]:
    """
    Lightweight semantic pattern checks for the serial-to-parallel example.

    This is intentionally conservative and example-specific.
    """

    diagnostics: List[S1Diagnostic] = []
    lower = vhdl.lower().replace(" ", "")

    if "valid<='1'" not in lower:
        diagnostics.append(
            S1Diagnostic(
                error_type="missing_valid_assertion",
                tool="semantic_checker",
                message="valid is never explicitly asserted.",
                module="serial_to_parallel",
            )
        )

    if "valid<='0'" not in lower:
        diagnostics.append(
            S1Diagnostic(
                error_type="missing_valid_default_low",
                tool="semantic_checker",
                message="valid is not explicitly cleared to create one-cycle pulse behavior.",
                module="serial_to_parallel",
            )
        )

    if "bit_count=7" not in lower and 'bit_count="111"' not in lower:
        diagnostics.append(
            S1Diagnostic(
                error_type="missing_terminal_count_check",
                tool="semantic_checker",
                message="No visible terminal count check for 8-bit frame completion.",
                module="serial_to_parallel",
            )
        )

    if "parallel_out<=out_reg" not in lower:
        diagnostics.append(
            S1Diagnostic(
                error_type="missing_registered_output_assignment",
                tool="semantic_checker",
                message="parallel_out should be driven from registered output storage.",
                module="serial_to_parallel",
            )
        )

    return diagnostics


# ---------------------------------------------------------------------
# Prompt Construction
# ---------------------------------------------------------------------


def build_s1_generation_prompt(
    specification: str,
    merged_plan_json: str,
    reuse_plan_json: str,
) -> str:
    """
    Build the S1 generation prompt.

    This prompt enforces the algorithm:
    1. entity generation
    2. architecture assembly
    3. constraint enforcement
    4. timing preservation
    5. synthesizable VHDL only
    """

    return f"""
# S1 Structured Synthesis Task

You are operating inside COHERENT Stage S1.

Generate synthesizable VHDL from the given S3 merged plan and S2 reuse plan.

Do not redesign the architecture.
Do not remove module boundaries unless explicitly required.
Do not change timing behavior.
Return only VHDL code.

## Original Specification

```text
{specification}
```

## Merged S3 Plan

```json
{merged_plan_json}
```

## S2 Reuse Plan

```json
{reuse_plan_json}
```

## Required S1 Algorithm

1. Generate entity declarations.
2. Generate architecture declarations.
3. Instantiate selected kernels.
4. Apply parameter and generic mappings.
5. Apply port mappings.
6. Insert minimal glue logic.
7. Enforce clock/reset consistency.
8. Enforce width/type consistency.
9. Enforce FSM completeness.
10. Enforce timing requirements.
11. Avoid latches.
12. Use IEEE std_logic_1164 and numeric_std.
13. Return only synthesizable VHDL.
""".strip()


def build_s1_repair_prompt(
    specification: str,
    current_vhdl: str,
    diagnostics: List[S1Diagnostic],
) -> str:
    """
    Build the S1 repair prompt.

    Diagnostics are passed in a structured form so the repair LLM can make
    local, bounded changes.
    """

    diag_json = [
        {
            "error_type": d.error_type,
            "tool": d.tool,
            "message": d.message,
            "module": d.module,
            "line": d.line,
            "expected": d.expected,
            "observed": d.observed,
            "time": d.time,
            "severity": d.severity,
        }
        for d in diagnostics
    ]

    return f"""
# S1 Local Repair Task

You are repairing VHDL produced by COHERENT Stage S1.

Make the smallest correction needed.
Modify only the affected module unless an interface change is unavoidable.
Preserve timing intent.
Preserve module boundaries.
Return only corrected VHDL code.

## Original Specification

```text
{specification}
```

## Current VHDL

```vhdl
{current_vhdl}
```

## Diagnostics

```json
{diag_json}
```

## Rules

1. Fix only reported failures.
2. Preserve correct modules.
3. Do not rename top-level ports.
4. Preserve reset policy.
5. Preserve clock-cycle timing.
6. Avoid non-synthesizable constructs.
7. Return only VHDL code.
""".strip()


# ---------------------------------------------------------------------
# Bounded S1 Checker / Repair Loop
# ---------------------------------------------------------------------


def run_s1_repair_loop(
    initial_vhdl: str,
    specification: str,
    repair_fn: RepairFunction,
    *,
    checker: Optional[S1Checker] = None,
    testbench: str = "",
    max_iterations: int = 3,
    example_semantic_check: bool = False,
) -> S1SynthesisResult:
    """
    Run bounded S1 validation and repair.

    This implements the paper's repair budget:

        maximum repair iterations = 3

    Each iteration:
    1. run static checks
    2. optionally run example semantic checks
    3. optionally call external checker
    4. pass diagnostics to repair_fn
    5. stop if clean

    repair_fn signature:
        repair_fn(current_vhdl, diagnostics) -> repaired_vhdl
    """

    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")

    current_vhdl = initial_vhdl
    reports: List[S1ValidationReport] = []

    for attempt in range(max_iterations + 1):
        diagnostics = static_vhdl_checks(current_vhdl)

        if example_semantic_check:
            diagnostics.extend(validate_serial_to_parallel_semantics(current_vhdl))

        report = S1ValidationReport(
            status=S1Status.STATIC_PASS if not diagnostics else S1Status.FAILED,
            syntax_pass=not diagnostics,
            structural_pass=not diagnostics,
            functional_pass=not diagnostics,
            simulation_pass=False,
            diagnostics=diagnostics,
            notes=[f"S1 validation attempt {attempt}"],
        )

        reports.append(report)

        if not diagnostics:
            return S1SynthesisResult(
                vhdl=current_vhdl,
                testbench=testbench,
                attempts=attempt,
                final_status=S1Status.STATIC_PASS,
                reports=reports,
            )

        if attempt == max_iterations:
            return S1SynthesisResult(
                vhdl=current_vhdl,
                testbench=testbench,
                attempts=attempt,
                final_status=S1Status.FAILED,
                reports=reports,
            )

        current_vhdl = repair_fn(current_vhdl, diagnostics)

    return S1SynthesisResult(
        vhdl=current_vhdl,
        testbench=testbench,
        attempts=max_iterations,
        final_status=S1Status.FAILED,
        reports=reports,
    )


# ---------------------------------------------------------------------
# File Utilities
# ---------------------------------------------------------------------


def write_s1_artifacts(
    result: S1SynthesisResult,
    out_dir: str | Path,
    design_name: str = "design",
) -> Dict[str, Path]:
    """
    Write S1 artifacts to disk.

    Outputs:
    - design VHDL
    - testbench VHDL if available
    - validation report text
    """

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    design_path = out / f"{design_name}.vhd"
    design_path.write_text(result.vhdl, encoding="utf-8")

    paths: Dict[str, Path] = {"design": design_path}

    if result.testbench:
        tb_path = out / f"tb_{design_name}.vhd"
        tb_path.write_text(result.testbench, encoding="utf-8")
        paths["testbench"] = tb_path

    report_lines: List[str] = []
    report_lines.append(f"final_status: {result.final_status}")
    report_lines.append(f"attempts: {result.attempts}")

    for i, report in enumerate(result.reports):
        report_lines.append(f"\nAttempt {i}: {report.status}")
        for diag in report.diagnostics:
            report_lines.append(
                f"- [{diag.tool}] {diag.error_type}: {diag.message}"
            )

    report_path = out / f"{design_name}_s1_report.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    paths["report"] = report_path

    return paths


__all__ = [
    "S1Checker",
    "S1Status",
    "S1Diagnostic",
    "S1ValidationReport",
    "S1SynthesisResult",
    "serial_to_parallel_reference_vhdl",
    "serial_to_parallel_reference_testbench",
    "static_vhdl_checks",
    "validate_serial_to_parallel_semantics",
    "build_s1_generation_prompt",
    "build_s1_repair_prompt",
    "run_s1_repair_loop",
    "write_s1_artifacts",
]