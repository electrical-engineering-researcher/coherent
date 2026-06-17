"""Confidence-based S3 merge and explicit conflict resolution."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Tuple

from .schemas import CandidatePlan, FSM, Module, Port, Signal, TimingRequirement


def _majority(values: List[str], default: str = "unspecified") -> str:
    if not values:
        return default
    return Counter(values).most_common(1)[0][0]


def resolve_reset_policy(values: List[str], specification: str) -> str:
    spec = specification.lower()
    if "asynchronous reset" in spec or "async reset" in spec:
        return "asynchronous"
    if "synchronous reset" in spec or "sync reset" in spec:
        return "synchronous"
    if "no reset" in spec:
        return "none"
    # Hardware-safe default used when unspecified in this implementation.
    if "synchronous" in values:
        return "synchronous"
    return _majority(values, default="synchronous")


def resolve_output_timing(candidates: List[TimingRequirement], specification: str) -> List[TimingRequirement]:
    spec = specification.lower()
    # Explicit serial-to-parallel pattern: output after full frame.
    if "serial" in spec and "parallel" in spec and ("8" in spec or "eight" in spec):
        return [TimingRequirement(
            name="parallel_output_after_frame",
            description="parallel_out updates only after 8 valid serial bits are received",
            latency_cycles=8,
            output_event="bit_counter_overflow",
        )]
    # Otherwise keep majority descriptions.
    by_desc = Counter(t.description for t in candidates)
    return [t for t in candidates if t.description == by_desc.most_common(1)[0][0]][:1]


def merge_candidate_plans(plans: List[CandidatePlan], dominant_labels: List[int] | None = None, dominant_cluster_id: int | None = None) -> CandidatePlan:
    """Merge plans using dominant-cluster consensus.

    Decisions retained in the merged plan are those that either appear in the dominant
    cluster or are required by explicit specification constraints.
    """
    if not plans:
        raise ValueError("At least one candidate plan is required")

    selected = plans
    if dominant_labels is not None and dominant_cluster_id is not None:
        selected = [p for p, lab in zip(plans, dominant_labels) if lab == dominant_cluster_id]

    spec = selected[0].original_spec

    def merge_by_name(items, attr: str):
        table: Dict[str, object] = {}
        for p in selected:
            for item in getattr(p, attr):
                if item.name not in table:
                    table[item.name] = item
        return list(table.values())

    modules: List[Module] = merge_by_name(selected, "modules")  # type: ignore
    ports: List[Port] = merge_by_name(selected, "ports")  # type: ignore
    signals: List[Signal] = merge_by_name(selected, "signals")  # type: ignore
    fsms: List[FSM] = merge_by_name(selected, "fsms")  # type: ignore

    timing_candidates: List[TimingRequirement] = []
    for p in selected:
        timing_candidates.extend(p.timing)

    constraints = sorted({c for p in selected for c in p.constraints})
    assumptions = sorted({a for p in selected for a in p.assumptions})
    datapath = sorted({d for p in selected for d in p.datapath})
    reset_policy = resolve_reset_policy([p.reset_policy for p in selected], spec)
    timing = resolve_output_timing(timing_candidates, spec) if timing_candidates else []

    return CandidatePlan(
        plan_id="merged_S3_plan",
        original_spec=spec,
        modules=modules,
        ports=ports,
        signals=signals,
        fsms=fsms,
        datapath=datapath,
        timing=timing,
        reset_policy=reset_policy,
        constraints=constraints,
        assumptions=assumptions,
        confidence=sum(p.confidence for p in selected) / len(selected),
    )


CONFLICT_RESOLUTION_RULES: List[Tuple[str, str]] = [
    ("synchronous vs asynchronous reset", "Use explicit specification. If unspecified, prefer synchronous reset for FPGA-safe/default reproducibility."),
    ("Moore vs Mealy FSM", "Use output timing requirement. Immediate output implies Mealy; registered/next-cycle output implies Moore."),
    ("registered vs combinational output", "Use timing statement. If output is required after N cycles, register it at the terminal event."),
    ("counter terminal count", "Use smallest width satisfying terminal count, and explicit terminal pulse/wrap logic."),
    ("CDC ambiguity", "Use validated synchronizer/handshake kernel. Do not synthesize unsafe bitwise bus synchronization."),
    ("width mismatch", "Prefer explicit adapter. Zero-extend when safe; truncate only when specification explicitly permits."),
]
