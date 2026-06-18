# T18: Parallel-to-serial with handshake

**Category:** Hierarchy

**Targeted reasoning challenge:** Load/busy correctness and safe back-pressure behavior.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t18_parallel_to_serial_with_handshake.vhd`.
