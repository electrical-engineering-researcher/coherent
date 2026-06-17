# COHERENT Reproducibility Package

This folder contains a reference implementation and reproducibility artifacts for **COHERENT: A Multi-Stage Framework for Hierarchical Reasoning and Kernel-Based Reuse in LLM-Driven VHDL Generation**.

The package is designed to answer reviewer requests for implementation detail, including:

- prompt templates
- candidate-plan representation
- knowledge-graph schema
- clustering and merge procedure
- conflict-resolution rules
- iteration budget
- idea for merging
- kernel retrieval scoring formula and weights
- embedding model
- kernel adaptation
- glue-logic generation method
- checker/tool feedback loop
- diagnostics passed to the LLM


The implementation is modular. Each stage can be run independently or as part of the full `S3 -> S2 -> S1` flow.

## Folder structure

```text
coherent_repro/
├── coherent_repro/              # Python reference implementation
├── configs/                     # Reproducible configuration files
├── docs/                        # Human-readable algorithm specifications
├── examples/                    # Example specs, plans, kernels, and outputs
├── kernel_library/              # Small example kernel metadata library
├── prompts/                     # Prompt templates for S3/S2/S1/repair
├── scripts/                     # CLI scripts for running the flow
├── tests/                       # Lightweight sanity tests
└── README.md
```

## Quick start

```bash
cd coherent_repro
python scripts/run_s3_example.py
python scripts/run_s2_example.py
python scripts/run_checker_example.py
python -m pytest tests
```

The code does not require external LLM API access. LLM calls are represented as prompt templates and structured interfaces so the experimental procedure is reproducible. If `sentence-transformers` is available, the implementation uses `sentence-transformers/all-mpnet-base-v2`. Otherwise it falls back to deterministic TF-IDF hashing for local dry-runs.

## Main configuration

The main reproducibility parameters are in:

```text
configs/coherent_config.yaml
```

Key values:

```yaml
embedding_model: sentence-transformers/all-mpnet-base-v2
embedding_dim: 768
similarity_metric: cosine
clustering:
  method: agglomerative
  linkage: average
  threshold_candidates: [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
retrieval:
  top_k: 5
  weights:
    embedding: 0.60
    tag: 0.25
    interface: 0.15
checker:
  max_repair_iterations: 3
```

## Citation note for manuscript/rebuttal

In the revision, this package can be described as the supplementary reproducibility artifact. It formalizes the S3 candidate plan schema, S3 knowledge graph, S3 clustering and merge logic, S2 retrieval formula, S2 kernel adaptation rules, S2 glue logic generation, and S1 checker/repair loop.
