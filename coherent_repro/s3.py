"""
s3.py

Stage S3: candidate-plan generation interface, knowledge-graph construction,
clustering, confidence-based merge, and merged-plan validation.

S3 is the conceptual reasoning stage of COHERENT.

It performs:

1. Candidate architecture generation
2. Candidate-plan normalization
3. Knowledge-graph construction
4. Candidate clustering
5. Dominant-cluster selection
6. Confidence-based merge
7. Merged-plan validation

S3 does not generate VHDL code.
S3 only produces a structured conceptual plan for S2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from .clustering import ClusterResult, cluster_candidate_plans
from .graph import build_knowledge_graph, validate_knowledge_graph
from .merge import merge_candidate_plans
from .schemas import CandidatePlan, CheckerResult, KnowledgeGraph
from .validation import validate_merged_plan


# ---------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------


@dataclass
class S3PromptConfig:
    """Configuration used for candidate-plan generation."""

    n_candidates: int = 5
    temperature: float = 0.2
    top_p: float = 0.9
    output_format: str = "json"
    require_no_code: bool = True


@dataclass
class S3GenerationRecord:
    """
    Metadata recording how S3 candidates were produced.

    This is useful for reproducibility logs.
    """

    specification: str
    prompt_config: S3PromptConfig
    prompt_text: str = ""
    model_name: str = ""
    raw_response: str = ""
    parse_errors: List[str] = field(default_factory=list)


@dataclass
class S3Output:
    """Final output of Stage S3."""

    candidates: List[CandidatePlan]
    graphs: List[KnowledgeGraph]
    graph_validation_issues: List[List[str]]
    clustering: ClusterResult
    dominant_candidates: List[CandidatePlan]
    merged_plan: CandidatePlan
    validation: CheckerResult
    generation_record: Optional[S3GenerationRecord] = None
    notes: List[str] = field(default_factory=list)


CandidateGenerator = Callable[[str, S3PromptConfig], List[CandidatePlan]]


# ---------------------------------------------------------------------
# Prompt Construction
# ---------------------------------------------------------------------


def build_s3_candidate_prompt(
    specification: str,
    config: Optional[S3PromptConfig] = None,
) -> str:
    """
    Build the S3 candidate generation prompt.

    The prompt asks the LLM to produce structured JSON candidate plans.
    """

    config = config or S3PromptConfig()

    return f"""
# S3 Candidate Plan Generation

You are operating inside COHERENT Stage S3.

You are a hardware architecture reasoning expert.

Read the natural-language VHDL specification and generate multiple candidate
architecture plans before any VHDL code is written.

Do not generate VHDL.
Do not generate testbenches.
Return valid JSON only.

## Specification

```text
{specification}
```

## Required Number of Candidates

Generate exactly {config.n_candidates} candidate plans.

Each candidate must include:

1. module hierarchy
2. ports and directions
3. internal signals
4. clock/reset policy
5. FSM states if applicable
6. datapath elements
7. timing assumptions
8. interface definitions
9. constraints
10. assumptions
11. confidence score

## Required JSON Structure

```json
{{
  "candidates": [
    {{
      "plan_id": "P1",
      "architecture_style": "",
      "summary": "",
      "modules": [],
      "ports": [],
      "signals": [],
      "fsms": [],
      "datapath": [],
      "control": [],
      "timing": [],
      "reset_policy": {{
        "style": "synchronous|asynchronous|none|unspecified",
        "polarity": "active_high|active_low|none|unspecified",
        "source": "specified|inferred",
        "reset_values": {{}}
      }},
      "interfaces": [],
      "constraints": [],
      "assumptions": [],
      "ambiguities_resolved": [],
      "confidence": 0.0,
      "confidence_rationale": ""
    }}
  ]
}}
```

## Candidate Diversity Requirement

Candidates must explore meaningfully different architectural interpretations
when ambiguity exists.

Examples:

* FSM-control vs counter-control
* registered output vs combinational output
* Moore FSM vs Mealy FSM
* hierarchical design vs compact design
* handshake-aware variant vs simple valid-pulse variant

## Strict Output Rule

