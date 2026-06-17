"""
examples.py

Canonical example objects used in documentation, tests, and reproducibility
artifacts for COHERENT.

This file intentionally contains detailed example metadata because reviewers
often ask whether the framework is reproducible from the paper.

The examples show:

1. S3 candidate plans
2. S2 kernel library records
3. kernel provenance categories
4. timing assumptions
5. reset policy
6. interface definitions
7. adaptation cases
8. contamination-separation metadata

Main running example:
    8-bit serial-to-parallel converter
"""

from __future__ import annotations

from .schemas import (
    CandidatePlan,
    Direction,
    FSM,
    KernelMetadata,
    Module,
    Port,
    Signal,
    TimingRequirement,
)


# ---------------------------------------------------------------------
# Canonical Specification
# ---------------------------------------------------------------------


SERIAL_TO_PARALLEL_SPEC = (
    "Design an 8-bit serial-to-parallel converter. "
    "Capture one serial bit per clock, accumulate 8 bits, then update "
    "parallel_out and assert valid for one cycle. Use synchronous reset."
)


# ---------------------------------------------------------------------
# Common Ports
# ---------------------------------------------------------------------


def serial_to_parallel_ports() -> list[Port]:
    """
    Common top-level ports for the serial-to-parallel example.
    """

    return [
        Port("clk", Direction.IN, width=1, dtype="std_logic"),
        Port("rst", Direction.IN, width=1, dtype="std_logic"),
        Port("serial_in", Direction.IN, width=1, dtype="std_logic"),
        Port(
            "parallel_out",
            Direction.OUT,
            width=8,
            dtype="std_logic_vector",
            role="registered parallel output",
        ),
        Port("valid", Direction.OUT, width=1, dtype="std_logic", role="one-cycle frame-valid pulse"),
    ]


# ---------------------------------------------------------------------
# S3 Candidate Plans
# ---------------------------------------------------------------------


