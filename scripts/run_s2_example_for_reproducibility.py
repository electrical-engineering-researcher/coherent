#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coherent_repro.examples import example_kernel_library, serial_to_parallel_candidate_plans
from coherent_repro.s3 import run_s3_from_candidates
from coherent_repro.s2 import build_reuse_plan

s3 = run_s3_from_candidates(serial_to_parallel_candidate_plans())
reuse = build_reuse_plan(s3.merged_plan, example_kernel_library(), top_k=5)
for rank, item in enumerate(reuse.retrieved, start=1):
    print(rank, item.kernel.kernel_id, item.kernel.name, round(item.total, 4), {
        "Simemb": round(item.sim_emb, 4),
        "Simtag": round(item.sim_tag, 4),
        "Simif": round(item.sim_if, 4),
    })
print("Glue logic:")
for g in reuse.glue_logic:
    print(g.name, g.vhdl)
