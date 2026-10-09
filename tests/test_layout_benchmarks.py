import json

import pytest
from qiskit_aer import AerSimulator

from qpu_weather import benchmarks as bm
from qpu_weather.aggregate import build_history
from qpu_weather.layout import all_chains, best_chain, chain_cost, naive_chain

LINE = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]


def test_chains_are_connected_simple_paths():
    for ch in all_chains(LINE, 3):
        assert len(set(ch)) == 3
        assert all(tuple(sorted(p)) in LINE for p in zip(ch, ch[1:]))


def test_naive_is_first_by_index():
    assert naive_chain(LINE, 3) == [0, 1, 2]


def test_best_chain_avoids_bad_qubit():
    qcost = {q: 0.01 for q in range(6)}
    qcost[1] = 0.5  # terrible qubit
    ecost = {tuple(sorted(e)): 0.01 for e in LINE}
    best = best_chain(LINE, 3, qcost, ecost)
    assert 1 not in best
    assert chain_cost(best, qcost, ecost) < chain_cost([0, 1, 2], qcost, ecost)


@pytest.mark.parametrize("name", ["ghz", "mirror"])
def test_benchmark_ideal_answer_is_correct_on_noiseless_sim(name):
    """The 'known correct answer' must really be correct, or every score is meaningless."""
    qc, ideal = bm.BENCHMARKS[name](4)
    counts = AerSimulator().run(qc, shots=2000).result().get_counts()
    assert bm.score_counts(counts, ideal) == pytest.approx(1.0)


def test_ghz_is_split_between_two_outcomes():
    qc, ideal = bm.ghz(3)
    counts = AerSimulator().run(qc, shots=4000).result().get_counts()
    assert set(counts) == {"000", "111"}


def test_aggregate_excludes_simulated(tmp_path):
    base = {
        "timestamp_utc": "2026-10-09T00:00:00+00:00", "backend": "b", "shots": 1,
        "chain_len": 5, "layouts": {}, "results": [], "calibration_summary": {},
        "calibration": {"qubits": [{"qubit": 0, "readout_error": 0.01, "gate_error_1q": 0.001,
                                     "reported_readout_error": 0.01,
                                     "reported_gate_error_1q": 0.0005}]},
    }
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "real.json").write_text(json.dumps({**base, "simulated": False}))
    (runs / "sim.json").write_text(json.dumps({**base, "simulated": True}))
    out = tmp_path / "out" / "h.json"
    assert build_history(runs, out) == 1
    assert build_history(runs, out, include_simulated=True) == 2
