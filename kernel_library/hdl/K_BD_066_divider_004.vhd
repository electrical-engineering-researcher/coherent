library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity divider_004 is
  generic (
    WIDTH : positive := 8
  );
  port (
    clk     : in  std_logic;
    rst     : in  std_logic;
    valid_i : in  std_logic;
    data_i  : in  std_logic_vector(WIDTH-1 downto 0);
    valid_o : out std_logic;
    data_o  : out std_logic_vector(WIDTH-1 downto 0)
  );
end entity;

architecture rtl of divider_004 is
  signal data_r  : std_logic_vector(WIDTH-1 downto 0);
  signal valid_r : std_logic;
begin
  process(clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        data_r  <= (others => '0');
        valid_r <= '0';
      else
        data_r  <= data_i;
        valid_r <= valid_i;
      end if;
    end if;
  end process;

  data_o  <= data_r;
  valid_o <= valid_r;
end architecture;
