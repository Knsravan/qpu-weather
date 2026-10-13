"""The daily experiment: check the chip, pick qubits, rank the error-mitigation fixes."""

from __future__ import annotations

import datetime as dt

import numpy as np

from . import mitigation as mit
from .backend import BackendHandle
from .benchmarks import BENCHMARKS
from .calibration import run_calibration, summarize_vs_reported
from .layout import best_chain, chain_cost, edge_errors, naive_chain, reported_qubit_cost
from .runner import run_counts, translate_only, transpile_with_layout

METHODS = ("raw", "readout", "zne", "readout+zne")
FACTORS = (1, 3, 5)
BOOTSTRAP = 200  # resamples for the 95% intervals


def _readout_matrices(cal: dict, chain: list[int]):
    by_q = {q["qubit"]: q for q in cal["qubits"]}
    return [mit.confusion_matrix(by_q[p]["p01"], by_q[p]["p10"]) for p in chain]


def _method_scores(probs_by_factor, ideal: set[str], matrices):
    n = len(matrices)
    raw = [mit.mass_on(p, ideal, n) for p in probs_by_factor]
    ro = [mit.mass_on(mit.apply_readout_mitigation(p, matrices), ideal, n) for p in probs_by_factor]
    f = list(FACTORS)
    # ZNE only means something if added noise lowered the score; otherwise report nothing
    zne_ok = mit.zne_valid(f, raw) and mit.zne_valid(f, ro)
    scores = {
        "raw": raw[0],
        "readout": ro[0],
        "zne": mit.zne_extrapolate(f, raw) if zne_ok else None,
        "readout+zne": mit.zne_extrapolate(f, ro) if zne_ok else None,
    }
    return raw, ro, zne_ok, scores


def score_methods(
    counts_by_factor: dict, ideal: set[str], matrices, n_boot: int = BOOTSTRAP, seed: int = 0
) -> dict:
    """Score one (layout, benchmark) under every mitigation method. 1.0 = perfect.

    `ci95` is a bootstrap interval: resample the shots, recompute every method, and
    keep the middle 95%. It shows shot noise only, not day-to-day drift.
    """
    n = len(matrices)
    probs = [mit.counts_to_probs(counts_by_factor[f], n) for f in FACTORS]
    raw, ro, zne_ok, scores = _method_scores(probs, ideal, matrices)

    rng = np.random.default_rng(seed)
    shots = [sum(counts_by_factor[f].values()) for f in FACTORS]
    samples: dict = {m: [] for m in METHODS}
    for _ in range(n_boot):
        resampled = [rng.multinomial(s, p) / s for s, p in zip(shots, probs)]
        for m, v in _method_scores(resampled, ideal, matrices)[3].items():
            if v is not None:
                samples[m].append(v)
    ci = {
        m: None
        if scores[m] is None or len(samples[m]) < n_boot // 2
        else [float(np.percentile(samples[m], 2.5)), float(np.percentile(samples[m], 97.5))]
        for m in METHODS
    }
    return {
        **scores,
        "raw_by_factor": dict(zip(map(str, FACTORS), raw)),
        "readout_by_factor": dict(zip(map(str, FACTORS), ro)),
        "zne_ok": zne_ok,
        "ci95": ci,
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

    # 2. choose qubit chains: a naive baseline, the vendor's pick, and ours by MEASURED error
    vendor_edges = edge_errors(target)  # vendor-reported
    measured_2q = {
        (min(e["a"], e["b"]), max(e["a"], e["b"])): e["gate_error_2q"]
        for e in cal.get("edges", [])
    }
    edges = {**vendor_edges, **measured_2q}  # prefer what we measured; fall back to vendor value
    q_cost = {q["qubit"]: q["readout_error"] + 3 * q["gate_error_1q"] for q in cal["qubits"]}
    layouts = {
        "naive": naive_chain(edges, chain_len),
        "vendor": best_chain(
            vendor_edges, chain_len, reported_qubit_cost(cal["qubits"]), vendor_edges
        ),
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
    counts_list, job_id = run_counts(handle.backend, circuits, shots, handle.simulated)

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
            m: (
                None
                if raw_err <= 1e-9 or scores[m] is None
                else 100 * (raw_err - (1 - scores[m])) / raw_err
            )
            for m in METHODS
        }
        entry["counts_by_factor"] = {str(f): c for f, c in sorted(g["counts"].items())}
        results.append(entry)

    return {
        "schema": 2,
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
        "ZNE is reported as null when added noise did not lower the score (zne_ok false). "
        "ci95 = bootstrap interval over shots only. GHZ score counts all-0/all-1 outcomes, "
        "so it detects bit flips but not loss of entanglement. "
        "Layout 'vendor' is chosen from IBM's reported numbers only. "
        "Two-qubit gate errors used for chain selection are measured by repeated-gate decay "
        "(includes crosstalk from parallel edges); vendor values are only a fallback.",
    }
