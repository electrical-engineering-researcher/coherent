# Kernel Library Provenance and Contamination Separation

This document specifies how the 157-kernel library should be documented and separated from evaluation tasks.

## Kernel library categories

The complete kernel library should be released as a metadata table with one row per kernel.

| Category | Count | Examples |
|---|---:|---|
| Manually developed reusable primitives | 62 | counters, shift registers, synchronizers, FIFOs, arbiters, UART TX/RX, FSM templates, clock dividers, datapath operators |
| Benchmark-derived reusable modules | 71 | generalized RTL-LLM modules, OpenCores components, educational RTL examples after removing task-specific logic |
| Manually curated design patterns | 24 | CDC synchronizers, handshake controllers, pipelined arithmetic, resource sharing, protocol adapters |
| Total | 157 | complete retrieval library |

## Metadata fields for every kernel

```json
{
  "kernel_id": "K_COUNTER_001",
  "name": "mod_counter",
  "category": "counter",
  "source_category": "manual_primitive | benchmark_derived | curated_pattern",
  "source_reference": "manual | RTL-LLM | OpenCores | educational-example | other",
  "description": "Parameterized modulo counter with terminal-count pulse.",
  "tags": ["counter", "modulo", "terminal_count"],
  "ports": [],
  "parameters": {},
  "timing": {},
  "constraints": [],
  "verification": {
    "syntax_pass": true,
    "simulation_pass": true,
    "synthesis_pass": true
  },
  "license": "...",
  "excluded_eval_tasks": []
}
```

## Separation rule

The following artifacts must not be used to construct the retrieval library:

1. custom T1-T20 task specifications;
2. custom T1-T20 golden reference implementations;
3. custom T1-T20 generated outputs;
4. custom T1-T20 golden testbenches;
5. any corrected output produced during evaluation.

## Exact-match check

For each evaluation design and each kernel:

1. remove comments and whitespace;
2. normalize identifiers where appropriate;
3. compute SHA-256 hash;
4. flag exact hash matches.

Any exact match between an evaluation reference and a kernel is treated as contamination unless the kernel is removed from that evaluation category.

## Near-duplicate check

Near-duplicate screening uses three signals:

```text
1. token Jaccard similarity
2. normalized edit similarity
3. embedding cosine similarity
```

Suggested thresholds:

```text
token_jaccard >= 0.80
or edit_similarity >= 0.85
or embedding_cosine >= 0.90
```

Flagged pairs are manually inspected. If a kernel is task-specific, it is excluded for that task category.

## Example: modulo counter

A generic modulo-counter kernel may be present in the library. However, the custom T14 Modulo-13 Counter solution is not present. For T14, S2 may retrieve the generic counter and adapt it by changing the modulo parameter and terminal-count logic. This is reuse, not memorization.

## Example: sequence detector

The library may contain generic Moore and Mealy FSM templates. It must not contain the exact T10 sequence-detector implementation or golden solution. For T10, S2 may retrieve an FSM template but the sequence-specific transition logic must be synthesized from the task specification.

## Saturation experiment

To support or weaken the 157-kernel saturation claim, report functional correctness as library size increases:

```text
25 kernels
50 kernels
100 kernels
157 kernels
>157 kernels
```

If correctness plateaus at 157, the saturation claim is supported. If correctness continues to improve, the paper should state only that 157 kernels were used in the implementation, not that it is a saturation point.
