# CLAUDE.md — Quantum Weather Report (`qpu-weather`)

Complete project brief. Read all of it before changing anything. It covers: who this is for, how the idea was chosen, what the project does and how, what already exists elsewhere, what is new here, what is built, what is NOT verified, and what to do next.

---

## 1. Owner and working style
- Owner: **Kns** (GitHub: `Knsravan`), a developer early in their career, based in India.
- Goal: a **credible, real-hardware portfolio project** for their GitHub profile. It does not need to be groundbreaking, but it must be honest, working, and defensible in an interview.
- Kns does not have a quantum-computing background. **Explain things in plain, simple language** (analogies are welcome), define jargon the first time, and avoid unexplained acronyms. Keep answers direct.
- Kns explicitly wants a **real quantum computer, not a simulator**, with real outputs.

## 2. One-paragraph summary
Quantum chips are moody: some days they are accurate, some days they are not, and vendors only publish "usually fine" numbers. **Quantum Weather Report** rides the bus every day and writes down what actually happens. Each day it runs small test programs on a real IBM quantum computer, measures how many mistakes every qubit really makes, compares that with what IBM says, keeps a history so drift is visible, picks the best qubits to use, and tests which error-fixing trick actually gets closest to the correct answer. Results appear on a public dashboard (GitHub Pages) and are committed to the repo by a daily GitHub Action.

Simple analogy used with the owner: *a school bus company says "we're usually on time"; this tool is the person who rides the bus every day, writes down what really happens, and says "take the 8:10 bus on Mondays, leave early on Fridays."*

## 3. How we got here (decision history — so you don't re-propose rejected ideas)
1. **Original idea:** a "certified quantum random number generator" (random bits from a real QPU, post-processed, validated with NIST SP 800-22 statistical tests, exposed via an API).
2. **Upgrade ideas considered:** CHSH/Bell-test certification, signed cryptographic receipts, an "ML tries to predict the bits" challenge, multi-source mixing, a public randomness beacon.
3. **Rejected by the owner:** it felt niche and not useful in practice. (Agreed: normal OS/bank-grade randomness is already good enough for almost everyone; the quantum part is mostly a "wow" factor.)
4. **New requirement:** a real-world quantum project that runs on **real hardware** with **real outputs**, not a simulator.
5. **Options offered:** quantum hardware health tracker, error-mitigation demo, VQE molecule energy (H2), BB84 key-exchange demo.
6. **Chosen:** hardware health tracker + error mitigation, then narrowed to two additions that fill real gaps:
   - **Idea 1 — Independent checking:** don't trust the vendor's numbers; measure them.
   - **Idea 3 — Which fix works best, measured:** rank mitigation methods with evidence instead of using defaults.
   - (Drift history comes along naturally with daily runs. Cross-vendor comparison was dropped as too costly/hard for a solo developer.)
7. **Repo:** `https://github.com/Knsravan/qpu-weather`. Built first in a Claude cloud session, now continued in Claude Code.

## 4. Glossary (plain language)
- **QPU** — Quantum Processing Unit: the quantum chip, like a CPU. We rent time on IBM's.
- **Qubit** — the quantum version of a bit; a chip has 100+ of them.
- **Shot** — one run of a circuit. We repeat circuits thousands of times and count outcomes.
- **Circuit** — the small program (a list of gates) we run on the chip.
- **Readout error** — the chip reads a qubit wrongly (says 1 when it was 0, or vice versa).
- **Gate error** — a gate (operation) does not do exactly what it should.
- **Calibration** — IBM's own periodic tuning/measurement of the device. Its published numbers can go stale between calibrations.
- **Drift** — how the chip's behavior changes over hours/days.
- **Error mitigation** — software tricks that reduce the effect of noise without full error correction.
- **Readout mitigation** — correct for known measurement mistakes using a measured confusion matrix.
- **ZNE (zero-noise extrapolation)** — run the circuit with *deliberately more* noise (1x, 3x, 5x), then extrapolate the score back to "zero noise".
- **Circuit folding** — how we add noise on purpose: replace circuit `C` with `C C† C` (C then its inverse then C again). Ideally identical result, but 3x the gates.
- **GHZ state** — entangled state of n qubits; ideal measurement gives all-0s or all-1s, about 50/50.
- **Mirror circuit** — random gates followed by their exact inverse; ideal output is all zeros *by construction*, so no simulation is needed to know the right answer.
- **Transpile** — compile a circuit onto a specific chip's native gates and chosen physical qubits.
- **Layout / chain** — which physical qubits a circuit uses; here, a path of connected qubits.

## 4b. What already exists (prior art) and what is new
*Written from memory during planning; verify with a quick search before making public claims.*

Already exists:
- IBM publishes per-qubit calibration data for every device (self-reported).
- Smart qubit selection: Qiskit's compiler picks low-error qubits; `mapomatic` does this too.
- Error mitigation: Qiskit Runtime built-ins, **Mitiq** (open source library), **Q-CTRL** (commercial).
- Benchmark tracking: Unitary Fund's **Metriq** compares devices on standard tests.