def serial_to_parallel_candidate_plans() -> list[CandidatePlan]:
    """
    Return three S3 candidate plans for the serial-to-parallel example.

    P1:
        Main intended architecture:
        shift register + bit counter + Moore FSM.

    P2:
        Lower-confidence interpretation:
        shift register output is continuously visible.
        This is included to show how S3 captures ambiguity.

    P3:
        Strong alternative:
        explicit guarded output register controlled by FSM.
    """

    common_ports = serial_to_parallel_ports()

    p1 = CandidatePlan(
        plan_id="P1_shift_counter_fsm",
        original_spec=SERIAL_TO_PARALLEL_SPEC,
        ports=common_ports,
        modules=[
            Module(
                "shift_register",
                "datapath",
                role="accumulate serial bits into an 8-bit frame",
            ),
            Module(
                "bit_counter",
                "counter",
                role="count received serial bits from 0 to 7",
            ),
            Module(
                "control_fsm",
                "fsm",
                role="assert valid when frame accumulation completes",
            ),
        ],
        signals=[
            Signal(
                "shift_reg",
                8,
                "std_logic_vector",
                producer="module:shift_register",
                consumers=["module:control_fsm", "port:parallel_out"],
                role="internal serial accumulation register",
                reset_value="00000000",
            ),
            Signal(
                "bit_count",
                3,
                "unsigned",
                producer="module:bit_counter",
                consumers=["module:control_fsm"],
                role="tracks number of received bits",
                reset_value="000",
            ),
            Signal(
                "count_done",
                1,
                "std_logic",
                producer="module:bit_counter",
                consumers=["module:control_fsm"],
                role="terminal-count pulse after 8 bits",
                reset_value="0",
            ),
            Signal(
                "valid_int",
                1,
                "std_logic",
                producer="module:control_fsm",
                consumers=["port:valid"],
                role="internal one-cycle valid pulse",
                reset_value="0",
            ),
        ],
        fsms=[
            FSM(
                "control_fsm",
                ["IDLE", "SHIFT", "OUTPUT"],
                "IDLE",
                transitions=[
                    {"from": "IDLE", "to": "SHIFT", "condition": "rst = 0"},
                    {"from": "SHIFT", "to": "OUTPUT", "condition": "count_done = 1"},
                    {"from": "OUTPUT", "to": "SHIFT", "condition": "next clock"},
                ],
                output_style="moore",
            )
        ],
        datapath=[
            "8-bit shift_register",
            "3-bit bit_counter",
            "registered parallel output path",
        ],
        timing=[
            TimingRequirement(
                "frame_latency",
                "parallel_out updates only after 8 valid serial bits are received",
                8,
                "bit_counter_terminal_count",
            ),
            TimingRequirement(
                "valid_pulse",
                "valid asserts for exactly one clock cycle at frame completion",
                1,
                "control_fsm_output_state",
            ),
        ],
        reset_policy="synchronous",
        constraints=[
            "one serial bit captured per rising clock edge",
            "valid asserted for one cycle after 8 bits",
            "parallel_out must not update early during partial frame",
            "no latch inference",
            "use numeric_std for counter arithmetic",
        ],
        assumptions=[
            "serial_in is sampled on rising_edge(clk)",
            "rst is active-high",
            "parallel_out remains stable between complete frames",
        ],
        confidence=0.95,
    )

    p2 = CandidatePlan(
        plan_id="P2_continuous_output",
        original_spec=SERIAL_TO_PARALLEL_SPEC,
        ports=common_ports,
        modules=[
            Module(
                "shift_register",
                "datapath",
                role="continuously expose current shift-register contents",
            ),
            Module(
                "bit_counter",
                "counter",
                role="count received bits and assert valid after 8 bits",
            ),
        ],
        signals=[
            Signal(
                "shift_reg",
                8,
                "std_logic_vector",
                producer="module:shift_register",
                consumers=["port:parallel_out"],
                role="continuously visible shift register",
                reset_value="00000000",
            ),
            Signal(
                "bit_count",
                3,
                "unsigned",
                producer="module:bit_counter",
                consumers=["port:valid"],
                role="bit counter",
                reset_value="000",
            ),
        ],
        fsms=[],
        datapath=[
            "8-bit shift_register",
            "3-bit bit_counter",
        ],
        timing=[
            TimingRequirement(
                "continuous_output",
                "parallel_out mirrors shift register every cycle, including partial frames",
                1,
                "clock_edge",
            )
        ],
        reset_policy="synchronous",
        constraints=[
            "one serial bit per clock",
            "valid asserted after 8 bits",
        ],
        assumptions=[
            "parallel_out may be visible during partial frame",
            "no separate output register is required",
        ],
        confidence=0.55,
    )

    p3 = CandidatePlan(
        plan_id="P3_fsm_guarded_output",
        original_spec=SERIAL_TO_PARALLEL_SPEC,
        ports=common_ports,
        modules=[
            Module(
                "shift_register",
                "datapath",
                role="serial capture path",
            ),
            Module(
                "bit_counter",
                "counter",
                role="detect 8-bit frame completion",
            ),
            Module(
                "output_register",
                "datapath",
                role="hold completed 8-bit parallel frame",
            ),
            Module(
                "control_fsm",
                "fsm",
                role="control shift, latch, and valid pulse timing",
            ),
        ],
        signals=[
            Signal(
                "shift_reg",
                8,
                "std_logic_vector",
                producer="module:shift_register",
                consumers=["module:output_register"],
                role="serial accumulation register",
                reset_value="00000000",
            ),
            Signal(
                "count_done",
                1,
                "std_logic",
                producer="module:bit_counter",
                consumers=["module:control_fsm"],
                role="frame completion trigger",
                reset_value="0",
            ),
            Signal(
                "parallel_reg",
                8,
                "std_logic_vector",
                producer="module:output_register",
                consumers=["port:parallel_out"],
                role="registered completed frame output",
                reset_value="00000000",
            ),
            Signal(
                "valid_int",
                1,
                "std_logic",
                producer="module:control_fsm",
                consumers=["port:valid"],
                role="registered one-cycle valid pulse",
                reset_value="0",
            ),
        ],
        fsms=[
            FSM(
                "control_fsm",
                ["SHIFT", "LATCH"],
                "SHIFT",
                transitions=[
                    {"from": "SHIFT", "to": "LATCH", "condition": "count_done = 1"},
                    {"from": "LATCH", "to": "SHIFT", "condition": "next clock"},
                ],
                output_style="moore",
            )
        ],
        datapath=[
            "8-bit shift_register",
            "3-bit bit_counter",
            "8-bit parallel_output_register",
        ],
        timing=[
            TimingRequirement(
                "frame_latency",
                "parallel_out updates only after 8 valid serial bits are received",
                8,
                "bit_counter_terminal_count",
            ),
            TimingRequirement(
                "registered_output_hold",
                "parallel_out holds last completed frame until next frame completes",
                0,
                "output_register",
            ),
        ],
        reset_policy="synchronous",
        constraints=[
            "valid asserted for one cycle after 8 bits",
            "parallel_out is registered",
            "counter resets after terminal count",
        ],
        assumptions=[
            "output register is required to prevent partial-frame visibility",
            "valid is generated by FSM rather than directly by counter",
        ],
        confidence=0.92,
    )

    return [p1, p2, p3]


# ---------------------------------------------------------------------
# Example Kernel Library
# ---------------------------------------------------------------------


