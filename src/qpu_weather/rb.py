"""Randomized benchmarking (RB) on the chosen chains: the standard way to measure gate error.

Our decay tests (calibration.py, twoq.py) are quick but include readout, idle decay and
crosstalk. RB [Knill 2008; Magesan 2011] is what vendors use. Each sequence applies m random
Clifford operations and then the single Clifford that undoes them all, so a perfect device
always returns to |0...0>. The probability of getting back, averaged over random sequences,
falls as A*p^m + B. The decay rate p gives the error per Clifford, and readout errors only
change A and B, not p, which is why RB is not fooled by misreads.

Run simultaneously on the qubits and couplings of a chain, so it includes crosstalk from
neighbours doing the same, as a real circuit on that chain would.
"""

from __future__ import annotations

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.quantum_info import Clifford, random_clifford

from .runner import CREG

LENGTHS_1Q = (1, 20, 50, 100)
LENGTHS_2Q = (1, 4, 8, 16)
SEQUENCES = 4  # random sequences per length
RB_SHOTS = 500
TWO_Q_GATES = ("cz", "ecr", "cx")
ONE_Q_PULSES = ("sx", "x")  # rz is a free frame change on IBM hardware


def _append_sequence(qc: QuantumCircuit, qubits: list[int], length: int, rng) -> None:
    """m random Cliffords on `qubits`, each fenced by a barrier, then their inverse."""
    nq = len(qubits)
    total = Clifford(QuantumCircuit(nq))
    for _ in range(length):
        c = random_clifford(nq, seed=int(rng.integers(2**31)))
        qc.compose(c.to_circuit(), qubits, inplace=True)
        qc.barrier(qubits)
        total = total.compose(c)
    qc.compose(total.adjoint().to_circuit(), qubits, inplace=True)
    qc.barrier(qubits)


def chain_pairs(n: int) -> list[list[tuple[int, int]]]:
    """Neighbouring pairs of a chain of n logical qubits, in two layers that share no qubit."""
    return [[(i, i + 1) for i in range(0, n - 1, 2)], [(i, i + 1) for i in range(1, n - 1, 2)]]


def rb_circuits(n: int, seed: int = 0):
    """Logical RB circuits for a chain of n qubits, plus a description of each.

    One-qubit RB runs on all n qubits at once; two-qubit RB runs in two layers of
    non-overlapping neighbouring pairs.
    """
    rng = np.random.default_rng(seed)
    circs, plan = [], []

    def new():
        return QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(n, CREG))

    for m in LENGTHS_1Q:
        for s in range(SEQUENCES):
            qc = new()
            for q in range(n):
                _append_sequence(qc, [q], m, rng)
            qc.measure(range(n), range(n))
            circs.append(qc)
            plan.append({"kind": "1q", "length": m, "seq": s})
    for li, pairs in enumerate(chain_pairs(n)):
        for m in LENGTHS_2Q:
            for s in range(SEQUENCES):
                qc = new()
                for a, b in pairs:
                    _append_sequence(qc, [a, b], m, rng)
                qc.measure(range(n), range(n))
                circs.append(qc)
                plan.append({"kind": "2q", "layer": li, "length": m, "seq": s})
    return circs, plan


def survival(counts: dict, n: int, qubits: tuple[int, ...]) -> float:
    """Probability that all `qubits` (logical indices) read 0. Clbit q is string index n-1-q."""
    total = sum(counts.values())
    hit = sum(v for k, v in counts.items() if all(k.replace(" ", "")[n - 1 - q] == "0" for q in qubits))
    return hit / total if total else 0.0


def fit_decay(lengths, mean_survival, dim: int):
    """Fit P(m) = A p^m + B with B fixed at 1/dim (the fully mixed value).

    Returns (p, error per Clifford) or (None, None) if the data cannot be fitted.
    Fixing B is the usual simplification when only a few lengths are measured.
    """
    b = 1.0 / dim
    m = np.asarray(lengths, float)
    y = np.asarray(mean_survival, float) - b
    keep = y > 1e-6
    if keep.sum() < 2:
        return None, None
    slope, _ = np.polyfit(m[keep], np.log(y[keep]), 1)
    p = float(min(1.0, np.exp(slope)))
    return p, float((1 - p) * (dim - 1) / dim)


def gate_counts(isa_circuits, plan, chain) -> tuple[float, float]:
    """Average physical 1q pulses per 1q Clifford, and 2q gates per 2q Clifford, as transpiled."""
    one, n1, two, n2 = 0, 0, 0, 0
    for qc, p in zip(isa_circuits, plan):
        ops = qc.count_ops()
        cliffords = p["length"] + 1  # the m random ones plus the inverse
        if p["kind"] == "1q":
            one += sum(ops.get(g, 0) for g in ONE_Q_PULSES)
            n1 += cliffords * len(chain)
        else:
            two += sum(ops.get(g, 0) for g in TWO_Q_GATES)
            n2 += cliffords * len(chain_pairs(len(chain))[p["layer"]])
    return (one / n1 if n1 else None), (two / n2 if n2 else None)


def analyse(counts_list, plan, chain, per_pulse_1q, per_gate_2q, reported_1q, reported_2q):
    """Turn RB counts for one chain into per-qubit and per-coupling error numbers.

    `reported_1q` maps physical qubit -> vendor single-gate error; `reported_2q` maps a sorted
    physical pair -> vendor two-qubit gate error. Per-gate figures divide the error per Clifford
    by the average number of physical gates in a Clifford: a common, approximate conversion.
    """
    n = len(chain)
    qubits, edges = [], []
    for q in range(n):
        means = []
        for m in LENGTHS_1Q:
            vals = [survival(c, n, (q,)) for c, p in zip(counts_list, plan) if p["kind"] == "1q" and p["length"] == m]
            means.append(float(np.mean(vals)))
        p, epc = fit_decay(LENGTHS_1Q, means, 2)
        phys = chain[q]
        qubits.append({
            "qubit": phys, "survival": means, "p": p, "epc": epc,
            "error_per_pulse": (epc / per_pulse_1q) if epc is not None and per_pulse_1q else None,
            "reported": reported_1q.get(phys),
        })
    for li, pairs in enumerate(chain_pairs(n)):
        for a, b in pairs:
            means = []
            for m in LENGTHS_2Q:
                vals = [survival(c, n, (a, b)) for c, p in zip(counts_list, plan)
                        if p["kind"] == "2q" and p["layer"] == li and p["length"] == m]
                means.append(float(np.mean(vals)))
            p, epc = fit_decay(LENGTHS_2Q, means, 4)
            pa, pb = sorted((chain[a], chain[b]))
            edges.append({
                "a": pa, "b": pb, "survival": means, "p": p, "epc": epc,
                "error_per_2q_gate": (epc / per_gate_2q) if epc is not None and per_gate_2q else None,
                "reported": reported_2q.get((pa, pb)),
            })
    return {
        "lengths_1q": list(LENGTHS_1Q), "lengths_2q": list(LENGTHS_2Q), "sequences": SEQUENCES,
        "pulses_per_1q_clifford": per_pulse_1q, "two_q_gates_per_2q_clifford": per_gate_2q,
        "qubits": qubits, "edges": edges,
    }
