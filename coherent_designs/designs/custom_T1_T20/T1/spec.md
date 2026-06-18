# T1: Structural 4-bit ALU from submodules

**Category:** Hierarchy

**Targeted reasoning challenge:** Preserve entity-component hierarchy, component declarations, and correct port mapping.

## Interface convention
All packaged examples use a common compact VHDL interface (`clk`, `rst`, `en`, `din`, `dout`, `valid`) so they can be compiled in a uniform regression harness. For the paper, the natural-language task text is the evaluated specification; this folder stores the reference design artifact and metadata.

## Expected validation
Compile with GHDL/VCS-equivalent simulator and run `tb_t1_structural_4_bit_alu_from_submodule.vhd`.
