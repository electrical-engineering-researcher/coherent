# T20: Clock enable versus clock gating

**Category:** Implicit assumptions

**Targeted reasoning challenge:** FPGA-safe CE logic instead of gated clocks.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t20_clock_enable_versus_clock_gating.vhd`.
