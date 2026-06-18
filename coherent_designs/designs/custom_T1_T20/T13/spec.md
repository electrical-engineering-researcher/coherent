# T13: Multi-bit bus synchronizer

**Category:** Hierarchy / CDC

**Targeted reasoning challenge:** Avoid unsafe bitwise sync; use valid-strobe based transfer.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t13_multi_bit_bus_synchronizer.vhd`.
