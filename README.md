# 🌦️ Quantum Weather Report

**A daily, independent check-up of a real IBM quantum computer** — how its qubits *actually* behave, how that drifts over time, and which error-fixing method really helps.

> Quantum chips are moody. Vendors publish "usually accurate" numbers. This project rides the bus every day and writes down what really happens.

**Status:** code complete and tested; no real-hardware results published yet. The dashboard stays empty until the first real QPU run (simulator output is deliberately never published).

---

## What it does

| Step | What happens | Why it matters |
|---|---|---|
| 1. **Independent check** | Measures every qubit's readout error and single-qubit gate error on the real device, then compares with the vendor-reported values | Datasheet numbers can be stale between calibrations |
| 2. **Drift diary** | Every run is saved; the dashboard plots trends over days | Shows which qubits/days are stable |
| 3. **Pick the best qubits** | Finds the healthiest connected chain by *measured* error and compares it with naively taking the first qubits | Quantifies how much qubit choice matters |
| 4. **Rank the fixes** | Runs benchmark circuits with a known correct answer under four methods: `raw`, `readout` mitigation, `zne` (zero-noise extrapolation), `readout+zne` | Evidence-based advice instead of defaults |

### How the scoring works (no simulator needed for the "right answer")
- **GHZ circuit** → correct outputs are all-0s or all-1s.
- **Mirror circuit** → random gates followed by their exact inverse, so the correct output is all-0s by construction.
- **Score** = probability of the correct output (1.0 = perfect).

### Methods (implemented from scratch in `mitigation.py`)
- **Readout mitigation:** invert the per-qubit confusion matrices measured in the same run.
- **ZNE:** deliberately add noise by folding the circuit (`C → C C† C`, 1×/3×/5× noise), then extrapolate the score back to zero noise. Folding happens *after* compilation so the compiler can't cancel it.

## Honest limitations
- Two-qubit gate errors used when choosing chains are **measured by this tool with a simple repeated-gate decay test** (see `twoq.py`). It is a quick estimate, not randomized benchmarking: it includes crosstalk from edges tested in parallel, and vendor values are only a fallback. So far it has only been checked on a local simulator.
- One-qubit gate error is estimated from long X-gate sequences run in parallel, so it includes some crosstalk.
- Free IBM plans have limited monthly QPU time. A default run is small (2 jobs), but check your quota.
- Results describe the specific device and day. Don't over-generalize.

## Quick start

```bash
git clone https://github.com/<you>/qpu-weather && cd qpu-weather
pip install -e ".[dev]"
pytest                                   # 16 tests, no quantum computer needed

# development only: noisy local simulator (output is tagged simulated, never published)
qpu-weather run --simulate --chain-len 4

# real hardware
export IBM_QUANTUM_TOKEN=...             # from your IBM Quantum account
qpu-weather run                          # least-busy device; or --backend <name>
qpu-weather aggregate                    # rebuilds docs/data/history.json
```

Open `docs/index.html` through a local server (`python -m http.server -d docs`) to see the dashboard.

## Automate it on GitHub (daily real runs)
1. Repo → **Settings → Secrets and variables → Actions** → add secret **`IBM_QUANTUM_TOKEN`**.
2. (Optional) add variable **`IBM_BACKEND`** to pin a device.
3. **Settings → Pages** → deploy from branch `main`, folder `/docs`.
4. The *Daily quantum weather report* workflow runs every day, commits `data/runs/*.json`, and the dashboard updates itself.

## Project layout
```
src/qpu_weather/
  backend.py       real IBM backend (or dev-only simulator)
  calibration.py   per-qubit readout + gate error, measured vs reported
  layout.py        best connected qubit chain
  benchmarks.py    GHZ and mirror circuits with known answers
  mitigation.py    folding, ZNE, readout mitigation
  experiment.py    the daily run
  aggregate.py     history file for the dashboard
docs/index.html    static dashboard (GitHub Pages)
tests/             unit + end-to-end tests
```

## Roadmap
- Upgrade the two-qubit gate error measurement to randomized benchmarking / interleaved CX
- Add dynamical decoupling and Pauli twirling to the mitigation comparison
- More devices and per-day stability scores for each qubit

## License
MIT
