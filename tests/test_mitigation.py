import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from qpu_weather import mitigation as mit


def test_fold_preserves_ideal_unitary():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.s(1)
    for f in (1, 3, 5):
        assert Operator(mit.fold_global(qc, f)).equiv(Operator(qc))


def test_fold_scales_gate_count():
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    base = sum(1 for i in qc.data if i.operation.name not in ("measure", "barrier"))
    for f in (1, 3, 5):
        out = mit.fold_global(qc, f)
        n = sum(1 for i in out.data if i.operation.name not in ("measure", "barrier"))
        assert n == base * f
        assert sum(1 for i in out.data if i.operation.name == "measure") == 2


def test_fold_rejects_even_factor():
    with pytest.raises(ValueError):
        mit.fold_global(QuantumCircuit(1), 2)


def test_zne_exact_on_linear_data():
    # score decays linearly with noise scale: 0.9 - 0.1*(f-1)/... -> intercept at f=0
    factors = [1, 3, 5]
    values = [0.8, 0.6, 0.4]  # slope -0.1, intercept 0.9
    assert mit.zne_extrapolate(factors, values) == pytest.approx(0.9)


def test_zne_clipped_to_unit_interval():
    assert mit.zne_extrapolate([1, 3, 5], [0.99, 0.9, 0.8]) <= 1.0


def test_readout_mitigation_recovers_true_distribution():
    rng = np.random.default_rng(1)
    mats = [mit.confusion_matrix(0.03, 0.08), mit.confusion_matrix(0.02, 0.05),
            mit.confusion_matrix(0.05, 0.1)]
    true = np.zeros(8)
    true[0], true[7] = 0.5, 0.5  # GHZ-like
    full = np.array([[1.0]])
    for m in mats:
        full = np.kron(m, full)
    measured = full @ true
    recovered = mit.apply_readout_mitigation(measured, mats)
    assert recovered == pytest.approx(true, abs=1e-9)


def test_readout_bit_order_is_lsb_first():
    # only bit 0 is noisy. State |bit0=1> (value 1) should leak to value 0, not value 2/4.
    mats = [mit.confusion_matrix(0.0, 0.2), mit.confusion_matrix(0, 0), mit.confusion_matrix(0, 0)]
    full = np.array([[1.0]])
    for m in mats:
        full = np.kron(m, full)
    true = np.zeros(8)
    true[1] = 1.0
    measured = full @ true
    assert measured[1] == pytest.approx(0.8)
    assert measured[0] == pytest.approx(0.2)


def test_counts_to_probs_normalises():
    p = mit.counts_to_probs({"00": 30, "11": 70}, 2)
    assert p.sum() == pytest.approx(1.0)
    assert p[3] == pytest.approx(0.7)
