"""Independent per-qubit health check.

We do NOT trust the numbers a vendor publishes. For every qubit we measure:
  * readout error  - prepare |0> and |1>, see how often we read the wrong bit
  * 1-qubit gate error - apply X an even number of times (ideally identity) and
    measure how much the |0> population decays versus a zero-gate baseline
  * 2-qubit gate error - see twoq.py (repeat each 2-qubit gate and watch the decay)
Then we compare against the vendor-reported values from the backend's target.
"""

from __future__ import annotations

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from .backend import BackendHandle
from .runner import CREG, job_info, run_counts, transpile_with_layout
from .twoq import (
    TWO_Q_REPEATS,
    edge_errors_from_counts,
    edge_gate_map,
    edge_layers,
    layer_circuits,
    plus_baseline,
)

X_REPEATS = 100  # even -> identity in theory


def _circuits(n: int):
    def base():
        return QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(n, CREG))

    prep0 = base()
    prep0.measure(range(n), range(n))

    prep1 = base()
    prep1.x(range(n))
    prep1.measure(range(n), range(n))

    xrep = base()
    for _ in range(X_REPEATS):
        xrep.x(range(n))
        xrep.barrier()
    xrep.measure(range(n), range(n))
    return [prep0, prep1, xrep]


def _p_one(counts: dict, n: int) -> np.ndarray:
    """Per-physical-qubit probability of reading 1."""
    ones = np.zeros(n)
    total = sum(counts.values())
    for k, v in counts.items():
        k = k.replace(" ", "")
        for q in range(n):
            if k[n - 1 - q] == "1":
                ones[q] += v
    return ones / total


def _reported(target, n: int):
    """Vendor-reported readout and X-gate errors per qubit (None if unavailable)."""
    ro, g1 = [], []
    for q in range(n):
        try:
            ro.append(target["measure"][(q,)].error)
        except Exception:
            ro.append(None)
        err = None
        for name in ("x", "sx"):
            try:
                err = target[name][(q,)].error
                break
            except Exception:
                continue
        g1.append(err)
    return ro, g1


def run_calibration(handle: BackendHandle, shots: int = 2000) -> dict:
    target = handle.target_backend.target
    n = handle.target_backend.num_qubits
    gate, edge_map = edge_gate_map(target)
    layers = edge_layers(edge_map)
    directed = {e: v[1] for e, v in edge_map.items()}
    circs = transpile_with_layout(
        _circuits(n)
        + [plus_baseline(n)]
        + layer_circuits(n, layers, gate, directed, basis="z")
        + layer_circuits(n, layers, gate, directed, basis="x"),
        handle.target_backend,
        list(range(n)),
        optimization_level=0,
    )
    counts_list, job_id = job_info(run_counts(handle.backend, circs, shots, handle.simulated))
    p1_prep0 = _p_one(counts_list[0], n)  # P(read 1 | prepared 0)
    p1_prep1 = _p_one(counts_list[1], n)  # P(read 1 | prepared 1)
    p0_after_x = 1 - _p_one(counts_list[2], n)  # P(read 0 after X^N)

    p01 = p1_prep0
    p10 = 1 - p1_prep1
    readout_err = (p01 + p10) / 2

    base_surv = 1 - p01  # P(read 0) with zero gates
    ratio = np.clip(p0_after_x / np.where(base_surv > 0, base_surv, 1), 1e-6, 1.0)
    gate_err = 1 - ratio ** (1 / X_REPEATS)

    rep_ro, rep_g1 = _reported(target, n)
    qubits = []
    for q in range(n):
        qubits.append(
            {
                "qubit": q,
                "p01": float(p01[q]),
                "p10": float(p10[q]),
                "readout_error": float(readout_err[q]),
                "gate_error_1q": float(gate_err[q]),
                "reported_readout_error": rep_ro[q],
                "reported_gate_error_1q": rep_g1[q],
            }
        )
    edges = edge_errors_from_counts(
        layers,
        counts_list[4 : 4 + len(layers)],
        counts_list[0],
        counts_list[4 + len(layers) :],
        counts_list[3],
        n,
        TWO_Q_REPEATS,
        {e: v[0] for e, v in edge_map.items()},
        readout={q: (float(p01[q]), float(p10[q])) for q in range(n)},
    )
    return {
        "qubits": qubits,
        "edges": edges,
        "two_q_gate": gate,
        "two_q_repeats": TWO_Q_REPEATS,
        "shots": shots,
        "job_id": job_id,
        "x_repeats": X_REPEATS,
    }


def summarize_vs_reported(cal: dict) -> dict:
    """How far is reality from the vendor's published numbers?"""
    ratios_ro, ratios_g = [], []
    for q in cal["qubits"]:
        r, m = q["reported_readout_error"], q["readout_error"]
        if r and r > 0:
            ratios_ro.append(m / r)
        r, m = q["reported_gate_error_1q"], q["gate_error_1q"]
        if r and r > 0:
            ratios_g.append(m / r)

    def med(x):
        return float(np.median(x)) if x else None

    worst = sorted(
        (q for q in cal["qubits"] if q["reported_readout_error"]),
        key=lambda q: q["readout_error"] / q["reported_readout_error"],
        reverse=True,
    )[:5]
    ratios_2q = [
        e["gate_error_2q"] / e["reported_gate_error_2q"]
        for e in cal.get("edges", [])
        if e["reported_gate_error_2q"]
    ]
    return {
        "median_gate2q_measured_over_reported": med(ratios_2q),
        "median_readout_measured_over_reported": med(ratios_ro),
        "median_gate1q_measured_over_reported": med(ratios_g),
        "worst_readout_qubits": [
            {
                "qubit": q["qubit"],
                "measured": q["readout_error"],
                "reported": q["reported_readout_error"],
            }
            for q in worst
        ],
    }
