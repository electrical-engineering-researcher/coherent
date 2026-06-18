# T7: Same-cycle accumulation

**Category:** Timing model

**Targeted reasoning challenge:** Use variable-based next value logic to avoid delta-cycle semantic errors.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t7_same_cycle_accumulation.vhd`.
