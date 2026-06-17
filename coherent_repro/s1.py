"""Stage S1: structured synthesis support utilities."""
from __future__ import annotations

from .checker import S1Checker


def serial_to_parallel_reference_vhdl() -> str:
    return r'''
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity serial_to_parallel is
  port (
    clk          : in  std_logic;
    rst          : in  std_logic;
    serial_in    : in  std_logic;
    parallel_out : out std_logic_vector(7 downto 0);
    valid        : out std_logic
  );
end entity;

architecture rtl of serial_to_parallel is
  signal shift_reg : std_logic_vector(7 downto 0) := (others => '0');
  signal out_reg   : std_logic_vector(7 downto 0) := (others => '0');
  signal bit_count : unsigned(2 downto 0) := (others => '0');
begin
  process(clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        shift_reg <= (others => '0');
        out_reg   <= (others => '0');
        bit_count <= (others => '0');
        valid     <= '0';
      else
        shift_reg <= shift_reg(6 downto 0) & serial_in;
        valid <= '0';
        if bit_count = 7 then
          out_reg <= shift_reg(6 downto 0) & serial_in;
          bit_count <= (others => '0');
          valid <= '1';
        else
          bit_count <= bit_count + 1;
        end if;
      end if;
    end if;
  end process;
  parallel_out <= out_reg;
end architecture;
'''.strip()


__all__ = ["S1Checker", "serial_to_parallel_reference_vhdl"]
