# Kernel Library Provenance and Contamination Separation

This manifest documents 157 kernels split exactly as used in the COHERENT paper:

- 62 manually developed reusable primitives
- 71 benchmark-derived reusable modules
- 24 manually curated design patterns

Benchmark-derived entries must be kept separate from evaluation tasks. Do not train, tune, or retrieve from a kernel that is byte-identical to the held-out evaluation target.
