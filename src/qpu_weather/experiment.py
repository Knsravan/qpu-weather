"""The daily experiment: check the chip, pick qubits, rank the error-mitigation fixes."""

from __future__ import annotations

import datetime as dt

import numpy as np

from . import mitigation as mit
from .backend import BackendHandle
from .benchmarks import BENCHMARKS
from .calibration import run_calibration, summarize_vs_reported
from .layout import best_chain, chain_cost, edge_errors, naive_chain
from .runner import job_info, run_counts, translate_only, transpile_with_layout

METHODS = ("raw", "readout", "zne", "readout+zne")
FACTORS = (1, 3, 5)


def _readout_matrices(cal: dict, chain: list[int]):
    by_q = {q["qubit"]: q for q in cal["qubits"]}
    return [mit.confusion_matrix(by_q[p]["p01"], by_q[p]["p10"]) for p in chain]


def score_methods(counts_by_factor: dict, ideal: set[str], matrices) -> dict:
    """Score one (layout, benchmark) under every mitigation method. 1.0 = perfect."""
    n = len(matrices)
    raw, ro = [], []
    for f in FACTORS:
        counts = counts_by_factor[f]
        probs = mit.counts_to_probs(counts, n)
        raw.append(mit.mass_on(probs, ideal, n))
        ro.append(mit.mass_on(mit.apply_readout_mitigation(probs, matrices), ideal, n))
    return {
        "raw": raw[0],
        "readout": ro[0],
        "zne": mit.zne_extrapolate(list(FACTORS), raw),
        "readout+zne": mit.zne_extrapolate(list(FACTORS), ro),
        "raw_by_factor": dict(zip(map(str, FACTORS), raw)),
    }


def run_experiment(
    handle: BackendHandle,
    shots: int = 4000,
    cal_shots: int = 2000,
    chain_len: int = 5,
    benchmarks: tuple[str, ...] = ("ghz", "mirror"),
) -> dict:
    started = dt.datetime.now(dt.timezone.utc)
    target = handle.target_backend.target

    # 1. independent health check of every qubit
    cal = run_calibration(handle, cal_shots)
    summary = summarize_vs_reported(cal)

    # 2. choose qubit chains: a naive baseline vs the healthiest by MEASURED error
    edges = edge_errors(target)  # vendor-reported
    measured_2q = {
        (min(e["a"], e["b"]), max(e["a"], e["b"])): e["gate_error_2q"]
        for e in cal.get("edges", [])
    }
    edges = {**edges, **measured_2q}  # prefer what we measured; fall back to vendor value
    q_cost = {q["qubit"]: q["readout_error"] + 3 * q["gate_error_1q"] for q in cal["qubits"]}
    layouts = {
        "naive": naive_chain(edges, chain_len),
        "best": best_chain(edges, chain_len, q_cost, edges),
    }

    # 3. build all benchmark circuits (transpile first, fold afterwards), run in ONE job
    plan = []  # (layout_name, bench_name, factor, ideal)
    circuits = []
    for lname, chain in layouts.items():
        for bname in benchmarks:
            qc, ideal = BENCHMARKS[bname](chain_len)
            isa = transpile_with_layout(qc, handle.target_backend, chain, optimization_level=1)
            for f in FACTORS:
                circuits.append(translate_only(mit.fold_global(isa, f), handle.target_backend))
                plan.append((lname, bname, f, ideal))
    counts_list, job_id = job_info(run_counts(handle.backend, circuits, shots, handle.simulated))

    # 4. score every method
    grouped: dict = {}
    for (lname, bname, f, ideal), counts in zip(plan, counts_list):
        grouped.setdefault((lname, bname), {"ideal": ideal, "counts": {}})["counts"][f] = counts
    results = []
    for (lname, bname), g in grouped.items():
        scores = score_methods(g["counts"], g["ideal"], _readout_matrices(cal, layouts[lname]))
        raw_err = 1 - scores["raw"]
        entry = {"layout": lname, "benchmark": bname, "chain": layouts[lname], "scores": scores}
        entry["improvement_vs_raw_pct"] = {
            m: (None if raw_err <= 1e-9 else 100 * (raw_err - (1 - scores[m])) / raw_err)
            for m in METHODS
        }
        results.append(entry)

    return {
        "schema": 1,
        "timestamp_utc": started.isoformat(timespec="seconds"),
        "backend": handle.name,
        "simulated": handle.simulated,
        "shots": shots,
        "chain_len": chain_len,
        "calibration": cal,
        "calibration_summary": summary,
        "layouts": {
            k: {"chain": v, "cost": chain_cost(v, q_cost, edges)} for k, v in layouts.items()
        },
        "results": results,
        "benchmark_job_id": job_id,
        "methods": list(METHODS),
        "notes": "Score = probability of the known-correct output (1.0 is perfect). "
        "Two-qubit gate errors used for chain selection are measured by repeated-gate decay "
        "(includes crosstalk from parallel edges); vendor values are only a fallback.",
    }
