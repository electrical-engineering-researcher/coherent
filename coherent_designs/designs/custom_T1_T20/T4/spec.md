# T4: Distributed-RAM FIFO

**Category:** Constraints

**Targeted reasoning challenge:** Force LUT/distributed RAM memory style rather than unintended BRAM inference.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t4_distributed_ram_fifo.vhd`.