What this project adds (the honest gap):
1. **Independent checking** — measure the chip ourselves and show whether it matches the vendor's numbers *today*.
2. **Drift history** — a public, easy-to-read daily record (as far as the owner and planning notes know, no easy public dataset like this exists).
3. **Measured ranking of fixes** — test several mitigation methods on the same circuits and report which one actually improved the answer and by how much, instead of just applying a default.

Honest framing: this is **incremental, not groundbreaking** — a "weather report for quantum chips". Its strength is real hardware, real data, clear scoring, and a real gap. Never oversell it.

## 5. Hard rules (do not break)
1. **Never publish simulator output as a result.** `--simulate` runs go to `data/simulated/` (gitignored); `aggregate` excludes them by default; the dashboard must show its empty state until a real QPU run exists.
2. **Never commit or print the IBM token.** It comes only from the `IBM_QUANTUM_TOKEN` env var / GitHub Actions secret.
3. **Never hand-write or invent results data.** Everything in `data/runs/` and `docs/data/history.json` must come from a real run through the CLI.
4. Keep claims honest. Do not call outputs "certified" or "proven". README and dashboard state the limitations (section 9).
5. **Fold circuits AFTER transpiling**, then re-translate with `translate_only` (optimization level 0). Folding before transpiling lets the compiler cancel the extra gates and silently breaks ZNE. (Inverting native gates yields non-native ones like `sxdg`; the translate step fixes that.)

## 6. How it works (the daily experiment, step by step)
Entry point: `experiment.run_experiment(handle, shots=4000, cal_shots=2000, chain_len=5)`; CLI: `qpu-weather run`.

**Step 1 — Independent check (`calibration.py`).** One job, 3 circuits spanning the whole device width:
- `prep0`: measure all qubits (gives P(read 1 | prepared 0) = p01).
- `prep1`: X on all qubits, measure (gives p10 = 1 − P(read 1 | prepared 1)).
- `xrep`: X applied 100 times (identity in theory), barriers between gates, then measure.
Per qubit: readout_error = (p01 + p10) / 2. 1-qubit gate error from decay: ratio = P(0 after X^100) / P(0 baseline); gate_error = 1 − ratio^(1/100). Compared with the vendor values in `backend.target` (`measure` error and `x`/`sx` error). `summarize_vs_reported` gives the median measured/reported ratio and the five worst qubits. Calibration uses an identity layout and optimization level 0.

**Step 2 — Choose qubits (`layout.py`).** Enumerate every simple path of `chain_len` connected qubits in the coupling map. Cost = sum over qubits of (measured readout error + 3 × measured 1q gate error) + sum over edges of vendor-reported 2-qubit error. `naive` = first chain by qubit index (the baseline a careless user gets); `best` = lowest cost.

**Step 3 — Benchmarks (`benchmarks.py`).** `ghz(n)` (ideal outputs all-0s/all-1s) and `mirror(n, layers=3, seed=11)` (ideal all-0s). Score = probability mass on the ideal outputs (1.0 = perfect). Each is transpiled onto each chain at optimization level 1, then folded at factors **1, 3, 5**. All circuits (2 layouts × 2 benchmarks × 3 factors = 12) run in **one** job. A barrier inside the mirror circuit stops the compiler cancelling it against its inverse.

**Step 4 — Score four methods (`experiment.score_methods`, `mitigation.py`):**
- `raw` — score at fold factor 1.
- `readout` — invert the tensor product of per-qubit confusion matrices (built from this run's p01/p10 for the chain's physical qubits; LSB-first to match Qiskit bit order); clip negatives, renormalize; then score.
- `zne` — linear fit of raw scores vs fold factor, take intercept at 0, clip to [0, 1].
- `readout+zne` — same extrapolation on the readout-mitigated scores.
`improvement_vs_raw_pct` = (raw_error − method_error) / raw_error × 100, where error = 1 − score.

**Step 5 — Save + publish.** CLI writes `data/runs/<timestamp>_<backend>.json`; `qpu-weather aggregate` builds a slim `docs/data/history.json`; the dashboard (`docs/index.html`) reads it. The GitHub Action (`daily.yml`) does run → aggregate → commit, daily at 03:17 UTC and on manual trigger.

## 7. Run file schema (`data/runs/*.json`)
`schema`, `timestamp_utc`, `backend`, `simulated`, `shots`, `chain_len`, `calibration` {`qubits`[ {`qubit`, `p01`, `p10`, `readout_error`, `gate_error_1q`, `reported_readout_error`, `reported_gate_error_1q`} ], `shots`, `job_id`, `x_repeats`}, `calibration_summary`, `layouts` {`naive`|`best`: {`chain`, `cost`}}, `results`[ {`layout`, `benchmark`, `chain`, `scores` {`raw`, `readout`, `zne`, `readout+zne`, `raw_by_factor`}, `improvement_vs_raw_pct`} ], `benchmark_job_id`, `methods`, `notes`.
`docs/data/history.json` = `{"runs": [...]}` with per-qubit rows slimmed to `q, ro, g1, ro_rep, g1_rep`.