def example_kernel_library() -> list[KernelMetadata]:
    """
    Return a small representative kernel library.

    In the full COHERENT implementation, the library contains 157 kernels
    grouped into:

    1. human-written reusable primitives
    2. benchmark-derived reusable modules
    3. curated design patterns

    This small example mirrors the metadata style used in the full library.
    """

    return [
        KernelMetadata(
            kernel_id="K_SHIFT_001",
            name="param_shift_register",
            category="datapath",
            description=(
                "Parameterized serial-in parallel-out shift register with "
                "synchronous reset and enable."
            ),
            tags=[
                "shift_register",
                "serial",
                "parallel",
                "datapath",
                "sequential",
                "sipo",
                "frame_accumulation",
            ],
            ports=[
                Port("clk", Direction.IN, width=1, dtype="std_logic"),
                Port("rst", Direction.IN, width=1, dtype="std_logic"),
                Port("en", Direction.IN, width=1, dtype="std_logic"),
                Port("din", Direction.IN, width=1, dtype="std_logic"),
                Port("q", Direction.OUT, width=8, dtype="std_logic_vector"),
            ],
            parameters={
                "WIDTH": 8,
                "SHIFT_DIRECTION": "left",
            },
            timing={
                "latency": 0,
                "throughput": "1 bit per clock",
                "output_behavior": "registered internal state",
            },
            verification={
                "syntax_pass": True,
                "sim_pass": True,
                "synthesis_pass": True,
                "lint_pass": True,
            },
            provenance={
                "source_type": "human_written_primitive",
                "source_description": (
                    "Developed as a reusable primitive with review from "
                    "experienced RTL engineers. Specific industrial names are "
                    "not disclosed due to confidentiality."
                ),
                "contamination_status": "not_derived_from_custom_eval_tasks",
            },
            adaptation_notes=[
                "WIDTH can be changed through parameter substitution.",
                "Port names can be normalized to serial_in and parallel_out.",
                "Enable can be connected to FSM shift control.",
            ],
        ),
        KernelMetadata(
            kernel_id="K_COUNTER_001",
            name="generic_modulo_counter",
            category="counter",
            description=(
                "Parameterized modulo counter with terminal-count pulse, "
                "enable control, and synchronous reset."
            ),
            tags=[
                "counter",
                "modulo_counter",
                "terminal_count",
                "control",
                "sequential",
                "frame_tracking",
            ],
            ports=[
                Port("clk", Direction.IN, width=1, dtype="std_logic"),
                Port("rst", Direction.IN, width=1, dtype="std_logic"),
                Port("en", Direction.IN, width=1, dtype="std_logic"),
                Port("count", Direction.OUT, width=3, dtype="std_logic_vector"),
                Port("tc", Direction.OUT, width=1, dtype="std_logic"),
            ],
            parameters={
                "WIDTH": 3,
                "MODULO": 8,
            },
            timing={
                "terminal_pulse_cycles": 1,
                "count_range": "0 to MODULO-1",
                "wrap_behavior": "wrap to zero after terminal count",
            },
            verification={
                "syntax_pass": True,
                "sim_pass": True,
                "synthesis_pass": True,
                "lint_pass": True,
            },
            provenance={
                "source_type": "benchmark_derived_generalized",
                "source_description": (
                    "Generalized from public RTL benchmark-style counter "
                    "examples after removing task-specific logic and "
                    "normalizing interface names."
                ),
                "contamination_status": "generic_counter_only_not_task_solution",
            },
            adaptation_notes=[
                "MODULO can be changed for modulo-N counter tasks.",
                "WIDTH is recomputed as ceil(log2(MODULO)).",
                "Terminal-count output can drive FSM transition logic.",
            ],
        ),
        KernelMetadata(
            kernel_id="K_FSM_001",
            name="moore_fsm_template",
            category="fsm",
            description=(
                "Reusable Moore FSM template with safe default transition, "
                "registered outputs, and explicit reset state."
            ),
            tags=[
                "fsm",
                "moore",
                "control",
                "registered_output",
                "safe_fsm",
            ],
            ports=[
                Port("clk", Direction.IN, width=1, dtype="std_logic"),
                Port("rst", Direction.IN, width=1, dtype="std_logic"),
                Port("event_in", Direction.IN, width=1, dtype="std_logic"),
                Port("valid", Direction.OUT, width=1, dtype="std_logic"),
            ],
            parameters={
                "STATES": 3,
                "OUTPUT_STYLE": "moore",
            },
            timing={
                "output_behavior": "registered",
                "illegal_state_recovery": "reset_state",
            },
            verification={
                "syntax_pass": True,
                "sim_pass": True,
                "synthesis_pass": True,
                "fsm_lint_pass": True,
            },
            provenance={
                "source_type": "curated_design_pattern",
                "source_description": (
                    "Curated from standard FSM design practice and reviewed "
                    "as a reusable controller template."
                ),
                "contamination_status": "template_only_not_sequence_specific_solution",
            },
            adaptation_notes=[
                "State names can be replaced by S3 state set.",
                "Transition conditions are filled from merged plan.",
                "Registered-output behavior must be preserved.",
            ],
        ),
        KernelMetadata(
            kernel_id="K_SYNC_001",
            name="two_flop_synchronizer",
            category="cdc",
            description=(
                "Two-flop synchronizer for single-bit asynchronous control "
                "signals crossing into a destination clock domain."
            ),
            tags=[
                "cdc",
                "synchronizer",
                "two_flop",
                "single_bit",
                "metastability",
            ],
            ports=[
                Port("clk_dst", Direction.IN, width=1, dtype="std_logic"),
                Port("rst_dst", Direction.IN, width=1, dtype="std_logic"),
                Port("async_in", Direction.IN, width=1, dtype="std_logic"),
                Port("sync_out", Direction.OUT, width=1, dtype="std_logic"),
            ],
            parameters={},
            timing={
                "latency": 2,
                "safe_for": "single_bit_control_only",
            },
            verification={
                "syntax_pass": True,
                "sim_pass": True,
                "synthesis_pass": True,
            },
            provenance={
                "source_type": "curated_design_pattern",
                "source_description": (
                    "Curated CDC-safe design pattern used for single-bit "
                    "control synchronization."
                ),
                "contamination_status": "generic_cdc_pattern",
            },
            adaptation_notes=[
                "Do not use for multi-bit data buses.",
                "Can be instantiated when S3 identifies single-bit CDC.",
            ],
        ),
        KernelMetadata(
            kernel_id="K_HANDSHAKE_001",
            name="valid_ready_controller",
            category="interface",
            description=(
                "Reusable valid-ready handshake controller for back-pressure "
                "safe data transfer."
            ),
            tags=[
                "valid_ready",
                "handshake",
                "interface",
                "controller",
                "backpressure",
            ],
            ports=[
                Port("clk", Direction.IN, width=1, dtype="std_logic"),
                Port("rst", Direction.IN, width=1, dtype="std_logic"),
                Port("valid_in", Direction.IN, width=1, dtype="std_logic"),
                Port("ready_in", Direction.IN, width=1, dtype="std_logic"),
                Port("fire", Direction.OUT, width=1, dtype="std_logic"),
            ],
            parameters={},
            timing={
                "fire_condition": "valid_in and ready_in",
                "latency": 0,
            },
            verification={
                "syntax_pass": True,
                "sim_pass": True,
                "synthesis_pass": True,
            },
            provenance={
                "source_type": "human_written_primitive",
                "source_description": (
                    "Reusable interface-control primitive written from common "
                    "RTL handshake design practice."
                ),
                "contamination_status": "not_derived_from_custom_eval_tasks",
            },
            adaptation_notes=[
                "Can generate fire condition for load/accept behavior.",
                "Useful for parallel-to-serial and streaming tasks.",
            ],
        ),
    ]


