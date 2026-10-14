"""Randomized benchmarking, the GHZ entanglement check and the equal-budget comparison."""

import numpy as np
import pytest
from qiskit import transpile
from qiskit_aer import AerSimulator

from qpu_weather import benchmarks as bm
from qpu_weather import mitigation as mit
from qpu_weather import rb
from qpu_weather.experiment import entanglement, score_methods
from qpu_weather.runner import run_counts


def test_fit_decay_recovers_known_rate():
    lengths = [1, 20, 50, 100]
    p_true = 0.995
    surv = [0.45 * p_true**m + 0.5 for m in lengths]
    p, epc = rb.fit_decay(lengths, surv, 2)
    assert p == pytest.approx(p_true, abs=1e-6)
    assert epc == pytest.approx((1 - p_true) / 2, abs=1e-6)


def test_rb_sequences_return_to_zero_on_a_perfect_machine():
    """Every sequence ends with its own inverse, so a noiseless run must always read 0...0."""
    circs, plan = rb.rb_circuits(3, seed=1)
    sim = AerSimulator()
    counts = sim.run(transpile(circs, sim), shots=200, seed_simulator=1).result().get_counts()
    assert all(set(c) == {"000"} for c in counts)
    out = rb.analyse(counts, plan, [10, 11, 12], 1.0, 1.5, {}, {})
    assert all(q["epc"] == pytest.approx(0, abs=1e-9) for q in out["qubits"])
    assert [(e["a"], e["b"]) for e in out["edges"]] == [(10, 11), (11, 12)]


def test_ghz_fidelity_separates_entangled_from_classical_mixture():
    assert bm.ghz_fidelity(1.0, [1, 0, -1, 0])["fidelity"] == pytest.approx(1.0)
    # all-0 / all-1 with no coherence scores 1.0 on population but only 0.5 on fidelity
    assert bm.ghz_fidelity(1.0, [0, 0, 0, 0])["fidelity"] == pytest.approx(0.5)


def test_entanglement_on_ideal_and_mixed_counts():
    perfect = [mit.confusion_matrix(0, 0)] * 3
    ghz = {"000": 500, "111": 500}
    even = {"000": 250, "011": 250, "101": 250, "110": 250}
    odd = {"001": 250, "010": 250, "100": 250, "111": 250}
    flat = {**{k: 125 for k in ["000", "001", "010", "011", "100", "101", "110", "111"]}}
    good = entanglement(ghz, [even, flat, odd, flat], perfect, n_boot=50)
    assert good["raw"]["fidelity"] == pytest.approx(1.0, abs=1e-3) and good["raw"]["entangled"]
    mixed = entanglement(ghz, [flat] * 4, perfect, n_boot=50)
    assert mixed["raw"]["fidelity"] == pytest.approx(0.5) and not mixed["raw"]["entangled"]


def test_ghz_parity_circuits_on_noiseless_sim():
    n, par = 4, []
    for k in range(bm.PARITY_PHASES):
        c = AerSimulator().run(bm.ghz_parity(n, k), shots=4000, seed_simulator=3).result().get_counts()
        par.append(bm.parity(mit.counts_to_probs(c, n)))
    assert bm.ghz_fidelity(1.0, par)["fidelity"] > 0.97


def test_equal_budget_interval_is_wider():
    perfect = [mit.confusion_matrix(0, 0)] * 2
    counts = {1: {"00": 3600, "11": 400}, 3: {"00": 3200, "11": 800}, 5: {"00": 2800, "11": 1200}}
    s = score_methods(counts, {"00"}, perfect, n_boot=100)
    full, eq = s["ci95"]["zne"], s["equal_budget"]["ci95"]["zne"]
    assert s["equal_budget"]["shots_per_factor"] == [1333, 1333, 1333]
    assert (eq[1] - eq[0]) > (full[1] - full[0])


def test_run_counts_accepts_shots_per_circuit():
    qc = bm.ghz(2)[0]
    counts, _ = run_counts(AerSimulator(), [qc, qc], [100, 300], simulated=True)
    assert [sum(c.values()) for c in counts] == [100, 300]
