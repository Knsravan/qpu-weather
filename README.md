# 🌦️ Quantum Weather Report

**A daily, independent check-up of a real IBM quantum computer** — how its qubits *actually* behave, how that drifts over time, and which error-fixing method really helps.

> Quantum chips are moody. Vendors publish "usually accurate" numbers. This project rides the bus every day and writes down what really happens.

**Status:** the first real-hardware run (IBM `ibm_fez`, 2026-10-09) completed and is published on the dashboard. Only one run exists so far, so there is no drift history yet; a weekly GitHub Action adds more. Simulator output is deliberately never published.

---

## What it does

| Step | What happens | Why it matters |
|---|---|---|
| 1. **Independent check** | Measures every qubit's readout error, a single-qubit gate-sequence error and every connection's two-qubit gate error on the real device, then compares with the vendor-reported values | Datasheet numbers can be stale between calibrations |
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

## First real result (single run, not a trend)
One run on IBM `ibm_fez`, 2026-10-09, 5-qubit chains, 4000 shots. Score = probability of the known-correct answer (1.0 = perfect):

| Chain | Benchmark | raw | readout | zne | readout+zne |
|---|---|---|---|---|---|
| best (q24,25,37,45,46) | GHZ | 0.909 | 0.947 | 0.943 | **0.981** |
| best | mirror | 0.910 | 0.930 | 0.943 | **0.964** |
| naive (q0-4) | GHZ | 0.820 | 0.883 | 0.900 | **0.966** |
| naive | mirror | 0.781 | 0.883 | 0.847 | **0.959** |

What it suggests, no more: qubit choice mattered (about 0.09 raw), and readout + ZNE together was best in all four cases. Independent readout error matched IBM's figure (median 1.00x) but a few qubits were clearly worse than advertised (q90: 5.8% vs 0.4%). One run on one device on one day is not enough to generalize; the weekly runs will build the history. The raw data is in `data/runs/`.

## Honest limitations
- Two-qubit gate errors used when choosing chains are **measured by this tool with a simple repeated-gate decay test** (see `twoq.py`). It is a quick estimate, not randomized benchmarking: it includes crosstalk from edges tested in parallel, and vendor values are only a fallback. So far it has only been checked on a local simulator.
- The one-qubit gate number is the decay over 100 repeated X gates on all qubits at once, so it also contains qubit decay and crosstalk. On the first real run it came out ~13x IBM's single-gate figure and was uncorrelated with it, so it is **not comparable** with IBM's number; it is only used to rank qubits against each other. Readout error, by contrast, matched IBM's figure (median ratio 1.00).
- Free IBM plans have limited monthly QPU time. A default run is small (2 jobs), but check your quota.
- Results describe the specific device and day. Don't over-generalize.

## Quick start

```bash
git clone https://github.com/<you>/qpu-weather && cd qpu-weather
pip install -e ".[dev]"
pytest                                   # 27 tests, no quantum computer needed

# development only: noisy local simulator (output is tagged simulated, never published)
qpu-weather run --simulate --chain-len 4

# real hardware
export IBM_QUANTUM_TOKEN=...             # from your IBM Quantum account
qpu-weather run                          # least-busy device; or --backend <name>
qpu-weather aggregate                    # rebuilds docs/data/history.json
```

Open `docs/index.html` through a local server (`python -m http.server -d docs`) to see the dashboard.

## Automate it on GitHub (weekly real runs)
1. Repo → **Settings → Secrets and variables → Actions** → add secret **`IBM_QUANTUM_TOKEN`**.
2. (Optional) add variable **`IBM_BACKEND`** to pin a device, and secret **`IBM_INSTANCE`** if IBM requires an instance (CRN).
3. **Settings → Pages** → deploy from branch `main`, folder `/docs`.
4. The *Quantum weather report* workflow runs weekly (Mondays 03:17 UTC; free IBM plans have little QPU time, so daily runs would not fit), commits `data/runs/*.json`, and the dashboard updates itself. It stops early with a clear message if the IBM instance has no QPU time left.

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
