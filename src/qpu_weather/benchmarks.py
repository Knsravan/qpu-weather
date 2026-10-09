"""Benchmark circuits whose correct answer is known in advance.

Each benchmark returns a circuit measured into a classical register named "c"
(classical bit k <- logical qubit k) plus the set of ideal output bitstrings.
Score = probability mass on the ideal outputs (1.0 is perfect).
"""

from __future__ import annotations

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from .runner import CREG


def _new(n: int) -> QuantumCircuit:
    return QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(n, CREG))


def ghz(n: int):
    """GHZ state: ideal outcomes are all-0 and all-1, each 50%."""
    qc = _new(n)
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    qc.barrier()
    qc.measure(range(n), range(n))
    return qc, {"0" * n, "1" * n}


def mirror(n: int, layers: int = 3, seed: int = 0):
    """Mirror circuit: random Clifford layers followed by their exact inverse.

    The ideal output is all zeros by construction, so no simulation is needed to
    know the right answer. A barrier in the middle stops the compiler from simply
    cancelling the circuit against its inverse.
    """
    rng = np.random.default_rng(seed)
    qc = _new(n)
    for _ in range(layers):
        for q in range(n):
            g = rng.integers(0, 4)
            if g == 0:
                qc.h(q)
            elif g == 1:
                qc.s(q)
            elif g == 2:
                qc.sx(q)
            else:
                qc.x(q)
        start = int(rng.integers(0, 2))
        for q in range(start, n - 1, 2):
            qc.cx(q, q + 1)
    body = qc.copy()
    qc.barrier()
    qc.compose(body.inverse(), inplace=True)
    qc.barrier()
    qc.measure(range(n), range(n))
    return qc, {"0" * n}


BENCHMARKS = {
    "ghz": lambda n: ghz(n),
    "mirror": lambda n: mirror(n, layers=3, seed=11),
}


def score_counts(counts: dict, ideal: set[str]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return sum(v for k, v in counts.items() if k.replace(" ", "") in ideal) / total
