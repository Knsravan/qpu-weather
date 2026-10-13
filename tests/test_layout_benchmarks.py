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


def test_vendor_cost_uses_reported_numbers_and_avoids_unknown_qubits():
    from qpu_weather.layout import reported_qubit_cost

    qubits = [
        {"qubit": 0, "reported_readout_error": 0.01, "reported_gate_error_1q": 0.001},
        {"qubit": 1, "reported_readout_error": None, "reported_gate_error_1q": 0.001},
    ]
    cost = reported_qubit_cost(qubits)
    assert cost[0] == pytest.approx(0.013)
    assert cost[1] > 1.0


def test_aggregate_strips_counts_and_flags_old_runs_with_bad_zne(tmp_path):
    def res(by_factor):
        return {"layout": "naive", "benchmark": "mirror", "chain": [0, 1],
                "scores": {"raw": by_factor["1"], "raw_by_factor": by_factor},
                "counts_by_factor": {"1": {"00": 1}}}

    run = {
        "timestamp_utc": "2026-10-12T00:00:00+00:00", "backend": "b", "simulated": False,
        "results": [res({"1": 0.371, "3": 0.537, "5": 0.514}), res({"1": 0.9, "3": 0.8, "5": 0.7})],
        "calibration": {"qubits": []},
    }
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "r.json").write_text(json.dumps(run))
    out = tmp_path / "h.json"
    build_history(runs, out)
    got = json.loads(out.read_text())["runs"][0]["results"]
    assert all("counts_by_factor" not in r for r in got)
    assert [r["scores"]["zne_ok"] for r in got] == [False, True]
