# COHERENT: A Multi-Stage Framework for Hierarchical Reasoning and Kernel-Based Reuse in LLM-Driven VHDL Generation

COHERENT is a multi-stage framework designed to improve the reliability, correctness, and scalability of LLM-driven hardware design generation. Rather than generating HDL directly from a natural language specification in a single pass, COHERENT decomposes the design process into three specialized stages:

* **S3:** Hierarchical Reasoning and Architectural Planning
* **S2:** Kernel Retrieval and Reuse
* **S1:** Structured HDL Synthesis and Verification

The framework is motivated by the observation that hardware design requires reasoning about architecture, timing, interfaces, hierarchy, and reusable design patterns before implementation begins. COHERENT therefore separates conceptual reasoning from implementation and verification, allowing each stage to focus on a distinct aspect of the design process.

---

# Framework Overview

```text
Natural Language Specification
                │
                ▼
      ┌─────────────────┐
      │       S3        │
      │ Architectural   │
      │    Reasoning    │
      └─────────────────┘
                │
                ▼
      ┌─────────────────┐
      │       S2        │
      │ Kernel Reuse &  │
      │   Adaptation    │
      └─────────────────┘
                │
                ▼
      ┌─────────────────┐
      │       S1        │
      │ HDL Synthesis & │
      │    Validation   │
      └─────────────────┘
                │
                ▼
          Final VHDL
```

Each stage operates independently and exchanges structured intermediate representations rather than raw text.

---

# Repository Structure

```text
coherent_repro/
├── coherent_repro/
│   ├── planning.py
│   ├── knowledge_graph.py
│   ├── clustering.py
│   ├── retrieval.py
│   ├── adaptation.py
│   ├── synthesis.py
│   ├── checker.py
│   └── repair.py
│
├── configs/
├── docs/
├── examples/
├── kernel_library/
├── prompts/
├── scripts/
└── tests/
```

---

# Stage S3: Hierarchical Reasoning and Planning

S3 converts a natural language hardware specification into a structured architectural representation.

The goal of S3 is to explore multiple possible implementations before selecting a final design plan.

Instead of generating HDL immediately, S3 identifies:

* Functional blocks
* Datapath elements
* Control logic
* State machines
* Timing requirements
* Interface definitions
* Reset behavior
* Hierarchical module boundaries

## Candidate Plan Generation

Multiple candidate plans are generated independently.

Each candidate contains:

```json
{
  "modules": [],
  "interfaces": [],
  "fsm_states": [],
  "datapath_elements": [],
  "timing_constraints": [],
  "reset_strategy": "",
  "hierarchy": {}
}
```

Each candidate represents a possible interpretation of the specification.

---

## Knowledge Graph Construction

Candidate plans are converted into a hardware knowledge graph.

Node types include:

* Module
* Interface
* FSM State
* Counter
* Register
* Arithmetic Unit
* Memory
* Constraint

Relationship types include:

* contains
* connects_to
* controls
* transitions_to
* depends_on

Example:

```text
Controller
   │
   ├── controls ──► Counter
   │
   └── transitions_to ──► DONE
```

The graph provides a structured representation of design intent that can be compared across candidate solutions.

---

## Embedding Representation

Candidate plans are transformed into textual graph descriptions and embedded using:

```text
sentence-transformers/all-mpnet-base-v2
```

Configuration:

```yaml
embedding_dim: 768
similarity_metric: cosine
```

These embeddings capture semantic similarity between candidate architectures.

---

## Candidate Clustering

Architectural candidates are clustered using agglomerative clustering.

Configuration:

```yaml
method: agglomerative
linkage: average
threshold_candidates:
  - 0.50
  - 0.55
  - 0.60
  - 0.65
  - 0.70
  - 0.75
```

The threshold producing the best cluster separation is selected automatically.

The objective is to identify recurring architectural ideas that appear across multiple independently generated plans.

---

## Consensus Merge

After clustering, COHERENT merges compatible design elements to produce a consensus architecture.

Examples:

### Compatible Merge

```text
Candidate A:
  Counter(8)

Candidate B:
  Counter(8)

Merged:
  Counter(8)
```

### Conflict Example

```text
Candidate A:
  synchronous reset

Candidate B:
  asynchronous reset
```

Conflict resolution prioritizes:

1. Explicit specification requirements
2. Majority agreement across candidates
3. Hardware safety heuristics

The resulting consensus plan becomes the architectural blueprint for downstream synthesis.

---

# Stage S2: Kernel Retrieval and Reuse

S2 enriches the architectural plan with reusable hardware building blocks.

