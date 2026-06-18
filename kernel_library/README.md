# COHERENT Kernel Library

This folder contains the COHERENT S2 retrieval library scaffold.

## Structure

```text
kernel_library/
├── hdl/                         # one VHDL file per kernel
├── metadata/
│   └── kernels.json             # 157-row kernel metadata table
├── docs/
│   └── provenance_and_contamination.md
├── checks/
│   └── contamination_check.py
└── scripts/
    └── generate_kernel_metadata.py
```

## Generate the full 157-kernel metadata table

```bash
python kernel_library/scripts/generate_kernel_metadata.py
```

## Important

The generated files are a clean release scaffold. Mark `syntax_pass`, `simulation_pass`, and `synthesis_pass` as `true` only after your actual GHDL/VCS/DC flow passes.
