"""
glue.py

Minimal glue-logic generation for S2 kernel composition in COHERENT.

Glue logic is generated only when two selected kernels cannot be connected
directly because of a small interface mismatch.

Allowed glue logic:
- direct signal wiring
- zero/sign extension
- explicit truncation only when allowed
- type conversion wrappers
- enable/status wiring
- terminal-count to control wiring
- one-cycle pulse generation
- ready/valid fire condition
- load/busy adapter
- simple mux selection
- reset polarity normalization
- CDC-safe single-bit synchronizer specification

Glue logic must NOT:
- replace a missing architectural block
- invent new datapath behavior
- change timing intent
- silently truncate data
- change FSM semantics
- hide unresolved interface mismatches
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------


@dataclass
class GlueLogic:
    """
    Structured representation of generated glue logic.

    The `vhdl` field contains a small synthesizable VHDL snippet.
    This snippet is intended for S1 to insert into the final architecture.

    Glue logic is intentionally small and local.
    """

    name: str
    reason: str
    vhdl: str
    source: str = ""
    destination: str = ""
    glue_type: str = ""
    latency_cycles: int = 0
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# Basic Signal Wiring
# ---------------------------------------------------------------------


def generate_direct_wire(src: str, dst: str) -> GlueLogic:
    """
    Generate direct assignment when signals are already compatible.

    Example:
        enable <= terminal_count;
    """

    return GlueLogic(
        name="direct_wire",
        glue_type="direct_assignment",
        source=src,
        destination=dst,
        reason="Signals are interface-compatible; direct assignment is sufficient.",
        vhdl=f"{dst} <= {src};",
    )


# ---------------------------------------------------------------------
# Width Adaptation
# ---------------------------------------------------------------------


def generate_width_adapter(
    src: str,
    dst: str,
    src_width: int,
    dst_width: int,
    *,
    signed: bool = False,
    allow_truncation: bool = False,
) -> GlueLogic:
    """
    Generate explicit width adaptation.

    Cases:
    1. Equal widths:
       dst <= src;

    2. Source narrower than destination:
       zero extension for unsigned data
       sign extension for signed data

    3. Source wider than destination:
       explicit truncation only if allowed by the specification.

    This function never silently truncates.
    """

    if src_width <= 0 or dst_width <= 0:
        raise ValueError("Signal widths must be positive integers.")

    if src_width == dst_width:
        return generate_direct_wire(src, dst)

    if src_width < dst_width:
        pad = dst_width - src_width

        if signed:
            if pad == 1:
                extension = f"{src}({src_width - 1})"
            else:
                extension = f"({pad - 1} downto 0 => {src}({src_width - 1}))"

            return GlueLogic(
                name="sign_extension",
                glue_type="width_adapter",
                source=src,
                destination=dst,
                reason=f"Sign-extend {src_width}-bit signed signal to {dst_width}-bit signal.",
                vhdl=f"{dst} <= {extension} & {src};",
            )

        if pad == 1:
            extension = "'0'"
        else:
            extension = f"({pad - 1} downto 0 => '0')"

        return GlueLogic(
            name="zero_extension",
            glue_type="width_adapter",
            source=src,
            destination=dst,
            reason=f"Zero-extend {src_width}-bit signal to {dst_width}-bit signal.",
            vhdl=f"{dst} <= {extension} & {src};",
        )

    if not allow_truncation:
        raise ValueError(
            f"Unsafe truncation requested from {src_width} bits to {dst_width} bits. "
            "Truncation is not allowed unless explicitly permitted by the specification."
        )

    return GlueLogic(
        name="explicit_truncation",
        glue_type="width_adapter",
        source=src,
        destination=dst,
        reason=f"Explicitly truncate {src_width}-bit signal to {dst_width}-bit signal.",
        vhdl=f"{dst} <= {src}({dst_width - 1} downto 0);",
        warnings=[
            "Truncation may discard significant bits.",
            "This adapter should only be used if the specification explicitly allows truncation.",
        ],
    )


# ---------------------------------------------------------------------
# Type Conversion
# ---------------------------------------------------------------------


def generate_type_conversion(
    src: str,
    dst: str,
    src_type: str,
    dst_type: str,
) -> GlueLogic:
    """
    Generate explicit numeric_std-compatible type conversion.

    Supported examples:
    - std_logic_vector -> unsigned
    - unsigned -> std_logic_vector
    - std_logic_vector -> signed
    - signed -> std_logic_vector
    - unsigned -> signed
    - signed -> unsigned
    """

    src_type = src_type.strip()
    dst_type = dst_type.strip()

    if src_type == dst_type:
        return generate_direct_wire(src, dst)

    conversion_map = {
        ("std_logic_vector", "unsigned"): f"{dst} <= unsigned({src});",
        ("unsigned", "std_logic_vector"): f"{dst} <= std_logic_vector({src});",
        ("std_logic_vector", "signed"): f"{dst} <= signed({src});",
        ("signed", "std_logic_vector"): f"{dst} <= std_logic_vector({src});",
        ("unsigned", "signed"): f"{dst} <= signed({src});",
        ("signed", "unsigned"): f"{dst} <= unsigned({src});",
    }

    key = (src_type, dst_type)

    if key not in conversion_map:
        raise ValueError(f"Unsupported type conversion: {src_type} -> {dst_type}")

    return GlueLogic(
        name="type_conversion",
        glue_type="type_adapter",
        source=src,
        destination=dst,
        reason=f"Convert {src_type} signal to {dst_type} using explicit numeric_std conversion.",
        vhdl=conversion_map[key],
    )


# ---------------------------------------------------------------------
# Control / Status Wiring
# ---------------------------------------------------------------------


def generate_enable_status_adapter(status_signal: str, enable_signal: str) -> GlueLogic:
    """
    Connect a status signal from one kernel to an enable/control input
    of another kernel.

    Example:
        shift_enable <= fsm_shift_en;
    """

    return GlueLogic(
        name="enable_status_wiring",
        glue_type="control_wire",
        source=status_signal,
        destination=enable_signal,
        reason="Connect status/control output from one kernel to enable input of another kernel.",
        vhdl=f"{enable_signal} <= {status_signal};",
    )


def generate_terminal_to_fsm_adapter(
    terminal_signal: str,
    fsm_input_signal: str,
) -> GlueLogic:
    """
    Connect a counter terminal-count pulse to an FSM input.

    Example:
        frame_done <= bit_counter_tc;
    """

    return GlueLogic(
        name="terminal_count_to_fsm",
        glue_type="control_wire",
        source=terminal_signal,
        destination=fsm_input_signal,
        reason="Use counter terminal-count pulse as FSM transition condition.",
        vhdl=f"{fsm_input_signal} <= {terminal_signal};",
    )


# ---------------------------------------------------------------------
# Ready / Valid and Load / Busy Adapters
# ---------------------------------------------------------------------


def generate_ready_valid_adapter(
    upstream_valid: str,
    downstream_ready: str,
    fire: str,
) -> GlueLogic:
    """
    Generate standard ready/valid transfer condition.

    Transfer occurs only when:
        valid = '1' and ready = '1'
    """

    return GlueLogic(
        name="ready_valid_adapter",
        glue_type="handshake_adapter",
        source=upstream_valid,
        destination=fire,
        reason="Generate ready/valid transfer-fire condition.",
        vhdl=f"{fire} <= {upstream_valid} and {downstream_ready};",
    )


def generate_load_busy_accept_adapter(
    load: str,
    busy: str,
    accept: str,
) -> GlueLogic:
    """
    Generate load acceptance condition for load/busy protocol.

    A new load is accepted only when:
        load = '1' and busy = '0'
    """

    return GlueLogic(
        name="load_busy_accept_adapter",
        glue_type="handshake_adapter",
        source=load,
        destination=accept,
        reason="Generate safe accept condition for load/busy protocol.",
        vhdl=f"{accept} <= {load} and not {busy};",
    )


# ---------------------------------------------------------------------
# Pulse Generation
# ---------------------------------------------------------------------


def generate_one_cycle_pulse(
    clk: str,
    rst: str,
    trigger: str,
    pulse: str,
    *,
    reset_active_high: bool = True,
) -> GlueLogic:
    """
    Generate a one-cycle registered pulse from a trigger signal.

    This is useful when a kernel produces a terminal condition and the
    final design requires a one-cycle valid/done pulse.

    The trigger is sampled on the rising edge of clk.
    """

    reset_condition = f"{rst} = '1'" if reset_active_high else f"{rst} = '0'"

    vhdl = f"""
