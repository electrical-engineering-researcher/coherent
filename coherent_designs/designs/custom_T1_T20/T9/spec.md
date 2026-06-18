# T9: 3-state Moore FSM

**Category:** FSM

**Targeted reasoning challenge:** Safe illegal-state handling and complete next-state specification.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t9_3_state_moore_fsm.vhd`.
