# COHERENT Implementation Details for Reproducibility

This document formalizes the implementation details requested by reviewers.

## S3 candidate-plan representation

Each S3 candidate is a structured design object with:

- `modules`: module hierarchy and roles
- `ports`: name, direction, width, type, clock domain
- `signals`: internal signals, producer, consumers
- `fsms`: states, initial state, transitions, output style
- `datapath`: datapath elements
- `timing`: latency/output-event requirements
- `reset_policy`: synchronous/asynchronous/none/unspecified
- `constraints`: explicit design constraints
- `assumptions`: inferred assumptions
- `confidence`: LLM confidence score

The schema is implemented in `coherent_repro/schemas.py`.

## Knowledge-graph schema

Node types:

```text
PORT, REGISTER, COUNTER, FSM, FSM_STATE, MEMORY, MODULE,
CLOCK, RESET, OUTPUT, CONSTRAINT, DATAPATH, CONTROL
```

Edge types:

```text
DRIVES, READS, UPDATES, RESETS, TRANSITIONS_TO,
DEPENDS_ON, CONNECTS_TO, CONTAINS, CLOCKS, ENABLES
```

Example:

```text
serial_in --drives--> shift_register
bit_counter --drives--> control_fsm
control_fsm --drives--> valid
```

## Clustering procedure

1. Serialize each candidate plan into canonical normalized text.
2. Encode using `sentence-transformers/all-mpnet-base-v2`.
3. Compute pairwise cosine similarity.
4. Run agglomerative clustering with average linkage.
5. Try thresholds `[0.50, 0.55, 0.60, 0.65, 0.70, 0.75]`.
6. Choose the threshold with the best silhouette score.
7. Select the dominant cluster by largest cluster size, breaking ties by mean confidence.

## Merge procedure

The merged plan retains decisions from the dominant cluster. Common modules, ports, signals, FSMs, datapath components, timing constraints, and reset policy are merged by name and consistency.

Conflicts are resolved in this order:

1. explicit specification
2. interface consistency
3. timing consistency
4. reset policy
5. hardware-safety default
6. majority vote

## Conflict-resolution rules

| Conflict | Rule |
|---|---|
| Sync vs async reset | Use explicit spec; if unspecified, prefer synchronous reset. |
| Moore vs Mealy FSM | Use output timing. Immediate output means Mealy; registered output means Moore. |
| Registered vs combinational output | Use timing requirement. For N-cycle output, register terminal event. |
| Counter terminal count | Use smallest width satisfying terminal count and explicit wrap logic. |
| CDC ambiguity | Use validated synchronizer/handshake kernel. Do not bitwise-sync multi-bit buses. |
| Width mismatch | Use adapter. Zero-extend if safe; truncate only if explicit. |

## Merged-plan validation criteria

A merged plan passes validation if:

1. every output has a producer;
2. every internal signal has a producer unless explicitly external/constant;
3. FSM initial state is declared;
4. FSM states are reachable or explicitly marked unreachable/safe;
5. stateful elements have reset behavior;
6. port widths are positive and consistent;
7. clock/reset domains are identified for sequential elements;
8. no required module is dangling.

## S2 kernel retrieval formula

```text
Score(k) = 0.60 * Simemb + 0.25 * Simtag + 0.15 * Simif
```

Where:

```text
Simemb = cosine(query_embedding, kernel_embedding)
Simtag = |query_tags ∩ kernel_tags| / max(|query_tags|, |kernel_tags|)
Simif = 0.30 * port_name + 0.25 * width + 0.20 * direction
      + 0.15 * clock_reset + 0.10 * parameter
```

Top-k value: `k = 5`.

Embedding model: `sentence-transformers/all-mpnet-base-v2`, 768 dimensions, L2-normalized, cosine similarity.

## Kernel adaptation

Retrieved kernels are adapted using:

1. parameter substitution;
2. bit-width scaling;
3. port renaming;
4. signal type alignment;
5. interface normalization;
6. terminal-count logic modification for counters;
7. safe default transition insertion for FSMs.

## Glue-logic generation

Glue logic is minimal and only generated for explicit mismatches:

- width adapters;
- zero-extension;
- explicit truncation only if allowed;
- enable/status wiring;
- ready/valid handshake adapters;
- CDC adapters only when a validated CDC kernel exists.

## S1 checker/tool feedback loop

For each generated VHDL design:

1. static structural check;
2. compile using GHDL;
3. generate/run testbench;
4. check functional behavior;
5. check structural properties;
6. pass diagnostics to repair prompt;
7. repair only affected module;
8. repeat for at most 3 iterations.

If the design fails after 3 repair attempts, it is classified as unsuccessful and excluded from synthesis/PPA.

## Diagnostics passed to LLM

Diagnostics are passed as structured JSON:

```json
{
  "error_type": "width_mismatch",
  "tool": "ghdl",
  "message": "formal port width does not match actual signal width",
  "module": "counter",
  "line": 73,
  "expected": "8 bits",
  "observed": "4 bits",
  "time": null,
  "raw_log": "..."
}
```
