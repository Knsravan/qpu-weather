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


# ---------------------------------------------------------------- entanglement check
PARITY_PHASES = 4  # quarter-period samples of the parity oscillation


def ghz_parity(n: int, k: int):
    """GHZ, then measure every qubit along the axis at angle phi = k*pi/(2n) in the X-Y plane.

    For a GHZ state the parity of the outcomes oscillates as C*cos(n*phi + offset); C is the
    coherence between |0...0> and |1...1>, which a classical 50/50 mixture does not have.
    Phases k = 0..3 sample that oscillation a quarter period apart.
    """
    qc, _ = ghz(n)
    qc.remove_final_measurements(inplace=True)
    qc = QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(n, CREG)).compose(qc)
    phi = k * np.pi / (2 * n)
    for q in range(n):
        qc.rz(-phi, q)
        qc.h(q)
    qc.measure(range(n), range(n))
    return qc


def parity(probs) -> float:
    """Expectation of (-1)^(number of ones) for a probability vector indexed by bitstring value."""
    return float(sum(p * (-1) ** bin(i).count("1") for i, p in enumerate(probs)))


def ghz_fidelity(population: float, parities, variances=None) -> dict:
    """GHZ state fidelity F = (population + coherence) / 2.

    population = P(0...0) + P(1...1); coherence from four parities a quarter period apart.
    F > 0.5 is the standard witness that all qubits are genuinely entangled.

    Shot noise always makes the squared differences below look larger than they are, so a
    state with no coherence at all would still show a little. Passing the variance of each
    parity estimate removes that bias (an unbiased estimate of coherence squared, floored at 0).
    """
    p0, p1, p2, p3 = parities
    v = list(variances) if variances is not None else [0.0] * 4
    c2 = 0.25 * ((p0 - p2) ** 2 - v[0] - v[2] + (p1 - p3) ** 2 - v[1] - v[3])
    coherence = float(min(1.0, np.sqrt(max(0.0, c2))))
    return {"population": population, "coherence": coherence, "fidelity": (population + coherence) / 2}