Return only valid JSON.
""".strip()


# ---------------------------------------------------------------------
# Candidate Normalization
# ---------------------------------------------------------------------


def normalize_candidate_plan(plan: CandidatePlan, index: int) -> CandidatePlan:
    """
    Normalize one candidate plan before graph construction and clustering.

    This function is intentionally conservative. It fills missing identifiers
    and ensures stable plan IDs for reproducibility.
    """

    if not getattr(plan, "plan_id", ""):
        plan.plan_id = f"P{index + 1}"

    if not getattr(plan, "confidence", None):
        plan.confidence = 0.5

    return plan


def normalize_candidates(candidates: Sequence[CandidatePlan]) -> List[CandidatePlan]:
    """Normalize all candidate plans."""

    return [normalize_candidate_plan(plan, i) for i, plan in enumerate(candidates)]


# ---------------------------------------------------------------------
# Dominant Cluster Extraction
# ---------------------------------------------------------------------


def dominant_cluster_candidates(
    candidates: Sequence[CandidatePlan],
    labels: Sequence[int],
    dominant_cluster_id: int,
) -> List[CandidatePlan]:
    """
    Return candidates belonging to the dominant cluster.

    The dominant cluster represents the most internally consistent group of
    architectural interpretations.
    """

    return [
        candidate
        for candidate, label in zip(candidates, labels)
        if label == dominant_cluster_id
    ]


# ---------------------------------------------------------------------
# Main S3 Pipeline
# ---------------------------------------------------------------------


def run_s3_from_candidates(
    candidates: List[CandidatePlan],
    *,
    generation_record: Optional[S3GenerationRecord] = None,
) -> S3Output:
    """
    Run the complete S3 pipeline from already-generated candidate plans.

    Steps:
    1. normalize candidates
    2. construct knowledge graph for each candidate
    3. validate each graph
    4. cluster candidate plans
    5. select dominant cluster
    6. merge dominant-cluster candidates
    7. validate merged conceptual plan
    """

    if not candidates:
        raise ValueError("S3 requires at least one candidate plan.")

    normalized = normalize_candidates(candidates)

    graphs = [build_knowledge_graph(plan) for plan in normalized]
    graph_issues = [validate_knowledge_graph(graph) for graph in graphs]

    clustering = cluster_candidate_plans(normalized)

    dominant = dominant_cluster_candidates(
        candidates=normalized,
        labels=clustering.labels,
        dominant_cluster_id=clustering.dominant_cluster_id,
    )

    if not dominant:
        dominant = normalized

    merged = merge_candidate_plans(
        normalized,
        clustering.labels,
        clustering.dominant_cluster_id,
    )

    validation = validate_merged_plan(merged)

    notes: List[str] = []

    notes.append(f"Input candidates: {len(normalized)}")
    notes.append(f"Dominant cluster id: {clustering.dominant_cluster_id}")
    notes.append(f"Dominant cluster size: {len(dominant)}")

    if any(graph_issues):
        notes.append("Some candidate knowledge graphs contain validation warnings.")

    return S3Output(
        candidates=normalized,
        graphs=graphs,
        graph_validation_issues=graph_issues,
        clustering=clustering,
        dominant_candidates=dominant,
        merged_plan=merged,
        validation=validation,
        generation_record=generation_record,
        notes=notes,
    )


def run_s3_from_specification(
    specification: str,
    generator: CandidateGenerator,
    *,
    config: Optional[S3PromptConfig] = None,
    model_name: str = "",
) -> S3Output:
    """
    Run S3 directly from a natural-language specification.

    The generator function is responsible for calling the selected LLM or
    deterministic candidate-generation backend.

    generator signature:
        generator(specification, config) -> List[CandidatePlan]

    This makes the S3 interface reproducible and testable because the LLM
    call is injected rather than hidden inside the pipeline.
    """

    config = config or S3PromptConfig()
    prompt = build_s3_candidate_prompt(specification, config)

    record = S3GenerationRecord(
        specification=specification,
        prompt_config=config,
        prompt_text=prompt,
        model_name=model_name,
    )

    candidates = generator(specification, config)

    output = run_s3_from_candidates(
        candidates,
        generation_record=record,
    )

    return output


# ---------------------------------------------------------------------
# Reporting Helpers
# ---------------------------------------------------------------------


def s3_summary(output: S3Output) -> Dict[str, object]:
    """Produce a compact JSON-serializable summary of S3 output."""

    return {
        "num_candidates": len(output.candidates),
        "num_graphs": len(output.graphs),
        "cluster_labels": list(output.clustering.labels),
        "dominant_cluster_id": output.clustering.dominant_cluster_id,
        "dominant_cluster_size": len(output.dominant_candidates),
        "merged_plan_id": getattr(output.merged_plan, "plan_id", ""),
        "validation_pass": getattr(output.validation, "passed", False),
        "validation_messages": getattr(output.validation, "messages", []),
        "notes": output.notes,
    }


def explain_s3_output(output: S3Output) -> str:
    """
    Human-readable explanation for logs or supplementary material.

    This should not be used inside LLM prompts.
    """

    lines: List[str] = []

    lines.append("S3 Conceptual Reasoning Summary")
    lines.append("--------------------------------")
    lines.append(f"Candidate plans: {len(output.candidates)}")
    lines.append(f"Knowledge graphs: {len(output.graphs)}")
    lines.append(f"Cluster labels: {list(output.clustering.labels)}")
    lines.append(f"Dominant cluster: {output.clustering.dominant_cluster_id}")
    lines.append(f"Dominant candidates: {len(output.dominant_candidates)}")

    lines.append("")
    lines.append("Graph validation issues:")

    for idx, issues in enumerate(output.graph_validation_issues):
        plan_id = getattr(output.candidates[idx], "plan_id", f"P{idx + 1}")
        if issues:
            lines.append(f"- {plan_id}: {len(issues)} issue(s)")
            for issue in issues:
                lines.append(f"  - {issue}")
        else:
            lines.append(f"- {plan_id}: none")

    lines.append("")
    lines.append("Merged-plan validation:")

    validation_pass = getattr(output.validation, "passed", False)
    validation_messages = getattr(output.validation, "messages", [])

    lines.append(f"- passed: {validation_pass}")

    for message in validation_messages:
        lines.append(f"- {message}")

    return "\n".join(lines)


__all__ = [
    "S3PromptConfig",
    "S3GenerationRecord",
    "S3Output",
    "CandidateGenerator",
    "build_s3_candidate_prompt",
    "normalize_candidate_plan",
    "normalize_candidates",
    "dominant_cluster_candidates",
    "run_s3_from_candidates",
    "run_s3_from_specification",
    "s3_summary",
    "explain_s3_output",
]