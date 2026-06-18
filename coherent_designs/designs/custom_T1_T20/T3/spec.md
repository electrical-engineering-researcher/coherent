# T3: 2-stage pipelined multiplier

**Category:** Constraints

**Targeted reasoning challenge:** Interpret 100 MHz timing, generate XDC, and show visible pipelining.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t3_2_stage_pipelined_multiplier.vhd`.