## 8. Dashboard
`docs/index.html`: single static file, vanilla JS + inline SVG, no libraries, light/dark aware. Cards: today's advice (best chain), measured-vs-reported ratio, which-fix-works-best table (average score on the best chain across all runs), drift line chart (median readout error measured vs reported), five best/worst qubits. Empty state when no runs. Live on GitHub Pages (`/docs` of `main`).

## 9. Honest limitations (keep these visible)
- 2-qubit gate errors used for chain selection are **vendor-reported**, not measured.
- 1q gate error is estimated from long parallel X sequences, so it includes crosstalk.
- Results describe one device on one day; do not over-generalize.
- Passing benchmark scores is not a proof of anything beyond those circuits.
- Calibration circuits span the full device width; confirm this is fine on real hardware and within free-plan QPU time.
- `get_backend` uses `QiskitRuntimeService(channel="ibm_quantum_platform", token=...)`. IBM's platform naming and a possible need for an **instance (CRN)** may differ from the code — the most likely first failure.
- ZNE uses simple linear extrapolation over factors 1/3/5; with noisy data it can overshoot (clipped to [0, 1]).
- Free-plan quota changes; do not assume limits. Default run is small (2 jobs).

## 10. Status (as of 2026-10-09)
Done:
- Full code (`src/qpu_weather/`), **16 passing tests** (`pytest -q`, no quantum access needed), dashboard, two GitHub Actions workflows, README, LICENSE (MIT).
- End-to-end pipeline verified **only on a local noisy simulator** (FakeLagosV2 via Aer). On it, independent measurement matched the simulator's reported numbers (~0.99×) and readout mitigation clearly beat raw — evidence the logic works, **not** evidence about real hardware.
- Pushed to GitHub; Pages dashboard live and correctly showing the empty state.

NOT done / unverified:
- **The real-hardware path has never run.** Owner still needed to add the `IBM_QUANTUM_TOKEN` repo secret and trigger the first workflow run (Actions → "Daily quantum weather report" → Run workflow).
- Pages deployment was confirmed by the owner's screenshot; nothing has been published beyond the empty state.

## 11. Repo layout
```
src/qpu_weather/
  backend.py      get_backend(): real IBM service or dev-only Aer simulator
                  (BackendHandle: .backend = where it runs, .target_backend = what it is transpiled against)
  runner.py       transpile_with_layout, translate_only, run_counts (SamplerV2 real / backend.run sim), job_info
  calibration.py  per-qubit readout + 1q gate error, measured vs vendor-reported
  layout.py       all_chains / naive_chain / best_chain, edge_errors
  benchmarks.py   ghz, mirror, score_counts; classical register named "c"
  mitigation.py   fold_global, zne_extrapolate, confusion_matrix, apply_readout_mitigation
  experiment.py   run_experiment, score_methods
  aggregate.py    build_history (skips simulated by default)
  cli.py          `qpu-weather run | aggregate`
tests/            test_mitigation.py, test_layout_benchmarks.py, test_end_to_end.py
docs/             index.html + data/history.json (starts as {"runs":[]})
data/runs/        real run files (committed by the Action)
.github/workflows daily.yml (cron + manual, needs secret), tests.yml (pytest on push/PR)
```
Bit order: Qiskit counts strings have classical bit 0 as the RIGHTMOST character; readout matrices are built LSB-first (unit-tested).

## 12. Commands
```bash
pip install -e ".[dev]"
pytest -q
qpu-weather run --simulate --chain-len 4        # dev only -> data/simulated/
qpu-weather run [--backend NAME]                # REAL hardware; needs IBM_QUANTUM_TOKEN
qpu-weather aggregate                           # rebuild docs/data/history.json
python -m http.server -d docs                   # view dashboard locally
```
Python 3.13 locally, CI uses 3.12. Fake backend for dev/tests: `FakeLagosV2` (7 qubits).

## 13. Next steps (in order)
1. **First real run.** Get the workflow green: verify auth (add optional `IBM_INSTANCE` support if IBM requires it), confirm `SamplerV2` result access through the `c` register works on real devices, confirm `translate_only` preserves the physical layout, check QPU seconds used, consider calibrating only a candidate subset of qubits if the full-width job is too costly. Fix what breaks and add a regression test per fix where possible.
2. When real data lands: run `qpu-weather aggregate`, confirm the dashboard renders it, update the README status line.
3. Measure 2-qubit gate error directly (interleaved/repeated CX or ECR decay) and use it in `layout.py` instead of vendor values.
4. Add dynamical decoupling and Pauli twirling to the mitigation comparison.
5. Per-qubit stability score over time on the dashboard; more devices if access allows.
6. Pin the repo on Kns's GitHub profile once real results exist; add a short results section (real numbers only) to the README.

## 14. Working style for this repo
- Minimal dependencies; dashboard stays static and library-free.
- New logic gets tests; tests must never need QPU access (use fake backends / Aer).
- Commit small and often. Never commit anything under `data/simulated/`.
- When reporting back to Kns: plain language, say what is verified vs not, no oversell.