process({clk})
begin
    if rising_edge({clk}) then
        if {reset_condition} then
            {pulse} <= '0';
        else
            {pulse} <= {trigger};
        end if;
    end if;
end process;
""".strip()

    return GlueLogic(
        name="one_cycle_pulse_generator",
        glue_type="pulse_adapter",
        source=trigger,
        destination=pulse,
        reason="Generate a registered one-cycle pulse from a trigger condition.",
        vhdl=vhdl,
        latency_cycles=1,
    )


def generate_edge_pulse(
    clk: str,
    rst: str,
    signal_in: str,
    signal_d: str,
    pulse_out: str,
    *,
    rising: bool = True,
    reset_active_high: bool = True,
) -> GlueLogic:
    """
    Generate pulse on rising or falling edge of a synchronous signal.

    rising=True:
        pulse_out = signal_in and not delayed_signal

    rising=False:
        pulse_out = not signal_in and delayed_signal
    """

    reset_condition = f"{rst} = '1'" if reset_active_high else f"{rst} = '0'"

    if rising:
        pulse_expr = f"{signal_in} and not {signal_d}"
        edge_name = "rising_edge_pulse"
    else:
        pulse_expr = f"not {signal_in} and {signal_d}"
        edge_name = "falling_edge_pulse"

    vhdl = f"""
