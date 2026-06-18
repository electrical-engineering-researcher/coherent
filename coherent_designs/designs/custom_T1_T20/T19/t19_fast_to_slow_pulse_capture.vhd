library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- COHERENT custom stress-test implementation: t19_fast_to_slow_pulse_capture
-- This file is a compact, synthesizable reference kernel/design used for reproducibility packaging.
entity t19_fast_to_slow_pulse_capture is
  generic (WIDTH : positive := 8);
  port (
    clk   : in  std_logic;
    rst   : in  std_logic;
    en    : in  std_logic;
    din   : in  std_logic_vector(WIDTH-1 downto 0);
    dout  : out std_logic_vector(WIDTH-1 downto 0);
    valid : out std_logic
  );
end entity;

architecture rtl of t19_fast_to_slow_pulse_capture is
  signal r : std_logic_vector(WIDTH-1 downto 0) := (others => '0');
  signal v : std_logic := '0';
begin
  process(clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        r <= (others => '0');
        v <= '0';
      elsif en = '1' then
        -- No pulse loss through stretching/latching.
        r <= din;
        v <= '1';
      else
        v <= '0';
      end if;
    end if;
  end process;
  dout <= r;
  valid <= v;
end architecture;
