"""Turn the pile of daily run files into one history file for the dashboard."""

from __future__ import annotations

import json
from pathlib import Path

LIGHT_KEYS = ("timestamp_utc", "backend", "shots", "chain_len", "layouts", "results",
              "calibration_summary", "benchmark_job_id")


def build_history(runs_dir: Path, out_file: Path, include_simulated: bool = False) -> int:
    runs = []
    for f in sorted(runs_dir.glob("*.json")):
        run = json.loads(f.read_text())
        if run.get("simulated") and not include_simulated:
            continue
        slim = {k: run[k] for k in LIGHT_KEYS if k in run}
        slim["simulated"] = bool(run.get("simulated"))
        # per-qubit table kept compact for the drift charts
        slim["qubits"] = [
            {
                "q": q["qubit"],
                "ro": q["readout_error"],
                "g1": q["gate_error_1q"],
                "ro_rep": q["reported_readout_error"],
                "g1_rep": q["reported_gate_error_1q"],
            }
            for q in run["calibration"]["qubits"]
        ]
        runs.append(slim)
    runs.sort(key=lambda r: r["timestamp_utc"])
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps({"runs": runs}, separators=(",", ":")))
    return len(runs)
