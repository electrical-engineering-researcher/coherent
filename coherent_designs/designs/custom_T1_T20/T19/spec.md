# T19: Fast-to-slow pulse capture

**Category:** Timing / CDC

**Targeted reasoning challenge:** No pulse loss through stretching/latching.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t19_fast_to_slow_pulse_capture.vhd`.
