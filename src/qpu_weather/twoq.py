"""Measure 2-qubit gate error ourselves, instead of trusting the vendor's number.

Every 2-qubit gate we use (ecr, cz, cx) is its own inverse, so applying it an even
number of times should change nothing. We start every qubit in |0>, apply the gate
K times on an edge, and see how much of the "both qubits still read 0" probability
survives compared with applying it zero times (which also cancels readout error).
Edges that share no qubit are tested in the same circuit, so a whole chip needs only
a handful of circuits.
"""

from __future__ import annotations

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from . import mitigation as mit
from .runner import CREG

TWO_Q_REPEATS = 20  # even -> identity in theory
TWO_Q_GATES = ("ecr", "cz", "cx")


def edge_gate_map(target):
    """(gate name, {undirected edge: (error, directed qargs to use)}) for the device's 2q gate."""
    for gate in TWO_Q_GATES:
        if gate not in target.operation_names:
            continue
        out: dict[tuple[int, int], tuple[float, tuple[int, int]]] = {}
        for qargs, props in target[gate].items():
            if qargs is None or len(qargs) != 2:
                continue
            err = props.error if props is not None and props.error is not None else 0.05
            key = tuple(sorted(qargs))
            if key not in out or err < out[key][0]:
                out[key] = (err, tuple(qargs))
        return gate, out
    raise RuntimeError("device has no ecr/cz/cx two-qubit gate")


def edge_layers(edges) -> list[list[tuple[int, int]]]:
    """Greedily split edges into layers whose edges share no qubit (tested in parallel)."""
    layers: list[tuple[list, set]] = []
    for e in sorted(edges):
        for members, used in layers:
            if e[0] not in used and e[1] not in used:
                members.append(e)
                used.update(e)
                break
        else:
            layers.append(([e], set(e)))
    return [m for m, _ in layers]


def plus_baseline(n: int) -> QuantumCircuit:
    """H then H (identity) then measure: the zero-gate reference for the |+> tests."""
    qc = QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(n, CREG))
    qc.h(range(n))
    qc.barrier()
    qc.h(range(n))
    qc.measure(range(n), range(n))
    return qc


def layer_circuits(
    n: int, layers, gate: str, directed: dict, repeats: int = TWO_Q_REPEATS, basis: str = "z"
):
    """One circuit per layer: the gate applied `repeats` times on every edge in that layer.

    basis "z": every qubit starts in |0>  (sees bit-flip type errors)
    basis "x": every qubit starts in |+>, and is rotated back before measuring
               (sees phase-flip / dephasing type errors the "z" test cannot see)
    """
    circs = []
    for members in layers:
        qc = QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(n, CREG))
        if basis == "x":
            qc.h(range(n))
            qc.barrier()
        for _ in range(repeats):
            for e in members:
                getattr(qc, gate)(*directed[e])
            qc.barrier()
        if basis == "x":
            qc.h(range(n))
        qc.measure(range(n), range(n))
        circs.append(qc)
    return circs


def p_both_zero(counts: dict, n: int, a: int, b: int) -> float:
    """P(qubit a and qubit b both read 0). Qiskit: classical bit q is at string index n-1-q."""
    total = sum(counts.values())
    hit = 0
    for k, v in counts.items():
        k = k.replace(" ", "")
        if k[n - 1 - a] == "0" and k[n - 1 - b] == "0":
            hit += v
    return hit / total


def p_both_zero_corrected(counts: dict, n: int, a: int, b: int, readout) -> float:
    """P(a and b both truly 0), with readout errors of just these two qubits undone.

    Without this, a "1" misread as "0" makes a decayed state look like it survived.
    `readout` maps qubit -> (p01, p10); without an entry we use the raw probability.
    """
    if a not in readout or b not in readout:
        return p_both_zero(counts, n, a, b)
    pair = np.zeros(4)  # index = bit_a + 2 * bit_b
    total = sum(counts.values())
    for k, v in counts.items():
        k = k.replace(" ", "")
        pair[int(k[n - 1 - a]) + 2 * int(k[n - 1 - b])] += v
    mats = [mit.confusion_matrix(*readout[a]), mit.confusion_matrix(*readout[b])]
    return float(mit.apply_readout_mitigation(pair / total, mats)[0])


def _decay_error(after, base, repeats):
    ratio = float(np.clip(after / base, 1e-6, 1.0)) if base > 0 else 1e-6
    return float(1 - ratio ** (1 / repeats))


def edge_errors_from_counts(
    layers, z_counts, z_base, x_counts, x_base, n, repeats, reported, readout=None
):
    """Per-edge measured error per gate.

    Two decay tests (start in |0>, start in |+>); each only sees some error types, so
    we report the larger of the two. Both are kept in the output for transparency.
    """
    readout = readout or {}
    rows = []
    for members, zc, xc in zip(layers, z_counts, x_counts):
        for a, b in members:
            ez = _decay_error(
                p_both_zero_corrected(zc, n, a, b, readout),
                p_both_zero_corrected(z_base, n, a, b, readout),
                repeats,
            )
            ex = _decay_error(
                p_both_zero_corrected(xc, n, a, b, readout),
                p_both_zero_corrected(x_base, n, a, b, readout),
                repeats,
            )
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "gate_error_2q": max(ez, ex),
                    "gate_error_2q_z": ez,
                    "gate_error_2q_x": ex,
                    "reported_gate_error_2q": reported.get((a, b)),
                }
            )
    return rows