The kernel library contains parameterized HDL patterns such as:

* Counters
* FIFOs
* Shift Registers
* FSM Templates
* Synchronizers
* UART Blocks
* Arithmetic Units
* Protocol Adapters

Each kernel stores metadata including:

```json
{
  "name": "",
  "tags": [],
  "ports": [],
  "parameters": [],
  "description": ""
}
```

---

## Retrieval Scoring

Kernel selection combines semantic similarity, tag overlap, and interface compatibility.

The retrieval score is:

```text
Score =
0.60 × EmbeddingSimilarity
+ 0.25 × TagSimilarity
+ 0.15 × InterfaceCompatibility
```

Configuration:

```yaml
top_k: 5

weights:
  embedding: 0.60
  tag: 0.25
  interface: 0.15
```

The highest-scoring kernels are selected for adaptation.

---

## Kernel Adaptation

Retrieved kernels are transformed to match the target architecture.

Adaptation operations include:

* Bit-width modification
* Port renaming
* Parameter specialization
* Reset conversion
* Clock adaptation
* Signal remapping

Example:

```text
Retrieved Counter:
  WIDTH = 8

Target Design:
  WIDTH = 12

Adapted Kernel:
  WIDTH = 12
```

---

## Glue Logic Generation

When reused kernels do not connect directly, COHERENT automatically synthesizes glue logic.

Examples include:

* Signal width adapters
* Protocol converters
* Control signal translators
* Multiplexers
* Demultiplexers
* Register stages

Example:

```text
Kernel A Output:
  [7:0]

Kernel B Input:
  [15:0]

Glue Logic:
  Zero-extension adapter
```

The adapted kernels and generated glue logic form a reusable implementation skeleton.

---

# Stage S1: Structured HDL Synthesis

S1 converts the architecture and reusable kernels into synthesizable VHDL.

Instead of generating the design in a single pass, S1 follows a structured synthesis workflow.

Steps include:

1. Entity generation
2. Architecture construction
3. Signal declaration
4. FSM synthesis
5. Datapath generation
6. Testbench generation
7. Constraint validation
8. Compilation checks

---

## Verification Pipeline

Generated HDL is validated through automated checking.

Verification stages include:

### Syntax Validation

Checks:

* Parser errors
* Missing declarations
* Type mismatches
* Invalid port mappings

### Structural Validation

Checks:

* Interface consistency
* Hierarchy preservation
* Module connectivity

### Functional Validation

Checks:

* Testbench execution
* Expected outputs
* State transitions
* Timing behavior

---

## Repair Loop

When failures are detected, diagnostics are fed back into a repair module.

Examples:

```text
Signal width mismatch:
expected std_logic_vector(7 downto 0)
found std_logic_vector(3 downto 0)
```

```text
FSM missing transition:
IDLE → ACTIVE
```

Repair prompts receive:

* Original specification
* Current HDL
* Tool diagnostics
* Previous repair history

The model then produces a corrected version.

Configuration:

```yaml
max_repair_iterations: 3
```

---

# Configuration

Main configuration file:

```text
configs/coherent_config.yaml
```

Default settings:

```yaml
embedding_model: sentence-transformers/all-mpnet-base-v2
embedding_dim: 768

similarity_metric: cosine

clustering:
  method: agglomerative
  linkage: average
  threshold_candidates:
    - 0.50
    - 0.55
    - 0.60
    - 0.65
    - 0.70
    - 0.75

retrieval:
  top_k: 5

  weights:
    embedding: 0.60
    tag: 0.25
    interface: 0.15

checker:
  max_repair_iterations: 3
```

---

# Example Workflow

```text
Specification:
"Design an 8-bit UART receiver with parity checking."

S3:
  ├─ Identify FSM
  ├─ Identify shift register
  ├─ Identify parity logic
  └─ Build architecture plan

S2:
  ├─ Retrieve UART FSM kernel
  ├─ Retrieve shift-register kernel
  ├─ Retrieve parity-check kernel
  └─ Generate adapters

S1:
  ├─ Generate VHDL
  ├─ Generate testbench
  ├─ Run validation
  ├─ Repair failures
  └─ Produce final design
```

---

# Key Design Principles

COHERENT is built around four principles:

1. **Reason before synthesis** by explicitly constructing architectural plans.
2. **Reuse before regeneration** by leveraging validated hardware kernels.
3. **Structure before implementation** through hierarchical intermediate representations.
4. **Verify before acceptance** using automated checking and repair.

These stages make sure of more reliable HDL generation while preserving architectural intent, design hierarchy, and hardware-specific correctness requirements.
