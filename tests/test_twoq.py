import pytest
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeLagosV2

from qpu_weather.twoq import (
    edge_errors_from_counts,
    edge_gate_map,
    edge_layers,
    layer_circuits,
    p_both_zero,
)


def test_layers_have_no_shared_qubits_and_cover_all_edges():
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (1, 3)]
    layers = edge_layers(edges)
    assert sorted(e for l in layers for e in l) == sorted(edges)
    for members in layers:
        qs = [q for e in members for q in e]
        assert len(qs) == len(set(qs))


def test_p_both_zero_uses_qiskit_bit_order():
    # "0010": classical bit 1 is set (rightmost char is bit 0)
    assert p_both_zero({"0010": 10}, 4, 0, 2) == 1.0
    assert p_both_zero({"0010": 10}, 4, 0, 1) == 0.0


def test_repeating_gate_is_identity_when_noiseless():
    """The premise: an even number of 2q gates leaves |00> alone."""
    target = FakeLagosV2().target
    gate, edge_map = edge_gate_map(target)
    layers = edge_layers(edge_map)
    directed = {e: v[1] for e, v in edge_map.items()}
    n = 7
    circs = layer_circuits(n, layers, gate, directed, repeats=6)
    from qiskit import transpile

    sim = AerSimulator()
    for qc in circs:
        counts = sim.run(transpile(qc, sim), shots=500).result().get_counts()
        assert counts.get("0" * n) == 500


def test_error_is_zero_without_decay_and_positive_with_decay():
    layers = [[(0, 1)]]
    base = {"00": 1000}
    ok = [{"00": 1000}]
    none = edge_errors_from_counts(layers, ok, base, ok, base, 2, 20, {})[0]
    assert none["gate_error_2q"] < 1e-9
    bad = [{"00": 800, "11": 200}]
    decayed = edge_errors_from_counts(layers, bad, base, ok, base, 2, 20, {(0, 1): 0.01})[0]
    assert 0.005 < decayed["gate_error_2q"] < 0.02  # 1 - 0.8**(1/20) ~ 0.011
    assert decayed["gate_error_2q_x"] < 1e-9  # only the |0> test saw it; max() keeps it


def test_x_basis_circuit_is_identity_when_noiseless():
    from qiskit import transpile

    target = FakeLagosV2().target
    gate, edge_map = edge_gate_map(target)
    layers = edge_layers(edge_map)
    directed = {e: v[1] for e, v in edge_map.items()}
    sim = AerSimulator()
    for qc in layer_circuits(7, layers, gate, directed, repeats=6, basis="x"):
        counts = sim.run(transpile(qc, sim), shots=500).result().get_counts()
        assert counts.get("0" * 7) == 500


def test_readout_correction_removes_misread_ones():
    from qpu_weather.twoq import p_both_zero_corrected

    # truth: both qubits are 0. Qubit 0 reads a true 0 as 1 with prob 0.2.
    counts = {"00": 800, "01": 200}  # string "01": qubit0 = 1
    raw = p_both_zero(counts, 2, 0, 1)
    fixed = p_both_zero_corrected(counts, 2, 0, 1, {0: (0.2, 0.0), 1: (0.0, 0.0)})
    assert raw == 0.8 and fixed == pytest.approx(1.0)
