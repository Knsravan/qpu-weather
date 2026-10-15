# 🌦️ Qubit Weather Report

**A daily, independent check-up of a real IBM quantum computer** — how its qubits *actually* behave, how that drifts over time, and which error-fixing method really helps.

> Quantum chips are moody. Vendors publish "usually accurate" numbers. This project rides the bus every day and writes down what really happens.

**Status:** four real-hardware runs so far: three on IBM `ibm_fez` (2026-10-09, 2026-10-13) and one on IBM `ibm_kingston` (2026-10-12). That is too few for a drift trend, and two different chips cannot share one trend line, so the weekly GitHub Action now stays on `ibm_fez`. Simulator output is deliberately never published.

---

## What it does

| Step | What happens | Why it matters |
|---|---|---|
| 1. **Independent check** | Measures every qubit's readout error, a single-qubit gate-sequence error and every connection's two-qubit gate error on the real device, then compares with the vendor-reported values | Datasheet numbers can be stale between calibrations |
| 2. **Drift diary** | Every run is saved; the dashboard plots trends over days | Shows which qubits/days are stable |
| 3. **Pick the best qubits** | Finds the healthiest connected chain by *measured* error and runs it next to two others: the first qubits by index (naive) and the chain IBM's own published numbers would pick (vendor) | Shows whether measuring yourself beats trusting the datasheet |
| 3b. **Gate errors, the standard way** | Randomized benchmarking on the qubits and couplings of the selected and vendor-guided chains | A gate-error number that is not fooled by misreads, unlike the quick decay test |
| 3c. **Is it really entangled?** | Four extra "parity" circuits per chain turn the GHZ score into a fidelity *F*; *F* > 0.5 over its whole 95% range means the qubits were genuinely entangled | The plain GHZ score cannot tell entanglement from a lucky 50/50 mix of all-0 and all-1 |
| 4. **Rank the fixes** | Runs benchmark circuits with a known correct answer under four methods: `raw`, `readout` mitigation, `zne` (zero-noise extrapolation), `readout+zne` | Evidence-based advice instead of defaults |

### How the scoring works (no simulator needed for the "right answer")
- **GHZ circuit** → correct outputs are all-0s or all-1s.
- **Mirror circuit** → random gates followed by their exact inverse, so the correct output is all-0s by construction.
- **Score** = probability of the correct output (1.0 = perfect). Each score comes with a 95% range from shot noise (bootstrap: resample the shots and recompute).
- The GHZ score only counts all-0 / all-1 outcomes, so it catches bit flips but cannot tell whether the entanglement survived.

### Methods (implemented from scratch in `mitigation.py`)
- **Readout mitigation:** invert the per-qubit confusion matrices measured in the same run.
- **ZNE:** deliberately add noise by folding the circuit (`C → C C† C`, 1×/3×/5× noise), then extrapolate the score back to zero noise. Folding happens *after* compilation so the compiler can't cancel it. If adding noise did **not** lower the score, ZNE's basic assumption is broken and no ZNE number is reported for that case.

## Real results so far (4 runs, 2 chips, not a trend)
5-qubit chains, 4000 shots. Raw score = probability of the known-correct answer (1.0 = perfect), with no fix applied:

| Run | Chip | best chain: GHZ / mirror | first 5 qubits: GHZ / mirror |
|---|---|---|---|
| 2026-10-09 14:41 | `ibm_fez` | 0.909 / 0.910 | 0.820 / 0.781 |
| 2026-10-09 14:48 | `ibm_fez` | 0.929 / 0.913 | 0.821 / 0.776 |
| 2026-10-12 11:01 | `ibm_kingston` | 0.931 / 0.923 | 0.669 / 0.371 |
| 2026-10-13 09:34 | `ibm_fez` | 0.941 / 0.897 | 0.835 / 0.831 |

What it suggests, no more:
- **Picking qubits by measured error helped in every run.** The 2026-10-12 gap is unusually large because the first-5 chain broke down (see below), so don't read it as typical.
- **Readout error matched IBM's figure** each time (median 1.00×, 1.01×, 0.98×, 0.95×), but single qubits can be far worse than advertised (2026-10-09: q90 measured 5.8% vs IBM's 0.4%).
- **The "best" chain changes every run** (24,25,37,45,46 → 94,95,99,115,114 → 151–155 → 137,147,146,145,144). It is advice for that run, not a fixed property of the chip.
- **Readout + ZNE was the best fix on the best chain in all eight cases**, and on every chain in the 2026-10-13 run. On `ibm_kingston` the first-5 chain behaved strangely: its score went *up* when noise was added (mirror 0.37 → 0.54 → 0.51). ZNE cannot work there and the dashboard leaves those cases out. Possible causes, not proven: the chip changed between the calibration and benchmark jobs, or steady (coherent) errors partly cancel when the circuit is folded.
- **Our chain vs the chain IBM's own numbers would pick: no clear winner yet (one run).** On 2026-10-13 (`ibm_fez`), raw GHZ was 0.941 (95% range 0.935–0.948) for ours vs 0.927 (0.918–0.934) for IBM's pick, only just apart; raw mirror was 0.897 vs 0.891 with overlapping ranges, so a tie. After readout+ZNE, IBM's pick scored higher on mirror (0.974 vs 0.953). So far, measuring the chip ourselves clearly beats "first 5 qubits" but has **not** been shown to beat trusting IBM's numbers. The ranges cover shot noise only; more weekly runs are needed.

