library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_r29_register_file is end entity;
architecture sim of tb_r29_register_file is
  constant WIDTH : positive := 8;
  signal clk,rst,en,valid : std_logic := '0';
  signal din,dout : std_logic_vector(WIDTH-1 downto 0) := (others=>'0');
begin
  clk <= not clk after 5 ns;
  dut: entity work.r29_register_file generic map(WIDTH=>WIDTH) port map(clk=>clk,rst=>rst,en=>en,din=>din,dout=>dout,valid=>valid);
  process
  begin
    rst <= '1'; wait for 20 ns; rst <= '0'; wait for 10 ns;
    din <= x"A5"; en <= '1'; wait for 10 ns; en <= '0'; wait for 20 ns;
    assert dout = x"A5" report "Mismatch in r29_register_file" severity failure;
    assert valid = '0' or valid = '1' report "Valid not driven" severity failure;
    report "PASS r29_register_file" severity note;
    wait;
  end process;
end architecture;
