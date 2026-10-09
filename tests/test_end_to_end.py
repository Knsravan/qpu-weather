"""Full pipeline on the local noisy simulator. Proves the code runs end to end;
it says nothing about real quantum hardware."""

from qpu_weather.backend import get_backend
from qpu_weather.experiment import METHODS, run_experiment


def test_pipeline_runs_and_mitigation_helps_on_noisy_sim():
    handle = get_backend(simulate=True)
    r = run_experiment(handle, shots=2000, cal_shots=1000, chain_len=4)

    assert r["simulated"] is True
    assert set(r["layouts"]) == {"naive", "best"}
    assert len(r["results"]) == 4  # 2 layouts x 2 benchmarks
    assert len(r["calibration"]["qubits"]) == handle.target_backend.num_qubits

    for res in r["results"]:
        s = res["scores"]
        assert all(0.0 <= s[m] <= 1.0 for m in METHODS)
        # readout noise dominates on this fake device, so mitigation must beat raw
        assert s["readout"] > s["raw"]

    # the independent health check should land near the (noisy) simulator's truth
    med = r["calibration_summary"]["median_readout_measured_over_reported"]
    assert 0.5 < med < 2.0
