"""Structured schemas used by COHERENT.

The classes in this file define the formal candidate-plan representation,
knowledge-graph elements, kernel metadata, diagnostics, and checker results.
They are intentionally plain dataclasses so the schema is easy to inspect,
serialize, and reproduce.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import json


class Direction(str, Enum):
    IN = "in"
    OUT = "out"
    INOUT = "inout"


class NodeType(str, Enum):
    PORT = "port"
    REGISTER = "register"
    COUNTER = "counter"
    FSM = "fsm"
    FSM_STATE = "fsm_state"
    MEMORY = "memory"
    MODULE = "module"
    CLOCK = "clock"
    RESET = "reset"
    OUTPUT = "output"
    CONSTRAINT = "constraint"
    DATAPATH = "datapath"
    CONTROL = "control"


class EdgeType(str, Enum):
    DRIVES = "drives"
    READS = "reads"
    UPDATES = "updates"
    RESETS = "resets"
    TRANSITIONS_TO = "transitions_to"
    DEPENDS_ON = "depends_on"
    CONNECTS_TO = "connects_to"
    CONTAINS = "contains"
    CLOCKS = "clocks"
    ENABLES = "enables"


@dataclass
class Port:
    name: str
    direction: Direction
    width: int = 1
    dtype: str = "std_logic"
    clock_domain: Optional[str] = None
    description: str = ""


@dataclass
class Signal:
    name: str
    width: int = 1
    dtype: str = "std_logic"
    producer: Optional[str] = None
    consumers: List[str] = field(default_factory=list)
    clock_domain: Optional[str] = None
    description: str = ""


@dataclass
class Module:
    name: str
    category: str
    ports: List[Port] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    role: str = ""


@dataclass
class FSM:
    name: str
    states: List[str]
    initial_state: str
    transitions: List[Dict[str, str]] = field(default_factory=list)
    output_style: str = "unspecified"  # moore, mealy, or unspecified


@dataclass
class TimingRequirement:
    name: str
    description: str
    latency_cycles: Optional[int] = None
    output_event: Optional[str] = None


@dataclass
class CandidatePlan:
    plan_id: str
    original_spec: str
    modules: List[Module] = field(default_factory=list)
    ports: List[Port] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    fsms: List[FSM] = field(default_factory=list)
    datapath: List[str] = field(default_factory=list)
    timing: List[TimingRequirement] = field(default_factory=list)
    reset_policy: str = "unspecified"
    constraints: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def normalized_text(self) -> str:
        """Canonical text for embedding/clustering.

        The ordering is fixed to reduce sensitivity to incidental formatting.
        """
        chunks: List[str] = [f"spec: {self.original_spec}"]
        chunks.append("modules: " + ", ".join(sorted(m.name + ":" + m.category for m in self.modules)))
        chunks.append("ports: " + ", ".join(sorted(f"{p.name}:{p.direction}:{p.width}" for p in self.ports)))
        chunks.append("signals: " + ", ".join(sorted(f"{s.name}:{s.width}" for s in self.signals)))
        chunks.append("fsms: " + ", ".join(sorted(f"{f.name}:{'|'.join(f.states)}:{f.output_style}" for f in self.fsms)))
        chunks.append("datapath: " + ", ".join(sorted(self.datapath)))
        chunks.append("timing: " + ", ".join(sorted(t.description for t in self.timing)))
        chunks.append("reset_policy: " + self.reset_policy)
        chunks.append("constraints: " + ", ".join(sorted(self.constraints)))
        chunks.append("assumptions: " + ", ".join(sorted(self.assumptions)))
        return "\n".join(chunks)


@dataclass
class KGNode:
    node_id: str
    node_type: NodeType
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KGEdge:
    src: str
    dst: str
    edge_type: EdgeType
    condition: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeGraph:
    nodes: List[KGNode] = field(default_factory=list)
    edges: List[KGEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KernelMetadata:
    kernel_id: str
    name: str
    category: str
    description: str
    tags: List[str]
    ports: List[Port]
    parameters: Dict[str, Any] = field(default_factory=dict)
    timing: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    verification: Dict[str, bool] = field(default_factory=dict)
    hdl_path: Optional[str] = None

    def retrieval_text(self) -> str:
        return "\n".join([
            self.name,
            self.category,
            self.description,
            "tags: " + ", ".join(sorted(self.tags)),
            "ports: " + ", ".join(sorted(f"{p.name}:{p.direction}:{p.width}" for p in self.ports)),
            "parameters: " + json.dumps(self.parameters, sort_keys=True),
            "constraints: " + ", ".join(sorted(self.constraints)),
        ])


@dataclass
class Diagnostic:
    error_type: str
    tool: str
    message: str
    module: Optional[str] = None
    line: Optional[int] = None
    expected: Optional[str] = None
    observed: Optional[str] = None
    time: Optional[str] = None
    raw_log: str = ""

    def to_prompt_block(self) -> str:
        return json.dumps(asdict(self), indent=2)


@dataclass
class CheckerResult:
    passed: bool
    stage: str
    diagnostics: List[Diagnostic] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
