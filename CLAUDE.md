# CLAUDE.md — qpu-weather (Quantum Weather Report)

Read this first. It tells you what this project is, what is done, what is NOT verified, and what to build next.

## What this project is
A daily, independent check-up of a **real IBM quantum computer**. It (1) measures each qubit's real readout and 1-qubit gate error and compares it with the vendor-reported values, (2) logs drift over time, (3) picks the healthiest connected qubit chain by *measured* error, and (4) ranks error-mitigation methods (`raw`, `readout`, `zne`, `readout+zne`) on benchmark circuits whose correct answer is known in advance. A static dashboard (`docs/`, GitHub Pages) and a daily GitHub Action publish the results.

Owner: Kns (GitHub: Knsravan), a developer early in their career. The goal is a credible portfolio project for their GitHub profile. Explain decisions in plain language; do not assume quantum-computing background.

## Hard rules (do not break these)
1. **Never publish simulator output as a result.** Runs from `--simulate` go to `data/simulated/` (gitignored) and `aggregate` excludes them by default. The dashboard must show the empty state until a real QPU run exists.
2. **Never commit or print the IBM token.** It comes from the `IBM_QUANTUM_TOKEN` env var / GitHub Actions secret only.
3. **Do not invent or hand-write results data.** Anything in `data/runs/` or `docs/data/history.json` must come from a real run via the CLI.
4. Keep claims honest: README and dashboard state limitations (see below). Do not call results "certified" or "proven".
5. Fold circuits **after** transpiling, then re-translate with `translate_only` (optimization level 0). Folding before transpiling lets the compiler cancel the extra gates and silently breaks ZNE.

## Current status (as of 2026-10-09)
- Code complete, **16 tests pass** (`pytest -q`, no quantum hardware needed). Python 3.13 locally, CI uses 3.12.
- Pipeline verified end-to-end **only on a local noisy simulator** (FakeLagosV2 via Aer).
- Repo pushed; GitHub Pages dashboard is live and correctly shows "No real quantum-computer runs yet".
- **The real-hardware path has never been run.** The IBM token secret (`IBM_QUANTUM_TOKEN`) and first workflow run were still to be done by the owner.

## Layout
```
src/qpu_weather/
  backend.py      get_backend(): real IBM service, or dev-only Aer simulator (BackendHandle has
                  .backend = where it runs, .target_backend = what it is transpiled against)
  runner.py       transpile_with_layout, translate_only, run_counts (SamplerV2 on real, backend.run on sim)
  calibration.py  per-qubit readout + 1q gate error (X^100 decay), compared with target-reported values
  layout.py       all_chains / naive_chain / best_chain on the coupling map (2q edge errors are vendor-reported)
  benchmarks.py   ghz(n), mirror(n) with known ideal outputs; classical register is named "c"
  mitigation.py   fold_global, zne_extrapolate (linear, clipped to [0,1]), readout confusion-matrix inversion
  experiment.py   run_experiment(): calibrate -> choose chains -> ONE benchmark job -> score 4 methods
  aggregate.py    data/runs/*.json -> docs/data/history.json (skips simulated)
  cli.py          `qpu-weather run|aggregate`
docs/index.html   dependency-free dashboard (vanilla JS + inline SVG), reads docs/data/history.json
.github/workflows daily.yml (cron + manual, needs secret), tests.yml
```
Bit-order convention: Qiskit counts strings have classical bit 0 as the RIGHTMOST character; readout matrices are built LSB-first to match (tested).

## Commands
```bash
pip install -e ".[dev]"
pytest -q
qpu-weather run --simulate --chain-len 4        # dev only, output goes to data/simulated/
qpu-weather run [--backend NAME]                # REAL hardware; needs IBM_QUANTUM_TOKEN
qpu-weather aggregate                           # rebuild docs/data/history.json
python -m http.server -d docs                   # view dashboard locally
```

## Known limitations / risks
- 2-qubit gate errors used for chain selection are **vendor-reported**, not measured.
- 1q gate error comes from long parallel X sequences, so it includes some crosstalk.
- Calibration circuits span the **whole device width** (e.g. 127+ qubits). Check this is acceptable on real hardware and within the free-plan QPU time budget; consider calibrating only a candidate subset if not.
- `get_backend` uses `QiskitRuntimeService(channel="ibm_quantum_platform", token=...)`. IBM's platform/channel naming and the need for an **instance (CRN)** may differ from what is coded; this is the most likely first failure on a real run.
- ZNE uses simple linear extrapolation over factors 1/3/5; with noisy data it can overshoot (clipped to [0,1]).
- Free-plan quota changes; do not assume limits. Keep default runs small (currently 2 jobs per run).

## Suggested next steps (in order)
1. **First real run.** Help the owner get the workflow green: verify auth (add optional `IBM_INSTANCE` support if needed), confirm `SamplerV2` result access via the `c` register works on real devices, confirm `translate_only` keeps the physical layout intact, and check QPU seconds used. Fix whatever breaks; add a regression test for each fix where possible.
2. After the first real data lands: run `qpu-weather aggregate`, check the dashboard renders it, and update the README status line.
3. Measure 2-qubit gate error directly (e.g. interleaved/repeated CX-or-ECR decay), and use it instead of vendor values in `layout.py`.
4. Add dynamical decoupling and Pauli twirling to the mitigation comparison.
5. Per-qubit stability score over time on the dashboard; more devices.
6. Pin the repo on the owner's GitHub profile once there are real results; add a short results section (with real numbers only) to the README.

## Working style for this repo
- Keep dependencies minimal; the dashboard stays static and library-free.
- Add tests for new logic; tests must not need QPU access (use fake backends / Aer).
- Commit small and often. Do not commit anything under `data/simulated/`.