The raw data is in `data/runs/`.

## Honest limitations
- Two-qubit gate errors used when choosing chains are **measured by this tool with a simple repeated-gate decay test** (see `twoq.py`). It is a quick estimate, not randomized benchmarking: it includes crosstalk from edges tested in parallel, and vendor values are only a fallback. On the second real run (`ibm_fez`, 176 connections) it came out about 2.6x IBM's figures (median) with a Pearson correlation of 0.73 that is driven by four couplings IBM lists at 100% error (rank correlation about 0.4, only moderate agreement). Treat it as a rough indicator, not an absolute error rate and not a validated ranking. Its `|0>` start was nearly blind on this device's CZ gate (median 0.01%); the `|+>` start carried the signal (median 0.85%).
- The one-qubit gate number is the decay over 100 repeated X gates on all qubits at once, so it also contains qubit decay and crosstalk. On the first real run it came out ~13x IBM's single-gate figure and was uncorrelated with it, so it is **not comparable** with IBM's number; it is only used to rank qubits against each other. Readout error, by contrast, matched IBM's figure (median ratio 1.00).
- Free IBM plans have limited monthly QPU time. A default run is small (2 jobs; the benchmark job has 18 circuits since the vendor chain was added), but check your quota.
- ZNE uses a straight-line fit over 1×/3×/5× noise and is clipped to [0, 1]; a ZNE score of exactly 1.000 is that clipping, not a perfect chip. When added noise does not lower the score, ZNE is reported as missing rather than as a number.
- ZNE runs three noise levels, so it spends three times the shots of a raw run. Each run now also reports ZNE's range when it gets only a third of the shots per level (the same total as raw), and the dashboard says whether it is still clearly ahead.
- Randomized benchmarking runs on the chosen chains only (not the whole chip) to save machine time, and all qubits of a chain at once, so it includes neighbour interference. Per-gate values are an approximation (error per random operation divided by its average gate count). On the simulator it recovered the true two-qubit errors to within 1.0-1.2x; single-qubit errors are so small that 500 shots resolve them only roughly.
- The ± ranges cover shot noise only, not day-to-day drift. Runs before 2026-10-13 have no ranges and no saved raw counts.
- Results describe the specific device and day. Don't over-generalize.

## Quick start

```bash
git clone https://github.com/<you>/qpu-weather && cd qpu-weather
pip install -e ".[dev]"
pytest                                   # 32 tests, no quantum computer needed

# development only: noisy local simulator (output is tagged simulated, never published)
qpu-weather run --simulate --chain-len 4

# real hardware
export IBM_QUANTUM_TOKEN=...             # from your IBM Quantum account
qpu-weather run                          # least-busy device; or --backend <name>
qpu-weather aggregate                    # rebuilds docs/data/history.json

# figures for the paper, regenerated from the real run files
pip install -e ".[paper]"
python scripts/paper_figures.py --out paper/figures
```

A plain-language, point-and-explain tour of the dashboard is in `docs/explain.html` (same data, same server).

Open `docs/index.html` through a local server (`python -m http.server -d docs`) to see the dashboard.

## Automate it on GitHub (weekly real runs)
1. Repo → **Settings → Secrets and variables → Actions** → add secret **`IBM_QUANTUM_TOKEN`**.
2. (Optional) the workflow uses `ibm_fez` so the history stays on one chip; add variable **`IBM_BACKEND`** to use a different device, and secret **`IBM_INSTANCE`** if IBM requires an instance (CRN).
3. **Settings → Pages** → deploy from branch `main`, folder `/docs`.
4. The *Qubit weather report* workflow runs weekly (Mondays 03:17 UTC; free IBM plans have little QPU time, so daily runs would not fit), commits `data/runs/*.json`, and the dashboard updates itself. It stops early with a clear message if the IBM instance has no QPU time left.

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