process({clk})
begin
    if rising_edge({clk}) then
        if {reset_condition} then
            {signal_d} <= '0';
            {pulse_out} <= '0';
        else
            {pulse_out} <= {pulse_expr};
            {signal_d} <= {signal_in};
        end if;
    end if;
end process;
""".strip()

    return GlueLogic(
        name=edge_name,
        glue_type="pulse_adapter",
        source=signal_in,
        destination=pulse_out,
        reason="Generate a one-cycle edge-detection pulse.",
        vhdl=vhdl,
        latency_cycles=1,
    )


# ---------------------------------------------------------------------
# Multiplexer Glue
# ---------------------------------------------------------------------


def generate_mux2(
    sel: str,
    a: str,
    b: str,
    y: str,
) -> GlueLogic:
    """
    Generate a 2:1 combinational mux.

    y = b when sel = '1' else a
    """

    return GlueLogic(
        name="mux2_adapter",
        glue_type="datapath_adapter",
        source=f"{a},{b}",
        destination=y,
        reason="Generate minimal 2:1 mux glue logic for datapath selection.",
        vhdl=f"{y} <= {b} when {sel} = '1' else {a};",
    )


# ---------------------------------------------------------------------
# Reset Normalization
# ---------------------------------------------------------------------


def generate_reset_polarity_adapter(
    rst_in: str,
    rst_out: str,
    *,
    input_active_high: bool = True,
    output_active_high: bool = True,
) -> GlueLogic:
    """
    Normalize reset polarity between kernels.

    Example:
    input active-high reset, kernel expects active-low reset:
        rst_n <= not rst;
    """

    if input_active_high == output_active_high:
        return generate_direct_wire(rst_in, rst_out)

    return GlueLogic(
        name="reset_polarity_adapter",
        glue_type="reset_adapter",
        source=rst_in,
        destination=rst_out,
        reason="Normalize reset polarity between top-level design and reused kernel.",
        vhdl=f"{rst_out} <= not {rst_in};",
    )


# ---------------------------------------------------------------------
# CDC Adapter Specification
# ---------------------------------------------------------------------


def generate_two_flop_synchronizer_spec(
    clk_dst: str,
    rst_dst: str,
    async_in: str,
    sync_out: str,
    stage1: str,
    stage2: str,
) -> GlueLogic:
    """
    Generate synthesizable two-flop synchronizer glue for single-bit CDC.

    This should only be used for single-bit control signals.
    Multi-bit buses require handshake or valid/strobe protocol.
    """

    vhdl = f"""
process({clk_dst})
begin
    if rising_edge({clk_dst}) then
        if {rst_dst} = '1' then
            {stage1} <= '0';
            {stage2} <= '0';
        else
            {stage1} <= {async_in};
            {stage2} <= {stage1};
        end if;
    end if;
end process;

{sync_out} <= {stage2};
""".strip()

    return GlueLogic(
        name="two_flop_synchronizer",
        glue_type="cdc_adapter",
        source=async_in,
        destination=sync_out,
        reason="Synchronize single-bit asynchronous control signal into destination clock domain.",
        vhdl=vhdl,
        latency_cycles=2,
        warnings=[
            "Use only for single-bit control signals.",
            "Do not use for independent synchronization of multi-bit data buses.",
        ],
    )


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def validate_glue_logic(glue: GlueLogic) -> List[str]:
    """
    Perform lightweight validation of generated glue logic.

    This does not replace VHDL compilation.
    It catches obvious unsafe or underspecified glue generation.
    """

    issues: List[str] = []

    if not glue.name:
        issues.append("Glue logic is missing a name.")

    if not glue.vhdl.strip():
        issues.append("Glue logic has empty VHDL body.")

    if glue.glue_type == "width_adapter" and "truncate" in glue.name:
        if not glue.warnings:
            issues.append("Truncation adapter must include warnings.")

    if glue.glue_type == "cdc_adapter":
        if "two_flop" not in glue.name:
            issues.append("CDC adapter should explicitly identify synchronization strategy.")

    return issues


def render_glue_block(glue_items: List[GlueLogic]) -> str:
    """
    Render multiple glue snippets into one VHDL block.

    S1 may use this helper when assembling architecture body.
    """

    rendered: List[str] = []

    for item in glue_items:
        rendered.append(f"-- Glue: {item.name}")
        rendered.append(f"-- Reason: {item.reason}")

        for warning in item.warnings:
            rendered.append(f"-- WARNING: {warning}")

        rendered.append(item.vhdl)
        rendered.append("")

    return "\n".join(rendered).strip()

