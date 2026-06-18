# T2: Width-mismatch integration

**Category:** Hierarchy

**Targeted reasoning challenge:** Handle 8-bit to 4-bit interface mismatch explicitly without silent truncation.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t2_width_mismatch_integration.vhd`.
