#!/usr/bin/env python3
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coherent_repro.examples import serial_to_parallel_candidate_plans
from coherent_repro.s3 import run_s3_from_candidates

out = run_s3_from_candidates(serial_to_parallel_candidate_plans())
print("Selected threshold:", out.clustering.threshold)
print("Cluster labels:", out.clustering.labels)
print("Dominant cluster:", out.clustering.dominant_cluster_id)
print("Validation passed:", out.validation.passed)
print(out.merged_plan.to_json())
Path("examples/merged_plan_serial_to_parallel.json").write_text(out.merged_plan.to_json())
Path("examples/knowledge_graph_P1.json").write_text(json.dumps(out.graphs[0].to_dict(), indent=2, default=str))
