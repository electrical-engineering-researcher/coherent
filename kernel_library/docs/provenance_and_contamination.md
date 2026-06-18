# Kernel Library Provenance and Contamination Separation

This document specifies how the 157-kernel library is documented and separated from evaluation tasks.

## Kernel library categories

| Category | Count | Examples |
|---|---:|---|
| Manually developed reusable primitives | 62 | counters, shift registers, synchronizers, FIFOs, arbiters, UART TX/RX, FSM templates, clock dividers, datapath operators |
| Benchmark-derived reusable modules | 71 | generalized RTL-LLM modules, OpenCores components, educational RTL examples after removing task-specific logic |
| Manually curated design patterns | 24 | CDC synchronizers, handshake controllers, pipelined arithmetic, resource sharing, protocol adapters |
| Total | 157 | complete retrieval library |

## Required separation rule

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

## Near-duplicate check
Flag using:
```text
token_jaccard >= 0.80
or edit_similarity >= 0.85
or embedding_cosine >= 0.90
```
Flagged pairs are manually inspected. If a kernel is task-specific, it is excluded for that task category.

## Paper note
The kernel library consists of 157 reusable RTL kernels grouped into three categories. Human-written reusable primitives account for 62 kernels, benchmark-derived reusable modules account for 71 kernels, and curated design patterns account for 24 kernels. All kernels should be validated through compilation, simulation, and synthesis checks before being marked as verified.
