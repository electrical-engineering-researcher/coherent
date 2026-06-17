"""Validation criteria for merged S3 plans and S2 reuse plans."""
from __future__ import annotations

from typing import List
from .schemas import CandidatePlan, CheckerResult, Diagnostic, Direction


def validate_merged_plan(plan: CandidatePlan) -> CheckerResult:
    diagnostics: List[Diagnostic] = []

    output_ports = [p for p in plan.ports if p.direction == Direction.OUT or str(p.direction).endswith("OUT") or p.direction == "out"]
    signal_names = {s.name for s in plan.signals}
    module_names = {m.name for m in plan.modules}

    for out in output_ports:
        driven = any((out.name in s.consumers) or (f"port:{out.name}" in s.consumers) or s.name == out.name or out.name in (s.producer or "") for s in plan.signals)
        if not driven and out.name not in plan.datapath:
            diagnostics.append(Diagnostic(
                error_type="undriven_output",
                tool="s3_validator",
                message=f"Output port {out.name} has no producer in merged plan.",
            ))

    for s in plan.signals:
        if not s.producer and "clk" not in s.name and "rst" not in s.name:
            diagnostics.append(Diagnostic(
                error_type="dangling_signal",
                tool="s3_validator",
                message=f"Internal signal {s.name} has no producer.",
            ))

    for fsm in plan.fsms:
        if fsm.initial_state not in fsm.states:
            diagnostics.append(Diagnostic("fsm_initial_state_missing", "s3_validator", f"FSM {fsm.name} initial state is not in state list."))
        transition_sources = {t.get("from") for t in fsm.transitions}
        for st in fsm.states:
            if st != fsm.initial_state and st not in transition_sources and len(fsm.states) > 1:
                # Warning-like diagnostic, still treated as failure for reproducibility.
                diagnostics.append(Diagnostic("fsm_reachability_uncertain", "s3_validator", f"FSM state {st} has uncertain reachability."))

    stateful_names = [s.name for s in plan.signals if "reg" in s.name or "counter" in s.name or "state" in s.name]
    if stateful_names and plan.reset_policy == "unspecified":
        diagnostics.append(Diagnostic("reset_policy_missing", "s3_validator", "Stateful elements exist but reset policy is unspecified."))

    for m in plan.modules:
        for p in m.ports:
            if p.width <= 0:
                diagnostics.append(Diagnostic("invalid_width", "s3_validator", f"Port {m.name}.{p.name} has invalid width {p.width}."))

    passed = len(diagnostics) == 0
    return CheckerResult(passed=passed, stage="merged_plan_validation", diagnostics=diagnostics)
