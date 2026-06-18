# T16: Multi-waveform generator

**Category:** Implicit assumptions

**Targeted reasoning challenge:** Consistent triangle/square/saw boundary semantics.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t16_multi_waveform_generator.vhd`.