# ---------------------------------------------------------------------
# Expected S2 Adaptation Example
# ---------------------------------------------------------------------


def serial_to_parallel_expected_adaptations() -> list[dict]:
    """
    Expected adaptation actions for the serial-to-parallel example.

    These are useful for tests and documentation.
    """

    return [
        {
            "kernel_id": "K_SHIFT_001",
            "action_type": "parameter_substitution",
            "target": "WIDTH",
            "before": 8,
            "after": 8,
            "reason": "Need 8-bit serial frame accumulation.",
        },
        {
            "kernel_id": "K_COUNTER_001",
            "action_type": "parameter_substitution",
            "target": "MODULO",
            "before": 8,
            "after": 8,
            "reason": "Need terminal-count pulse after 8 serial bits.",
        },
        {
            "kernel_id": "K_COUNTER_001",
            "action_type": "control_wiring",
            "target": "tc -> control_fsm.event_in",
            "reason": "Counter terminal count triggers FSM output-valid state.",
        },
        {
            "kernel_id": "K_FSM_001",
            "action_type": "fsm_state_adaptation",
            "target": "states",
            "before": ["IDLE", "SHIFT", "OUTPUT"],
            "after": ["SHIFT", "LATCH"],
            "reason": "Merged S3 plan uses explicit shift/latch behavior.",
        },
    ]


__all__ = [
    "SERIAL_TO_PARALLEL_SPEC",
    "serial_to_parallel_ports",
    "serial_to_parallel_candidate_plans",
    "example_kernel_library",
    "serial_to_parallel_expected_adaptations",
]
