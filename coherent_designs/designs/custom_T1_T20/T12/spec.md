# T12: 8-cycle right-shift delay line

**Category:** Timing model

**Targeted reasoning challenge:** Exact pipeline depth and simultaneous taps.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t12_8_cycle_right_shift_delay_line.vhd`.
