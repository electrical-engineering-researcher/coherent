"""
S2 kernel adaptation rules for COHERENT.

This module converts a retrieved reusable kernel into an adapted kernel
instance that can be consumed by S1 structured synthesis.

It does not generate final VHDL. It only records:
- parameter changes
- port renaming
- width/type adaptations
- reset normalization
- terminal-count changes
- glue-logic requirements
- validation notes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, log2
from typing import Any, Dict, List, Optional

from .schemas import KernelMetadata


# ---------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------


@dataclass
class AdaptationAction:
    """
    One atomic adaptation applied to a retrieved kernel.

    Examples:
    - WIDTH 8 -> 13
    - port rst_i -> rst
    - reset polarity active_low -> active_high
    - add valid pulse adapter
    """

    action_type: str
    description: str
    target: str = ""
    before: str = ""
    after: str = ""
    reason: str = ""
    safety_note: str = ""


@dataclass
class GlueLogicSpec:
    """
    Minimal glue logic needed to connect adapted kernels.

    Glue logic is not final VHDL. It is a structured instruction for S1.
    """

    glue_type: str
    source: str
    destination: str
    method: str
    purpose: str
    width: Optional[int] = None
    latency_cycles: Optional[int] = None


@dataclass
class AdaptedKernel:
    """
    Kernel after S2 adaptation.

    This is the final S2 output for one selected kernel.
    S1 will convert this object into VHDL instantiation and wiring.
    """

    source_kernel: KernelMetadata
    instance_name: str
    role: str = ""
    parameter_overrides: Dict[str, int | str] = field(default_factory=dict)
    port_map: Dict[str, str] = field(default_factory=dict)
    type_conversions: Dict[str, str] = field(default_factory=dict)
    glue_logic: List[GlueLogicSpec] = field(default_factory=list)
    actions: List[AdaptationAction] = field(default_factory=list)
    validation_notes: List[str] = field(default_factory=list)
    unresolved_issues: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------


def required_counter_width(modulo: int) -> int:
    """
    Return the smallest counter width needed to represent 0 to modulo-1.

    Example:
    modulo = 8  -> width = 3
    modulo = 13 -> width = 4
    """

    if modulo <= 1:
        return 1
    return ceil(log2(modulo))


def safe_instance_name(kernel_name: str, suffix: str = "") -> str:
    """
    Create deterministic VHDL-safe instance names.
    """

    clean = kernel_name.lower().replace("-", "_").replace(" ", "_")
    if suffix:
        return f"u_{clean}_{suffix}"
    return f"u_{clean}"


def get_kernel_parameter(kernel: KernelMetadata, name: str, default: Any = None) -> Any:
    """
    Safely read a kernel parameter.

    Supports both:
    parameters = {"WIDTH": 8}
    and richer metadata:
    parameters = {"WIDTH": {"default": 8}}
    """

    value = kernel.parameters.get(name, default)

    if isinstance(value, dict):
        return value.get("default", default)

    return value


def add_action(
    actions: List[AdaptationAction],
    action_type: str,
    description: str,
    target: str = "",
    before: str = "",
    after: str = "",
    reason: str = "",
    safety_note: str = "",
) -> None:
    actions.append(
        AdaptationAction(
            action_type=action_type,
            description=description,
            target=target,
            before=str(before),
            after=str(after),
            reason=reason,
            safety_note=safety_note,
        )
    )


# ---------------------------------------------------------------------
# Counter Adaptation
# ---------------------------------------------------------------------


def adapt_counter_modulo(
    kernel: KernelMetadata,
    target_modulo: int,
    enable_signal: str = "enable",
    terminal_signal: str = "terminal_count",
) -> AdaptedKernel:
    """
    Adapt a reusable modulo counter.

    This preserves the verified counter structure while changing only:
    - MODULO parameter
    - WIDTH parameter
    - terminal-count behavior
    - optional enable/terminal-count signal names

    Example:
    Generic mod-8 counter -> mod-13 counter
    MODULO: 8 -> 13
    WIDTH: 3 -> 4
    terminal count: 7 -> 12
    """

    if target_modulo <= 0:
        raise ValueError("target_modulo must be positive")

    old_modulo = get_kernel_parameter(kernel, "MODULO", "unknown")
    old_width = get_kernel_parameter(kernel, "WIDTH", "unknown")
    new_width = required_counter_width(target_modulo)

    actions: List[AdaptationAction] = []

    add_action(
        actions,
        action_type="parameter_substitution",
        target="MODULO",
        description="Set counter modulus to required target value.",
        before=old_modulo,
        after=target_modulo,
        reason="S3 plan requires modulo-specific terminal-count behavior.",
        safety_note="Only terminal-count limit changes; verified counter update structure is preserved.",
    )

    add_action(
        actions,
        action_type="bit_width_scaling",
        target="WIDTH",
        description="Use the smallest safe width that can represent target_modulo - 1.",
        before=old_width,
        after=new_width,
        reason=f"Counter must represent values 0 through {target_modulo - 1}.",
        safety_note="Width scaling avoids overflow and preserves modulo behavior.",
    )

    add_action(
        actions,
        action_type="terminal_count_update",
        target=terminal_signal,
        description="Set terminal-count comparison to target_modulo - 1.",
        before=f"{old_modulo} - 1" if old_modulo != "unknown" else "unknown",
        after=str(target_modulo - 1),
        reason="Modulo counter must assert terminal-count pulse before wraparound.",
        safety_note="Terminal pulse remains one cycle if source kernel already implements registered pulse behavior.",
    )

    adapted = AdaptedKernel(
        source_kernel=kernel,
        instance_name=safe_instance_name(kernel.name, f"mod{target_modulo}"),
        role="modulo_counter",
        parameter_overrides={
            "MODULO": target_modulo,
            "WIDTH": new_width,
        },
        port_map={
            "enable": enable_signal,
            "terminal_count": terminal_signal,
        },
        actions=actions,
        validation_notes=[
            f"Counter width selected as {new_width} bits.",
            f"Expected count range is 0 to {target_modulo - 1}.",
            "Terminal-count pulse should assert at terminal count before wraparound.",
        ],
    )

    return adapted


# ---------------------------------------------------------------------
# Shift Register Adaptation
# ---------------------------------------------------------------------


def adapt_shift_register_width(
    kernel: KernelMetadata,
    target_width: int,
    serial_input: str = "serial_in",
    parallel_output: str = "parallel_out",
    enable_signal: str = "shift_enable",
) -> AdaptedKernel:
    """
    Adapt a parameterized shift-register kernel.

    Used for serial-to-parallel, delay line, deserializer, and bitstream
    accumulation tasks.
    """

    if target_width <= 0:
        raise ValueError("target_width must be positive")

    old_width = get_kernel_parameter(kernel, "WIDTH", "unknown")
    actions: List[AdaptationAction] = []

    add_action(
        actions,
        action_type="bit_width_scaling",
        target="WIDTH",
        description="Scale shift-register width to match required frame width.",
        before=old_width,
        after=target_width,
        reason="S3 plan requires accumulation of a fixed number of serial bits.",
        safety_note="Shift direction must still be checked against S3 timing assumptions.",
    )

    adapted = AdaptedKernel(
        source_kernel=kernel,
        instance_name=safe_instance_name(kernel.name, f"w{target_width}"),
        role="shift_register",
        parameter_overrides={"WIDTH": target_width},
        port_map={
            "serial_in": serial_input,
            "parallel_out": parallel_output,
            "enable": enable_signal,
        },
        actions=actions,
        validation_notes=[
            f"Shift register adapted to WIDTH={target_width}.",
            "S1 must preserve shift direction specified by S3.",
            "Output update timing must match merged plan.",
        ],
    )

    return adapted


# ---------------------------------------------------------------------
# FSM Adaptation
# ---------------------------------------------------------------------


def adapt_fsm_template(
    kernel: KernelMetadata,
    states: List[str],
    initial_state: str,
    fsm_style: str = "Moore",
    output_signals: Optional[List[str]] = None,
) -> AdaptedKernel:
    """
    Adapt a generic FSM template to the required state structure.

    This does not synthesize transitions directly.
    It records the state/control adaptation required for S1.
    """

    if not states:
        raise ValueError("FSM must contain at least one state")

    if initial_state not in states:
        raise ValueError("initial_state must be present in states")

    output_signals = output_signals or []
    old_state_count = get_kernel_parameter(kernel, "STATES", "unknown")

    actions: List[AdaptationAction] = []

    add_action(
        actions,
        action_type="fsm_state_adaptation",
        target="STATES",
        description="Adapt reusable FSM template to required state set.",
        before=old_state_count,
        after=len(states),
        reason="S3 plan defines a specific control sequence.",
        safety_note="FSM style and output timing must be preserved.",
    )

    add_action(
        actions,
        action_type="fsm_initial_state_assignment",
        target="initial_state",
        description="Set FSM reset state.",
        before="kernel_default",
        after=initial_state,
        reason="Reset behavior must match merged S3 plan.",
    )

    add_action(
        actions,
        action_type="fsm_style_preservation",
        target="fsm_style",
        description="Preserve specified Moore/Mealy behavior.",
        before=getattr(kernel, "fsm_style", "unknown"),
        after=fsm_style,
        reason="Changing FSM style may shift output timing by one cycle.",
        safety_note="Do not convert Moore to Mealy or Mealy to Moore unless S3 explicitly requires it.",
    )

    adapted = AdaptedKernel(
        source_kernel=kernel,
        instance_name=safe_instance_name(kernel.name, "ctrl"),
        role="fsm_controller",
        parameter_overrides={
            "STATES": len(states),
            "INITIAL_STATE": initial_state,
            "FSM_STYLE": fsm_style,
        },
        actions=actions,
        validation_notes=[
            f"FSM states: {states}",
            f"Initial state: {initial_state}",
            f"FSM style: {fsm_style}",
            f"Output signals controlled by FSM: {output_signals}",
        ],
    )

    return adapted


# ---------------------------------------------------------------------
# Port Renaming and Interface Normalization
# ---------------------------------------------------------------------


def rename_ports(
    kernel: KernelMetadata,
    mapping: Dict[str, str],
    role: str = "",
) -> AdaptedKernel:
    """
    Rename kernel ports to match the S3/S2 interface.

    Example:
    clk_i -> clk
    rst_i -> rst
    din   -> serial_in
    dout  -> parallel_out
    """

    actions: List[AdaptationAction] = []

    for src, dst in mapping.items():
        add_action(
            actions,
            action_type="port_renaming",
            target=src,
            description=f"Map kernel port '{src}' to design signal '{dst}'.",
            before=src,
            after=dst,
            reason="Kernel interface naming differs from target design interface.",
            safety_note="Only names are changed; signal role is preserved.",
        )

    return AdaptedKernel(
        source_kernel=kernel,
        instance_name=safe_instance_name(kernel.name),
        role=role,
        port_map=mapping,
        actions=actions,
        validation_notes=[
            "Port renaming performed without changing functional behavior.",
            "S1 must verify direction and width compatibility.",
        ],
    )


def normalize_clock_reset_ports(
    adapted: AdaptedKernel,
    clk_name: str = "clk",
    rst_name: str = "rst",
    reset_style: str = "synchronous",
    reset_polarity: str = "active_high",
) -> AdaptedKernel:
    """
    Normalize clock/reset naming and policy.

    This function updates the adapted kernel in-place and returns it.
    """

    adapted.port_map.setdefault("clk", clk_name)
    adapted.port_map.setdefault("rst", rst_name)

    add_action(
        adapted.actions,
        action_type="clock_reset_normalization",
        target="clk/rst",
        description="Normalize clock and reset ports to match top-level design.",
        before="kernel_default",
        after=f"{clk_name}, {rst_name}, {reset_style}, {reset_polarity}",
        reason="All reused kernels must share consistent clock/reset semantics.",
        safety_note="S1 must ensure reset implementation matches style and polarity.",
    )

    adapted.validation_notes.append(
        f"Clock/reset normalized to clk={clk_name}, rst={rst_name}, "
        f"style={reset_style}, polarity={reset_polarity}."
    )

    return adapted


# ---------------------------------------------------------------------
# Type and Width Adapters
# ---------------------------------------------------------------------


def add_width_adapter(
    adapted: AdaptedKernel,
    source: str,
    destination: str,
    source_width: int,
    destination_width: int,
    signed: bool = False,
) -> AdaptedKernel:
    """
    Add width adapter glue logic.

    If destination is wider:
    - zero extend for unsigned data
    - sign extend for signed data

    If destination is narrower:
    - truncation is marked unsafe unless explicitly intended.
    """

    if source_width == destination_width:
        adapted.validation_notes.append(
            f"No width adapter needed for {source} -> {destination}."
        )
        return adapted

    if source_width < destination_width:
        method = "sign_extend" if signed else "zero_extend"
        safety_note = "Width extension is safe when numeric interpretation is preserved."
    else:
        method = "truncate"
        safety_note = (
            "Truncation may lose information. S1 must only allow this if S3 explicitly permits it."
        )
        adapted.unresolved_issues.append(
            f"Potential unsafe truncation from {source_width} to {destination_width} "
            f"for {source} -> {destination}."
        )

    adapted.glue_logic.append(
        GlueLogicSpec(
            glue_type="width_adapter",
            source=source,
            destination=destination,
            method=method,
            purpose="Resolve width mismatch between reused kernel and target interface.",
            width=destination_width,
        )
    )

    add_action(
        adapted.actions,
        action_type="width_adapter_generation",
        target=f"{source}->{destination}",
        description="Generate explicit width adapter.",
        before=f"{source_width}",
        after=f"{destination_width}",
        reason="Kernel and target interface widths differ.",
        safety_note=safety_note,
    )

    return adapted


def add_type_conversion(
    adapted: AdaptedKernel,
    signal_name: str,
    before_type: str,
    after_type: str,
) -> AdaptedKernel:
    """
    Record an explicit type conversion needed by S1.

    Example:
    std_logic_vector -> unsigned
    unsigned -> std_logic_vector
    """

    if before_type == after_type:
        return adapted

    adapted.type_conversions[signal_name] = f"{before_type}->{after_type}"

    add_action(
        adapted.actions,
        action_type="type_conversion",
        target=signal_name,
        description="Add explicit type conversion.",
        before=before_type,
        after=after_type,
        reason="VHDL numeric operations require explicit type compatibility.",
        safety_note="S1 should use numeric_std conversions, not non-standard libraries.",
    )

    return adapted


# ---------------------------------------------------------------------
# Glue Logic Helpers
# ---------------------------------------------------------------------


def add_control_wire(
    adapted: AdaptedKernel,
    source: str,
    destination: str,
    purpose: str,
) -> AdaptedKernel:
    """
    Add direct control/status wiring between kernels.

    Example:
    counter.terminal_count -> fsm.frame_done
    """

    adapted.glue_logic.append(
        GlueLogicSpec(
            glue_type="control_wire",
            source=source,
            destination=destination,
            method="direct_assignment",
            purpose=purpose,
        )
    )

    add_action(
        adapted.actions,
        action_type="control_wiring",
        target=f"{source}->{destination}",
        description="Connect control/status signal between reused kernels.",
        before=source,
        after=destination,
        reason=purpose,
    )

    return adapted


def add_valid_pulse_adapter(
    adapted: AdaptedKernel,
    trigger_signal: str,
    valid_signal: str = "valid",
    duration_cycles: int = 1,
) -> AdaptedKernel:
    """
    Add a valid-pulse glue requirement.

    Used when the reused kernel provides a terminal-count/status signal
    but the final design requires a one-cycle valid pulse.
    """

    adapted.glue_logic.append(
        GlueLogicSpec(
            glue_type="valid_pulse_generator",
            source=trigger_signal,
            destination=valid_signal,
            method="registered_one_cycle_pulse",
            purpose="Generate valid pulse aligned with frame completion.",
            latency_cycles=duration_cycles,
        )
    )

    add_action(
        adapted.actions,
        action_type="valid_pulse_generation",
        target=valid_signal,
        description="Generate one-cycle valid pulse from trigger signal.",
        before=trigger_signal,
        after=valid_signal,
        reason="S3 timing plan requires explicit output-valid behavior.",
        safety_note="S1 must ensure valid pulse is not one cycle early or late.",
    )

    return adapted


# ---------------------------------------------------------------------
# High-Level Adaptation Dispatcher
# ---------------------------------------------------------------------


def adapt_kernel_for_block(
    kernel: KernelMetadata,
    block: Dict[str, Any],
) -> AdaptedKernel:
    """
    Generic dispatcher used by S2.

    block is a dictionary from the merged S3 plan describing one required
    design block.

    Expected block fields may include:
    - type
    - role
    - width
    - modulo
    - states
    - initial_state
    - fsm_style
    - ports
    """

    block_type = str(block.get("type", "")).lower()
    role = str(block.get("role", block_type))

    if "counter" in block_type:
        modulo = int(block.get("modulo", block.get("MODULO", 2)))
        adapted = adapt_counter_modulo(kernel, modulo)
        adapted.role = role
        return adapted

    if "shift" in block_type:
        width = int(block.get("width", block.get("WIDTH", 8)))
        adapted = adapt_shift_register_width(kernel, width)
        adapted.role = role
        return adapted

    if "fsm" in block_type:
        states = block.get("states", ["IDLE", "RUN", "DONE"])
        initial_state = block.get("initial_state", states[0])
        fsm_style = block.get("fsm_style", "Moore")
        adapted = adapt_fsm_template(
            kernel=kernel,
            states=states,
            initial_state=initial_state,
            fsm_style=fsm_style,
            output_signals=block.get("outputs", []),
        )
        adapted.role = role
        return adapted

    mapping = block.get("port_map", {})
    if mapping:
        return rename_ports(kernel, mapping, role=role)

    return AdaptedKernel(
        source_kernel=kernel,
        instance_name=safe_instance_name(kernel.name),
        role=role,
        validation_notes=[
            "No special adaptation required.",
            "Kernel selected as direct reusable component.",
        ],
    )


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def validate_adaptation(adapted: AdaptedKernel) -> List[str]:
    """
    Return validation issues for an adapted kernel.

    Empty list means no obvious S2 adaptation issue was found.
    """

    issues: List[str] = []

    if not adapted.instance_name:
        issues.append("Missing instance name.")

    if adapted.source_kernel is None:
        issues.append("Missing source kernel.")

    verification = getattr(adapted.source_kernel, "verification", {})
    if isinstance(verification, dict):
        if not verification.get("syntax_pass", False):
            issues.append("Source kernel did not pass syntax validation.")
        if not verification.get("sim_pass", verification.get("simulation_pass", False)):
            issues.append("Source kernel did not pass simulation validation.")

    for key, value in adapted.parameter_overrides.items():
        if value is None or value == "":
            issues.append(f"Parameter override {key} has invalid value.")

    for issue in adapted.unresolved_issues:
        issues.append(issue)

    return issues

