"""
retrieval.py

S2 kernel retrieval scoring for COHERENT.

The retrieval stage receives a merged S3 conceptual plan and ranks reusable
kernels from the kernel library.

Main scoring rule:

    Score(k) = 0.60 * Sim_emb
             + 0.25 * Sim_tag
             + 0.15 * Sim_if

where:

    Sim_emb = cosine similarity between S3 query embedding and kernel embedding
    Sim_tag = normalized functional tag overlap
    Sim_if  = interface compatibility score

Merge confidence rule:

    Confidence(d) = 0.50 * F_cluster
                  + 0.30 * F_spec
                  + 0.20 * F_consistency

where:

    F_cluster     = frequency of the decision in the dominant cluster
    F_spec        = alignment of the decision with the original specification
    F_consistency = structural consistency of the decision with the merged plan

The implementation is intentionally explicit so the retrieval and merge
confidence procedures are reproducible from the paper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

from .embedding import Embedder, cosine_similarity
from .schemas import CandidatePlan, KernelMetadata, Port


# ---------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------


@dataclass
class InterfaceBreakdown:
    """
    Detailed interface-compatibility score.

    All fields are normalized to [0, 1].
    """

    port_name: float = 0.0
    width: float = 0.0
    direction: float = 0.0
    clock_reset: float = 0.0
    parameter: float = 0.0

    @property
    def total(self) -> float:
        """
        Interface score:

            Sim_if = 0.40 * port_name
                   + 0.25 * width
                   + 0.20 * direction
                   + 0.10 * clock_reset
                   + 0.05 * parameter
        """

        return (
            0.40 * self.port_name
            + 0.25 * self.width
            + 0.20 * self.direction
            + 0.10 * self.clock_reset
            + 0.05 * self.parameter
        )


@dataclass
class MergeConfidenceBreakdown:
    """
    Confidence assigned to a merged S3 design decision.

    Formula:

        Confidence(d) = 0.50 * F_cluster
                      + 0.30 * F_spec
                      + 0.20 * F_consistency
    """

    decision: str
    f_cluster: float
    f_spec: float
    f_consistency: float

    @property
    def total(self) -> float:
        return (
            0.50 * self.f_cluster
            + 0.30 * self.f_spec
            + 0.20 * self.f_consistency
        )


@dataclass
class RetrievalScore:
    """
    Retrieval result for one kernel.
    """

    kernel: KernelMetadata
    total: float
    sim_emb: float
    sim_tag: float
    sim_if: float
    interface_breakdown: InterfaceBreakdown
    matched_tags: List[str] = field(default_factory=list)
    missing_query_tags: List[str] = field(default_factory=list)
    matched_ports: List[str] = field(default_factory=list)
    adaptation_cost: float = 0.0
    rejection_reason: str = ""


# ---------------------------------------------------------------------
# Normalization Helpers
# ---------------------------------------------------------------------


TAG_ALIASES: Dict[str, str] = {
    "finite_state_machine": "fsm",
    "state_machine": "fsm",
    "moore_fsm": "moore",
    "mealy_fsm": "mealy",
    "shiftreg": "shift_register",
    "shift-register": "shift_register",
    "sipo": "serial_to_parallel",
    "piso": "parallel_to_serial",
    "mod_counter": "modulo_counter",
    "modulo": "modulo_counter",
    "terminal": "terminal_count",
    "tc": "terminal_count",
    "cdc_sync": "cdc",
    "clock_domain_crossing": "cdc",
    "validready": "valid_ready",
    "readyvalid": "valid_ready",
    "loadbusy": "load_busy",
}


CLOCK_NAMES = {"clk", "clock", "clk_i", "i_clk"}
RESET_NAMES = {"rst", "reset", "rst_i", "i_rst", "rst_n", "reset_n"}


def normalize_token(token: str) -> str:
    """
    Normalize tags, categories, and signal-role names.
    """

    t = str(token).strip().lower()
    t = t.replace("-", "_").replace(" ", "_")
    return TAG_ALIASES.get(t, t)


def normalize_direction(direction: object) -> str:
    """
    Normalize port direction enum/string values.
    """

    text = str(direction).lower()

    if "." in text:
        text = text.split(".")[-1]

    if text in {"in", "input"}:
        return "in"

    if text in {"out", "output"}:
        return "out"

    if text in {"inout", "bidirectional"}:
        return "inout"

    return text


def normalize_tags(tags: Sequence[str]) -> List[str]:
    """
    Normalize and deduplicate tags while preserving deterministic order.
    """

    seen = set()
    result: List[str] = []

    for tag in tags:
        t = normalize_token(tag)
        if t and t not in seen:
            result.append(t)
            seen.add(t)

    return result


def port_role_name(port: Port) -> str:
    """
    Normalize a port name into a role-like name.
    """

    name = normalize_token(port.name)

    for suffix in ("_i", "_o", "_in", "_out"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    if name in CLOCK_NAMES:
        return "clk"

    if name in RESET_NAMES:
        return "rst"

    return name


def get_width(port: Port) -> int:
    """
    Safely extract port width.
    """

    width = getattr(port, "width", 1)

    try:
        return int(width)
    except Exception:
        return 1


# ---------------------------------------------------------------------
# Merge Confidence
# ---------------------------------------------------------------------


def plan_decision_tokens(plan: CandidatePlan) -> List[str]:
    """
    Extract normalized decision tokens from a candidate or merged plan.

    These tokens represent architectural decisions used during merge
    confidence computation.
    """

    tokens: List[str] = []

    for module in getattr(plan, "modules", []):
        tokens.extend(
            [
                getattr(module, "name", ""),
                getattr(module, "category", ""),
                getattr(module, "type", ""),
                getattr(module, "role", ""),
            ]
        )

    for dp in getattr(plan, "datapath", []):
        if isinstance(dp, str):
            tokens.append(dp)
        else:
            tokens.extend(
                [
                    getattr(dp, "name", ""),
                    getattr(dp, "type", ""),
                    getattr(dp, "role", ""),
                ]
            )

    for fsm in getattr(plan, "fsms", []):
        tokens.append("fsm")
        tokens.append(getattr(fsm, "name", ""))
        tokens.append(getattr(fsm, "output_style", getattr(fsm, "style", "")))
        tokens.extend([str(s) for s in getattr(fsm, "states", [])])

    for timing in getattr(plan, "timing", []):
        if isinstance(timing, str):
            tokens.append(timing)
        else:
            tokens.append(getattr(timing, "name", ""))
            tokens.append(getattr(timing, "description", ""))
            tokens.append(str(getattr(timing, "latency_cycles", "")))

    for constraint in getattr(plan, "constraints", []):
        if isinstance(constraint, str):
            tokens.append(constraint)
        elif isinstance(constraint, dict):
            tokens.extend([str(v) for v in constraint.values()])
        else:
            tokens.append(getattr(constraint, "type", ""))
            tokens.append(getattr(constraint, "description", ""))

    reset_policy = getattr(plan, "reset_policy", "")
    if reset_policy:
        tokens.append(str(reset_policy))

    return normalize_tags([t for t in tokens if t])


def dominant_cluster_plans(
    candidates: Sequence[CandidatePlan],
    labels: Sequence[int],
    dominant_cluster_id: int,
) -> List[CandidatePlan]:
    """
    Return candidates that belong to the dominant cluster.
    """

    return [
        plan
        for plan, label in zip(candidates, labels)
        if label == dominant_cluster_id
    ]


def decision_cluster_frequency(
    decision: str,
    dominant_plans: Sequence[CandidatePlan],
) -> float:
    """
    Compute F_cluster.

    F_cluster is the fraction of dominant-cluster plans that contain the
    selected decision.
    """

    if not dominant_plans:
        return 0.0

    d = normalize_token(decision)
    count = 0

    for plan in dominant_plans:
        tokens = set(plan_decision_tokens(plan))
        if d in tokens:
            count += 1

    return count / len(dominant_plans)


def decision_spec_alignment(
    decision: str,
    specification: str,
) -> float:
    """
    Compute F_spec.

    F_spec measures whether the selected decision is directly supported by
    the original natural-language specification.

    Exact normalized token appearance receives 1.0.
    Partial normalized phrase overlap receives fractional credit.
    """

    d = normalize_token(decision)
    spec_tokens = set(normalize_tags(specification.replace(",", " ").split()))

    if d in spec_tokens:
        return 1.0

    parts = set(d.split("_"))
    if not parts:
        return 0.0

    overlap = len(parts & spec_tokens) / len(parts)
    return max(0.0, min(1.0, overlap))


def decision_consistency_score(
    decision: str,
    merged_plan: CandidatePlan,
) -> float:
    """
    Compute F_consistency.

    F_consistency measures whether the selected decision is structurally
    consistent with the merged plan.

    A decision receives high score if it appears in the merged modules,
    datapath, FSMs, timing requirements, constraints, or reset policy.
    """

    d = normalize_token(decision)
    merged_tokens = set(plan_decision_tokens(merged_plan))

    if d in merged_tokens:
        return 1.0

    parts = set(d.split("_"))
    if not parts:
        return 0.0

    overlap = len(parts & merged_tokens) / len(parts)
    return max(0.0, min(1.0, overlap))


def compute_merge_confidence(
    decision: str,
    candidates: Sequence[CandidatePlan],
    labels: Sequence[int],
    dominant_cluster_id: int,
    merged_plan: CandidatePlan,
) -> MergeConfidenceBreakdown:
    """
    Compute merge confidence for one merged design decision.

    Formula:

        Confidence(d) = 0.50 * F_cluster
                      + 0.30 * F_spec
                      + 0.20 * F_consistency
    """

    dominant = dominant_cluster_plans(
        candidates=candidates,
        labels=labels,
        dominant_cluster_id=dominant_cluster_id,
    )

    specification = getattr(merged_plan, "original_spec", "")

    f_cluster = decision_cluster_frequency(decision, dominant)
    f_spec = decision_spec_alignment(decision, specification)
    f_consistency = decision_consistency_score(decision, merged_plan)

    return MergeConfidenceBreakdown(
        decision=decision,
        f_cluster=round(f_cluster, 6),
        f_spec=round(f_spec, 6),
        f_consistency=round(f_consistency, 6),
    )


def compute_plan_merge_confidences(
    merged_plan: CandidatePlan,
    candidates: Sequence[CandidatePlan],
    labels: Sequence[int],
    dominant_cluster_id: int,
) -> List[MergeConfidenceBreakdown]:
    """
    Compute merge confidence for all normalized decisions in the merged plan.
    """

    decisions = plan_decision_tokens(merged_plan)

    return [
        compute_merge_confidence(
            decision=decision,
            candidates=candidates,
            labels=labels,
            dominant_cluster_id=dominant_cluster_id,
            merged_plan=merged_plan,
        )
        for decision in decisions
    ]


# ---------------------------------------------------------------------
# Tag Similarity
# ---------------------------------------------------------------------


def tag_similarity(
    query_tags: Sequence[str],
    kernel_tags: Sequence[str],
) -> Tuple[float, List[str], List[str]]:
    """
    Compute normalized tag overlap.

    Formula:

        Sim_tag = |Q ∩ K| / |Q ∪ K|

    This is Jaccard similarity after tag normalization.

    Returns:
        score, matched_tags, missing_query_tags
    """

    q = set(normalize_tags(query_tags))
    k = set(normalize_tags(kernel_tags))

    if not q and not k:
        return 1.0, [], []

    if not q or not k:
        return 0.0, [], sorted(q)

    matched = sorted(q & k)
    missing = sorted(q - k)
    union = q | k

    return len(matched) / len(union), matched, missing


# ---------------------------------------------------------------------
# Interface Similarity
# ---------------------------------------------------------------------


def _best_kernel_port_match(
    query_port: Port,
    kernel_ports: Sequence[Port],
) -> Tuple[Port | None, float]:
    """
    Find the best role/name match for a query port among kernel ports.

    Exact normalized role name match receives 1.0.
    Clock/reset aliases are also normalized.
    """

    qrole = port_role_name(query_port)
    best_port = None
    best_score = 0.0

    for kp in kernel_ports:
        krole = port_role_name(kp)

        if qrole == krole:
            score = 1.0
        elif qrole in krole or krole in qrole:
            score = 0.5
        else:
            score = 0.0

        if score > best_score:
            best_port = kp
            best_score = score

    return best_port, best_score


def width_match_score(query_width: int, kernel_width: int) -> float:
    """
    Width compatibility score.

    Exact match gets 1.0.
    Small width differences receive partial credit.
    Large mismatches receive low credit.
    """

    if query_width <= 0 or kernel_width <= 0:
        return 0.0

    if query_width == kernel_width:
        return 1.0

    diff = abs(query_width - kernel_width)
    return 1.0 / (1.0 + diff)


def parameter_compatibility(
    plan: CandidatePlan,
    kernel: KernelMetadata,
) -> float:
    """
    Estimate whether a kernel can be adapted using parameters.

    A parameterized kernel is preferred because S2 can adapt it with less
    behavioral change.
    """

    params = getattr(kernel, "parameters", {})

    if params is None:
        return 0.0

    if isinstance(params, dict) and len(params) > 0:
        return 1.0

    return 0.5


def interface_similarity(
    query_ports: Sequence[Port],
    kernel_ports: Sequence[Port],
    plan: CandidatePlan | None = None,
    kernel: KernelMetadata | None = None,
) -> Tuple[float, InterfaceBreakdown, List[str]]:
    """
    Compute interface compatibility.

    Formula:

        Sim_if = 0.40 * Simport
               + 0.25 * Simwidth
               + 0.20 * Simdir
               + 0.10 * Simclkreset
               + 0.05 * Simparam
    """

    if not query_ports or not kernel_ports:
        breakdown = InterfaceBreakdown()
        return 0.0, breakdown, []

    matched_ports: List[str] = []
    port_name_scores: List[float] = []
    width_scores: List[float] = []
    direction_scores: List[float] = []

    for qp in query_ports:
        kp, name_score = _best_kernel_port_match(qp, kernel_ports)
        port_name_scores.append(name_score)

        if kp is None:
            width_scores.append(0.0)
            direction_scores.append(0.0)
            continue

        if name_score > 0.0:
            matched_ports.append(f"{qp.name}->{kp.name}")

        width_scores.append(width_match_score(get_width(qp), get_width(kp)))

        qdir = normalize_direction(getattr(qp, "direction", ""))
        kdir = normalize_direction(getattr(kp, "direction", ""))

        direction_scores.append(1.0 if qdir == kdir else 0.0)

    port_name = sum(port_name_scores) / len(port_name_scores)
    width = sum(width_scores) / len(width_scores)
    direction = sum(direction_scores) / len(direction_scores)

    q_cr = {
        port_role_name(p)
        for p in query_ports
        if port_role_name(p) in {"clk", "rst"}
    }

    k_cr = {
        port_role_name(p)
        for p in kernel_ports
        if port_role_name(p) in {"clk", "rst"}
    }

    if not q_cr and not k_cr:
        clock_reset = 1.0
    else:
        clock_reset = len(q_cr & k_cr) / max(len(q_cr | k_cr), 1)

    if plan is not None and kernel is not None:
        parameter = parameter_compatibility(plan, kernel)
    else:
        parameter = 0.5

    breakdown = InterfaceBreakdown(
        port_name=port_name,
        width=width,
        direction=direction,
        clock_reset=clock_reset,
        parameter=parameter,
    )

    return breakdown.total, breakdown, matched_ports


# ---------------------------------------------------------------------
# Query Construction
# ---------------------------------------------------------------------


def _stringify_items(items: Sequence[object]) -> List[str]:
    """
    Convert mixed schema objects into short strings.
    """

    out: List[str] = []

    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.append(" ".join(f"{k}:{v}" for k, v in item.items()))
        else:
            name = getattr(item, "name", "")
            category = getattr(item, "category", getattr(item, "type", ""))
            role = getattr(item, "role", "")
            desc = getattr(item, "description", "")
            text = " ".join(str(x) for x in [name, category, role, desc] if x)
            if text:
                out.append(text)

    return out


def plan_query_text(plan: CandidatePlan) -> str:
    """
    Construct the embedding query text from the merged S3 plan.
    """

    original_spec = getattr(plan, "original_spec", "")

    modules = _stringify_items(getattr(plan, "modules", []))
    datapath = _stringify_items(getattr(plan, "datapath", []))
    constraints = _stringify_items(getattr(plan, "constraints", []))
    timing = _stringify_items(getattr(plan, "timing", []))
    fsms = _stringify_items(getattr(plan, "fsms", []))

    ports = []

    for p in getattr(plan, "ports", []):
        ports.append(
            f"{p.name}:{normalize_direction(getattr(p, 'direction', ''))}:"
            f"width={get_width(p)}"
        )

    return "\n".join(
        [
            "original_spec: " + original_spec,
            "modules: " + ", ".join(modules),
            "datapath: " + ", ".join(datapath),
            "fsms: " + ", ".join(fsms),
            "ports: " + ", ".join(ports),
            "constraints: " + ", ".join(constraints),
            "timing: " + ", ".join(timing),
        ]
    )


def plan_tags(plan: CandidatePlan) -> List[str]:
    """
    Extract functional tags from the S3 plan.
    """

    tags: List[str] = []

    for m in getattr(plan, "modules", []):
        tags.extend(
            [
                getattr(m, "name", ""),
                getattr(m, "category", ""),
                getattr(m, "type", ""),
                getattr(m, "role", ""),
            ]
        )

    for dp in getattr(plan, "datapath", []):
        if isinstance(dp, str):
            tags.append(dp)
        else:
            tags.extend(
                [
                    getattr(dp, "name", ""),
                    getattr(dp, "type", ""),
                    getattr(dp, "role", ""),
                ]
            )

    for fsm in getattr(plan, "fsms", []):
        tags.append("fsm")
        tags.append(getattr(fsm, "output_style", getattr(fsm, "style", "")))

    for c in getattr(plan, "constraints", []):
        if isinstance(c, str):
            tags.append(c)
        elif isinstance(c, dict):
            tags.extend([str(c.get("type", "")), str(c.get("description", ""))])
        else:
            tags.extend(
                [
                    getattr(c, "type", ""),
                    getattr(c, "description", ""),
                ]
            )

    return normalize_tags([t for t in tags if t])


# ---------------------------------------------------------------------
# Kernel Filtering and Penalties
# ---------------------------------------------------------------------


def kernel_passes_basic_validation(kernel: KernelMetadata) -> Tuple[bool, str]:
    """
    Reject kernels that should not be used by retrieval.

    This protects against failed, non-synthesizable, or task-specific kernels.
    """

    verification = getattr(kernel, "verification", {}) or {}

    syntax_pass = verification.get("syntax_pass", True)
    sim_pass = verification.get("sim_pass", verification.get("simulation_pass", True))

    if not syntax_pass:
        return False, "kernel_failed_syntax_validation"

    if not sim_pass:
        return False, "kernel_failed_simulation_validation"

    tags = set(normalize_tags(getattr(kernel, "tags", [])))

    if "task_specific_solution" in tags or "golden_solution" in tags:
        return False, "kernel_appears_task_specific"

    return True, ""


def estimate_adaptation_cost(
    sim_if: float,
    sim_tag: float,
    kernel: KernelMetadata,
) -> float:
    """
    Estimate adaptation cost.

    Lower is better.
    """

    cost = 0.0

    cost += 1.0 - sim_if
    cost += 0.5 * (1.0 - sim_tag)

    params = getattr(kernel, "parameters", {}) or {}

    if not params:
        cost += 0.25

    return round(cost, 4)


# ---------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------


def retrieve_kernels(
    plan: CandidatePlan,
    kernels: Iterable[KernelMetadata],
    top_k: int = 5,
    w_emb: float = 0.60,
    w_tag: float = 0.25,
    w_if: float = 0.15,
    embedder: Embedder | None = None,
) -> List[RetrievalScore]:
    """
    Retrieve and rank reusable kernels for a merged S3 plan.
    """

    if top_k <= 0:
        raise ValueError("top_k must be positive")

    weight_sum = w_emb + w_tag + w_if

    if abs(weight_sum - 1.0) > 1e-6:
        raise ValueError("Retrieval weights must sum to 1.0")

    kernels = list(kernels)
    embedder = embedder or Embedder()

    query_text = plan_query_text(plan)
    qtags = plan_tags(plan)

    valid_kernels: List[KernelMetadata] = []

    for kernel in kernels:
        ok, _ = kernel_passes_basic_validation(kernel)

        if ok:
            valid_kernels.append(kernel)

    if not valid_kernels:
        return []

    kernel_texts = [k.retrieval_text() for k in valid_kernels]
    vectors = embedder.encode([query_text] + kernel_texts)

    qv = vectors[0]
    kvs = vectors[1:]

    scores: List[RetrievalScore] = []

    for kernel, kv in zip(valid_kernels, kvs):
        sim_emb = cosine_similarity(qv, kv)

        sim_tag, matched_tags, missing_tags = tag_similarity(
            qtags,
            getattr(kernel, "tags", []),
        )

        sim_if, breakdown, matched_ports = interface_similarity(
            getattr(plan, "ports", []),
            getattr(kernel, "ports", []),
            plan=plan,
            kernel=kernel,
        )

        total = (w_emb * sim_emb) + (w_tag * sim_tag) + (w_if * sim_if)

        adaptation_cost = estimate_adaptation_cost(
            sim_if=sim_if,
            sim_tag=sim_tag,
            kernel=kernel,
        )

        scores.append(
            RetrievalScore(
                kernel=kernel,
                total=round(total, 6),
                sim_emb=round(sim_emb, 6),
                sim_tag=round(sim_tag, 6),
                sim_if=round(sim_if, 6),
                interface_breakdown=breakdown,
                matched_tags=matched_tags,
                missing_query_tags=missing_tags,
                matched_ports=matched_ports,
                adaptation_cost=adaptation_cost,
            )
        )

    scores.sort(
        key=lambda s: (
            s.total,
            -s.adaptation_cost,
            s.sim_if,
            s.sim_tag,
        ),
        reverse=True,
    )

    return scores[:top_k]


# ---------------------------------------------------------------------
# Reporting Helpers
# ---------------------------------------------------------------------


def merge_confidences_to_dict(
    confidences: Sequence[MergeConfidenceBreakdown],
) -> List[dict]:
    """
    Convert merge-confidence values into JSON-serializable dictionaries.
    """

    return [
        {
            "decision": c.decision,
            "F_cluster": c.f_cluster,
            "F_spec": c.f_spec,
            "F_consistency": c.f_consistency,
            "confidence": round(c.total, 6),
        }
        for c in confidences
    ]


def retrieval_scores_to_dict(scores: Sequence[RetrievalScore]) -> List[dict]:
    """
    Convert RetrievalScore objects into JSON-serializable dictionaries.
    """

    rows: List[dict] = []

    for s in scores:
        kernel = s.kernel

        rows.append(
            {
                "kernel_id": getattr(kernel, "kernel_id", ""),
                "kernel_name": getattr(kernel, "name", ""),
                "category": getattr(kernel, "category", ""),
                "total": s.total,
                "Simemb": s.sim_emb,
                "Simtag": s.sim_tag,
                "Simif": s.sim_if,
                "interface_breakdown": {
                    "port_name": round(s.interface_breakdown.port_name, 6),
                    "width": round(s.interface_breakdown.width, 6),
                    "direction": round(s.interface_breakdown.direction, 6),
                    "clock_reset": round(s.interface_breakdown.clock_reset, 6),
                    "parameter": round(s.interface_breakdown.parameter, 6),
                    "total": round(s.interface_breakdown.total, 6),
                },
                "matched_tags": s.matched_tags,
                "missing_query_tags": s.missing_query_tags,
                "matched_ports": s.matched_ports,
                "adaptation_cost": s.adaptation_cost,
                "rejection_reason": s.rejection_reason,
            }
        )

    return rows