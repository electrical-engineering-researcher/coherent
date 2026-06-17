"""
kg.py

Knowledge-graph construction from S3 candidate plans.

The knowledge graph makes implicit hardware relationships explicit before
clustering and merge.

It represents:
- modules
- ports
- signals
- FSMs
- FSM states
- datapath elements
- constraints
- timing requirements
- reset policy
- interface relationships

The graph is used to detect:
- missing drivers
- dangling outputs
- inconsistent timing assumptions
- FSM transition conflicts
- reset conflicts
- module-interface mismatches
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .schemas import (
    CandidatePlan,
    EdgeType,
    KGEdge,
    KGNode,
    KnowledgeGraph,
    NodeType,
)


# ---------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------


def _safe_str(value: Any) -> str:
    """Convert schema enum/string values into stable lowercase strings."""

    if value is None:
        return ""

    text = str(value)

    if "." in text:
        text = text.split(".")[-1]

    return text.lower()


def _node_id(prefix: str, name: str) -> str:
    """Create a stable graph node ID."""

    clean = str(name).strip().replace(" ", "_")
    return f"{prefix}:{clean}"


def _add_node_once(
    graph: KnowledgeGraph,
    node_id: str,
    node_type: NodeType,
    name: str,
    **attrs: Any,
) -> None:
    """Add node only if it does not already exist."""

    existing = {n.node_id for n in graph.nodes}

    if node_id in existing:
        return

    graph.nodes.append(
        KGNode(
            node_id=node_id,
            node_type=node_type,
            name=name,
            attributes=attrs,
        )
    )


def _add_edge(
    graph: KnowledgeGraph,
    src: str,
    dst: str,
    edge_type: EdgeType,
    **attrs: Any,
) -> None:
    """Add a graph edge."""

    graph.edges.append(
        KGEdge(
            src=src,
            dst=dst,
            edge_type=edge_type,
            attributes=attrs,
        )
    )


def _direction_is_output(direction: Any) -> bool:
    """Return True when a port direction denotes output."""

    return _safe_str(direction) in {"out", "output"}


def _direction_is_input(direction: Any) -> bool:
    """Return True when a port direction denotes input."""

    return _safe_str(direction) in {"in", "input"}


def _infer_signal_node_type(name: str, role: str = "", signal_type: str = "") -> NodeType:
    """
    Infer graph node type for an internal signal.

    This is intentionally conservative.
    """

    lname = name.lower()
    lrole = role.lower()
    ltype = signal_type.lower()

    if "clk" in lname or lrole == "clock":
        return NodeType.CLOCK

    if "rst" in lname or "reset" in lname or lrole == "reset":
        return NodeType.RESET

    if "state" in lname:
        return NodeType.FSM_STATE

    if "count" in lname or "counter" in lrole:
        return NodeType.COUNTER

    if "reg" in lname or "register" in lrole or "register" in ltype:
        return NodeType.REGISTER

    if "mem" in lname or "fifo" in lname or "ram" in lname:
        return NodeType.MEMORY

    return NodeType.DATAPATH


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """
    Read attribute from dataclass/model/dict safely.
    """

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)



def build_knowledge_graph(plan: CandidatePlan) -> KnowledgeGraph:
    """
    Build a knowledge graph from one S3 candidate plan.

    The resulting graph contains explicit hardware entities and relations.

    Main edge types:
    - CONTAINS: module contains port/state/submodule
    - DRIVES: producer drives signal/output
    - READS: module/process reads a signal
    - UPDATES: FSM/datapath updates register/state
    - RESETS: reset controls stateful element
    - TRANSITIONS_TO: FSM transition
    - DEPENDS_ON: timing/control dependency
    - CONNECTS_TO: interface connection
    """

    graph = KnowledgeGraph()

    plan_id = _get_attr(plan, "plan_id", "unknown_plan")

    _add_node_once(
        graph,
        node_id=_node_id("plan", plan_id),
        node_type=NodeType.MODULE,
        name=plan_id,
        role="candidate_plan_root",
    )

    for port in _get_attr(plan, "ports", []):
        port_name = _get_attr(port, "name", "")
        direction = _get_attr(port, "direction", "")
        width = _get_attr(port, "width", 1)
        port_type = _get_attr(port, "type", "std_logic")
        role = _get_attr(port, "role", "")
        clock_domain = _get_attr(port, "clock_domain", "")

        if not port_name:
            continue

        if _direction_is_output(direction):
            node_type = NodeType.OUTPUT
        elif role.lower() == "clock":
            node_type = NodeType.CLOCK
        elif role.lower() == "reset":
            node_type = NodeType.RESET
        else:
            node_type = NodeType.PORT

        pid = _node_id("port", port_name)

        _add_node_once(
            graph,
            node_id=pid,
            node_type=node_type,
            name=port_name,
            direction=_safe_str(direction),
            width=width,
            type=port_type,
            role=role,
            clock_domain=clock_domain,
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=pid,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_port",
        )

    for module in _get_attr(plan, "modules", []):
        module_name = _get_attr(module, "name", "")
        if not module_name:
            continue

        mid = _node_id("module", module_name)

        _add_node_once(
            graph,
            node_id=mid,
            node_type=NodeType.MODULE,
            name=module_name,
            category=_get_attr(module, "category", _get_attr(module, "type", "")),
            role=_get_attr(module, "role", ""),
            parent=_get_attr(module, "parent", ""),
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=mid,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_module",
        )

        for port in _get_attr(module, "ports", []):
            pname = _get_attr(port, "name", "")
            if not pname:
                continue

            pid = _node_id("port", pname)

            _add_node_once(
                graph,
                node_id=pid,
                node_type=NodeType.PORT,
                name=pname,
                direction=_safe_str(_get_attr(port, "direction", "")),
                width=_get_attr(port, "width", 1),
                type=_get_attr(port, "type", "std_logic"),
            )

            _add_edge(
                graph,
                src=mid,
                dst=pid,
                edge_type=EdgeType.CONTAINS,
                relation="module_has_port",
            )


    for signal in _get_attr(plan, "signals", []):
        signal_name = _get_attr(signal, "name", "")
        if not signal_name:
            continue

        role = _get_attr(signal, "role", "")
        signal_type = _get_attr(signal, "type", "")
        width = _get_attr(signal, "width", 1)
        producer = _get_attr(signal, "producer", _get_attr(signal, "driver", ""))
        consumers = _get_attr(signal, "consumers", _get_attr(signal, "readers", []))
        reset_value = _get_attr(signal, "reset_value", "")

        sid = _node_id("signal", signal_name)

        _add_node_once(
            graph,
            node_id=sid,
            node_type=_infer_signal_node_type(signal_name, role, signal_type),
            name=signal_name,
            width=width,
            type=signal_type,
            role=role,
            reset_value=reset_value,
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=sid,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_signal",
        )

        if producer:
            src_id = producer if ":" in str(producer) else _node_id("producer", str(producer))

            _add_node_once(
                graph,
                node_id=src_id,
                node_type=NodeType.MODULE,
                name=str(producer),
                role="inferred_producer",
            )

            _add_edge(
                graph,
                src=src_id,
                dst=sid,
                edge_type=EdgeType.DRIVES,
                relation="producer_drives_signal",
            )

        for consumer in consumers:
            cid = consumer if ":" in str(consumer) else _node_id("consumer", str(consumer))

            _add_node_once(
                graph,
                node_id=cid,
                node_type=NodeType.MODULE,
                name=str(consumer),
                role="inferred_consumer",
            )

            _add_edge(
                graph,
                src=sid,
                dst=cid,
                edge_type=EdgeType.READS,
                relation="consumer_reads_signal",
            )

    for fsm in _get_attr(plan, "fsms", []):
        fsm_name = _get_attr(fsm, "name", "")
        if not fsm_name:
            continue

        fid = _node_id("fsm", fsm_name)

        _add_node_once(
            graph,
            node_id=fid,
            node_type=NodeType.FSM,
            name=fsm_name,
            output_style=_get_attr(fsm, "output_style", _get_attr(fsm, "style", "")),
            initial_state=_get_attr(fsm, "initial_state", ""),
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=fid,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_fsm",
        )

        for state in _get_attr(fsm, "states", []):
            state_name = str(state)
            sid = _node_id(f"state:{fsm_name}", state_name)

            _add_node_once(
                graph,
                node_id=sid,
                node_type=NodeType.FSM_STATE,
                name=state_name,
                fsm=fsm_name,
            )

            _add_edge(
                graph,
                src=fid,
                dst=sid,
                edge_type=EdgeType.CONTAINS,
                relation="fsm_has_state",
            )

        for tr in _get_attr(fsm, "transitions", []):
            src_state = _get_attr(tr, "from", "")
            dst_state = _get_attr(tr, "to", "")
            condition = _get_attr(tr, "condition", "")

            if not src_state or not dst_state:
                continue

            src_id = _node_id(f"state:{fsm_name}", src_state)
            dst_id = _node_id(f"state:{fsm_name}", dst_state)

            _add_edge(
                graph,
                src=src_id,
                dst=dst_id,
                edge_type=EdgeType.TRANSITIONS_TO,
                condition=condition,
                relation="fsm_transition",
            )

    # -----------------------------------------------------------------
    # Datapath Elements
    # -----------------------------------------------------------------

    for dp in _get_attr(plan, "datapath", []):
        dp_name = _get_attr(dp, "name", "")
        if not dp_name:
            continue

        did = _node_id("datapath", dp_name)

        _add_node_once(
            graph,
            node_id=did,
            node_type=NodeType.DATAPATH,
            name=dp_name,
            datapath_type=_get_attr(dp, "type", ""),
            width=_get_attr(dp, "width", ""),
            latency_cycles=_get_attr(dp, "latency_cycles", 0),
            update_condition=_get_attr(dp, "update_condition", ""),
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=did,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_datapath",
        )

        for inp in _get_attr(dp, "inputs", []):
            src = _node_id("signal", inp)
            _add_edge(
                graph,
                src=src,
                dst=did,
                edge_type=EdgeType.READS,
                relation="datapath_reads_input",
            )

        for out in _get_attr(dp, "outputs", []):
            dst = _node_id("signal", out)
            _add_edge(
                graph,
                src=did,
                dst=dst,
                edge_type=EdgeType.DRIVES,
                relation="datapath_drives_output",
            )

    # -----------------------------------------------------------------
    # Timing Requirements
    # -----------------------------------------------------------------

    for timing in _get_attr(plan, "timing", []):
        timing_name = _get_attr(
            timing,
            "name",
            _get_attr(timing, "signal_or_behavior", "timing_requirement"),
        )

        tid = _node_id("timing", timing_name)

        _add_node_once(
            graph,
            node_id=tid,
            node_type=NodeType.CONSTRAINT,
            name=timing_name,
            description=_get_attr(timing, "description", _get_attr(timing, "requirement", "")),
            latency_cycles=_get_attr(timing, "latency_cycles", 0),
            source=_get_attr(timing, "source", ""),
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=tid,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_timing_constraint",
        )

    # -----------------------------------------------------------------
    # Constraints
    # -----------------------------------------------------------------

    for constraint in _get_attr(plan, "constraints", []):
        cname = _get_attr(constraint, "type", _get_attr(constraint, "name", "constraint"))
        desc = _get_attr(constraint, "description", str(constraint))

        cid = _node_id("constraint", cname)

        _add_node_once(
            graph,
            node_id=cid,
            node_type=NodeType.CONSTRAINT,
            name=cname,
            description=desc,
            source=_get_attr(constraint, "source", ""),
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=cid,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_constraint",
        )

    # -----------------------------------------------------------------
    # Reset Policy
    # -----------------------------------------------------------------

    reset_policy = _get_attr(plan, "reset_policy", None)

    if reset_policy:
        style = _get_attr(reset_policy, "style", reset_policy if isinstance(reset_policy, str) else "")
        polarity = _get_attr(reset_policy, "polarity", "")
        reset_values = _get_attr(reset_policy, "reset_values", {})

        rid = _node_id("reset_policy", f"{style}_{polarity}")

        _add_node_once(
            graph,
            node_id=rid,
            node_type=NodeType.RESET,
            name="reset_policy",
            style=style,
            polarity=polarity,
            reset_values=reset_values,
        )

        _add_edge(
            graph,
            src=_node_id("plan", plan_id),
            dst=rid,
            edge_type=EdgeType.CONTAINS,
            relation="plan_has_reset_policy",
        )

        if isinstance(reset_values, dict):
            for signal_name, value in reset_values.items():
                sid = _node_id("signal", signal_name)
                _add_edge(
                    graph,
                    src=rid,
                    dst=sid,
                    edge_type=EdgeType.RESETS,
                    reset_value=value,
                    relation="reset_assigns_signal",
                )

    return graph


# ---------------------------------------------------------------------
# Graph Validation
# ---------------------------------------------------------------------


def validate_knowledge_graph(graph: KnowledgeGraph) -> List[str]:
    """
    Lightweight validation for graph consistency.

    This is not full formal verification. It catches missing or suspicious
    structural information before clustering/merge.
    """

    issues: List[str] = []

    node_ids = {node.node_id for node in graph.nodes}

    for edge in graph.edges:
        if edge.src not in node_ids:
            issues.append(f"Edge source does not exist: {edge.src}")
        if edge.dst not in node_ids:
            issues.append(f"Edge destination does not exist: {edge.dst}")

    output_nodes = [
        node for node in graph.nodes
        if node.node_type == NodeType.OUTPUT
    ]

    driven_dsts = {
        edge.dst for edge in graph.edges
        if edge.edge_type == EdgeType.DRIVES
    }

    for output in output_nodes:
        if output.node_id not in driven_dsts:
            issues.append(f"Output has no explicit driver: {output.name}")

    state_nodes = [
        node for node in graph.nodes
        if node.node_type == NodeType.FSM_STATE
    ]

    transition_sources = {
        edge.src for edge in graph.edges
        if edge.edge_type == EdgeType.TRANSITIONS_TO
    }

    transition_dsts = {
        edge.dst for edge in graph.edges
        if edge.edge_type == EdgeType.TRANSITIONS_TO
    }

    for state in state_nodes:
        if state.node_id not in transition_sources and state.node_id not in transition_dsts:
            issues.append(f"FSM state has no transition relation: {state.name}")

    return issues


# ---------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------


def graph_to_adjacency(graph: KnowledgeGraph) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convert graph into adjacency-list representation.

    Useful for debugging, JSON export, and reproducibility artifacts.
    """

    adjacency: Dict[str, List[Dict[str, Any]]] = {}

    for node in graph.nodes:
        adjacency[node.node_id] = []

    for edge in graph.edges:
        adjacency.setdefault(edge.src, []).append(
            {
                "dst": edge.dst,
                "edge_type": _safe_str(edge.edge_type),
                "attributes": getattr(edge, "attributes", {}),
            }
        )

    return adjacency
