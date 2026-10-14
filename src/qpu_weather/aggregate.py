"""Turn the pile of daily run files into one history file for the dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from .mitigation import zne_valid

LIGHT_KEYS = ("timestamp_utc", "backend", "shots", "chain_len", "layouts", "results",
              "calibration_summary", "benchmark_job_id", "entanglement", "rb")


def _slim_result(res: dict) -> dict:
    """Drop raw counts (kept in data/runs/) and make sure every result says whether ZNE is usable.

    Runs from before schema 2 have no `zne_ok`; we derive it from the stored raw scores
    with the same rule the experiment now applies. Their readout-mitigated scores per
    fold factor were not saved, so only the raw trend can be checked for them.
    """
    out = {k: v for k, v in res.items() if k != "counts_by_factor"}
    s = out.get("scores", {})
    if "zne_ok" not in s and "raw_by_factor" in s:
        rbf = s["raw_by_factor"]
        factors = sorted(rbf, key=int)
        out["scores"] = {**s, "zne_ok": zne_valid([int(f) for f in factors], [rbf[f] for f in factors])}
    return out


def build_history(runs_dir: Path, out_file: Path, include_simulated: bool = False) -> int:
    runs = []
    for f in sorted(runs_dir.glob("*.json")):
        run = json.loads(f.read_text())
        if run.get("simulated") and not include_simulated:
            continue
        slim = {k: run[k] for k in LIGHT_KEYS if k in run}
        slim["simulated"] = bool(run.get("simulated"))
        slim["results"] = [_slim_result(r) for r in run.get("results", [])]
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
