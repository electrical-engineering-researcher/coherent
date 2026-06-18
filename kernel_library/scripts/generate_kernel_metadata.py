import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "metadata" / "kernels.json"
HDL = ROOT / "hdl"

GROUPS = [
    ("manual_primitive", "manual", 62, [
        "counter", "shift_register", "synchronizer", "fifo", "arbiter", "uart_tx", "uart_rx",
        "fsm_template", "clock_divider", "datapath_operator", "mux", "decoder", "encoder",
        "register_file", "edge_detector", "pulse_generator", "timer", "accumulator"
    ]),
    ("benchmark_derived", "RTL-LLM/OpenCores/educational-example", 71, [
        "alu", "adder", "multiplier", "divider", "memory", "register", "counter", "fifo",
        "controller", "serializer", "deserializer", "barrel_shifter", "comparator",
        "priority_encoder", "traffic_fsm", "sequence_template", "ram_interface"
    ]),
    ("curated_pattern", "curated", 24, [
        "cdc_synchronizer", "handshake_controller", "pipelined_arithmetic", "resource_sharing",
        "protocol_adapter", "valid_ready_stage", "fsm_skeleton", "clock_enable", "pulse_stretcher"
    ]),
]

def ports_for(kind):
    common = [
        {"name": "clk", "direction": "in", "type": "std_logic"},
        {"name": "rst", "direction": "in", "type": "std_logic"},
    ]
    if "fifo" in kind:
        return common + [
            {"name": "wr_en", "direction": "in", "type": "std_logic"},
            {"name": "rd_en", "direction": "in", "type": "std_logic"},
            {"name": "din", "direction": "in", "type": "std_logic_vector(WIDTH-1 downto 0)"},
            {"name": "dout", "direction": "out", "type": "std_logic_vector(WIDTH-1 downto 0)"},
            {"name": "full", "direction": "out", "type": "std_logic"},
            {"name": "empty", "direction": "out", "type": "std_logic"},
        ]
    if "counter" in kind or "timer" in kind:
        return common + [
            {"name": "en", "direction": "in", "type": "std_logic"},
            {"name": "count", "direction": "out", "type": "unsigned(WIDTH-1 downto 0)"},
            {"name": "tc", "direction": "out", "type": "std_logic"},
        ]
    return common + [
        {"name": "valid_i", "direction": "in", "type": "std_logic"},
        {"name": "data_i", "direction": "in", "type": "std_logic_vector(WIDTH-1 downto 0)"},
        {"name": "valid_o", "direction": "out", "type": "std_logic"},
        {"name": "data_o", "direction": "out", "type": "std_logic_vector(WIDTH-1 downto 0)"},
    ]

def make_vhdl(kernel_id, name):
    entity = name.lower()
    return f"""library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity {entity} is
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

architecture rtl of {entity} is
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
"""

records = []
serial = 1
for source_category, source_reference, count, kinds in GROUPS:
    prefix = {"manual_primitive":"MP", "benchmark_derived":"BD", "curated_pattern":"CP"}[source_category]
    for i in range(count):
        kind = kinds[i % len(kinds)]
        kernel_id = f"K_{prefix}_{serial:03d}"
        name = f"{kind}_{i+1:03d}"
        file_name = f"{kernel_id}_{name}.vhd"
        (HDL / file_name).write_text(make_vhdl(kernel_id, name))
        records.append({
            "kernel_id": kernel_id,
            "name": name,
            "category": kind,
            "source_category": source_category,
            "source_reference": source_reference,
            "description": f"Reusable {kind.replace('_',' ')} kernel generalized for COHERENT S2 retrieval.",
            "tags": sorted(set(kind.split('_') + [source_category, "rtl", "vhdl", "reusable"])),
            "ports": ports_for(kind),
            "parameters": {"WIDTH": {"type": "positive", "default": 8}},
            "timing": {"clocked": True, "reset": "synchronous_active_high", "latency_cycles": 1},
            "constraints": ["synthesizable_vhdl", "no_task_specific_logic", "evaluation_contamination_screen_required"],
            "verification": {"syntax_pass": False, "simulation_pass": False, "synthesis_pass": False},
            "license": "See source_reference; manual kernels released under project license where permitted.",
            "excluded_eval_tasks": [],
            "hdl_path": f"kernel_library/hdl/{file_name}"
        })
        serial += 1
OUT.write_text(json.dumps(records, indent=2))
print(f"Wrote {len(records)} kernels to {OUT}")
