"""Error-mitigation methods, implemented from scratch so each step is inspectable.

1. readout mitigation  - undo measurement errors with per-qubit confusion matrices
2. ZNE                 - zero-noise extrapolation by global unitary folding
Both can be combined. All functions work on plain numbers and counts.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit

# ---------------------------------------------------------------- folding


def fold_global(isa: QuantumCircuit, factor: int) -> QuantumCircuit:
    """Return circuit with noise scaled ~`factor` times (odd integers 1, 3, 5...).

    Works on an already-transpiled circuit: body -> body (body^-1 body)^k, with the
    final measurements kept at the end. Folding is done AFTER transpiling so the
    compiler cannot cancel the extra gates.
    """
    if factor < 1 or factor % 2 == 0:
        raise ValueError("fold factor must be an odd integer >= 1")
    if factor == 1:
        return isa.copy()

    body = isa.copy_empty_like()
    tail = []
    for inst in isa.data:
        if inst.operation.name == "measure":
            tail.append(inst)
        else:
            body.append(inst.operation, inst.qubits, inst.clbits)
    inv = body.inverse()

    out = isa.copy_empty_like()
    out.compose(body, inplace=True)
    for _ in range((factor - 1) // 2):
        out.barrier()
        out.compose(inv, inplace=True)
        out.barrier()
        out.compose(body, inplace=True)
    for inst in tail:
        out.append(inst.operation, inst.qubits, inst.clbits)
    return out


def zne_extrapolate(factors: list[int], values: list[float]) -> float:
    """Linear extrapolation of the score to zero noise, clipped to [0, 1]."""
    if len(factors) != len(values):
        raise ValueError("factors and values must have equal length")
    if len(factors) == 1:
        return float(values[0])
    slope, intercept = np.polyfit(np.asarray(factors, float), np.asarray(values, float), 1)
    return float(min(1.0, max(0.0, intercept)))


# ---------------------------------------------------------------- readout


def confusion_matrix(p_flip_0to1: float, p_flip_1to0: float) -> np.ndarray:
    """Column j = true state j, row i = measured state i."""
    return np.array(
        [[1 - p_flip_0to1, p_flip_1to0], [p_flip_0to1, 1 - p_flip_1to0]], dtype=float
    )


def counts_to_probs(counts: dict, n: int) -> np.ndarray:
    """Probability vector indexed by integer value of the bitstring (clbit0 = LSB)."""
    p = np.zeros(2**n)
    total = sum(counts.values())
    for k, v in counts.items():
        p[int(k.replace(" ", ""), 2)] += v
    return p / total if total else p


def apply_readout_mitigation(
    probs: np.ndarray, matrices: list[np.ndarray]
) -> np.ndarray:
    """Invert the tensor product of per-qubit confusion matrices.

    matrices[k] describes classical bit k (bit 0 = least significant). Negative
    entries from the inversion are clipped and the vector renormalised.
    """
    n = len(matrices)
    full = np.array([[1.0]])
    for m in matrices:  # build kron with MSB first
        full = np.kron(np.linalg.inv(m), full)
    # kron(inv(m_k), previous) puts bit k as the more significant factor, which
    # matches bit 0 = LSB after the loop (bit 0 ends up rightmost).
    mitigated = full @ probs
    mitigated = np.clip(mitigated, 0, None)
    s = mitigated.sum()
    return mitigated / s if s > 0 else mitigated


def mass_on(probs: np.ndarray, ideal: set[str], n: int) -> float:
    return float(sum(probs[int(b, 2)] for b in ideal))
