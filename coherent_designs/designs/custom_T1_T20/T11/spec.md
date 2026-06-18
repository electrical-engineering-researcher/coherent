# T11: 4-bit Johnson counter

**Category:** Control

**Targeted reasoning challenge:** Preserve twisted-ring feedback semantics.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t11_4_bit_johnson_counter.vhd`.
