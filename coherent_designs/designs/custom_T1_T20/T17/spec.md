# T17: Serial-to-parallel framing

**Category:** Hierarchy

**Targeted reasoning challenge:** Explicit start-bit, shift direction, and partial-frame behavior.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t17_serial_to_parallel_framing.vhd`.
