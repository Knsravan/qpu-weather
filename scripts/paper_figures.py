"""Regenerate the paper's figures from the real run files in data/runs/.

    pip install -e ".[paper]"
    python scripts/paper_figures.py --out paper/figures

Every number plotted comes from data/runs/*.json (real hardware only; simulated
runs are skipped). Nothing here is hand-entered.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch  # noqa: E402

from qpu_weather.layout import chain_cost, reported_qubit_cost  # noqa: E402
from qpu_weather.mitigation import zne_valid  # noqa: E402

OURS, NAIVE, VENDOR = "#3b63e6", "#8a8f99", "#c0873a"
BAD, INK, BAND = "#d64545", "#1f2430", "#e8eefc"
DEVICE_MARK = {"ibm_fez": "o", "ibm_kingston": "s"}
LAYOUT_STYLE = {
    "best": dict(color=OURS, hatch="///", label="selected (ours)"),
    "vendor": dict(color=VENDOR, hatch="xx", label="vendor-guided"),
    "naive": dict(color=NAIVE, hatch="..", label="first five qubits"),
}
METHODS = ("raw", "readout", "zne", "readout+zne")
METHOD_LABEL = {"raw": "raw", "readout": "readout", "zne": "ZNE", "readout+zne": "readout\n+ ZNE"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.grid": True, "grid.color": "#d9dce3", "grid.linewidth": 0.6, "legend.frameon": False,
    "hatch.linewidth": 0.8, "savefig.dpi": 300, "savefig.bbox": "tight",
})


# ------------------------------------------------------------------ data
def load_runs(runs_dir="data/runs"):
    runs = []
    for f in sorted(glob.glob(f"{runs_dir}/*.json")):
        r = json.loads(Path(f).read_text())
        if not r.get("simulated"):
            runs.append(r)
    runs.sort(key=lambda r: r["timestamp_utc"])
    for i, r in enumerate(runs, 1):
        r["_label"] = f"run {i}\n{r['timestamp_utc'][5:10]}\n{r['backend'].replace('ibm_', '')}"
        r["_n"] = i
    return runs


def arr(r, key):
    return np.array([q[key] for q in r["calibration"]["qubits"]], dtype=float)


def readout_se(r):
    p01, p10, n = arr(r, "p01"), arr(r, "p10"), r["calibration"]["shots"]
    return np.sqrt((p01 * (1 - p01) + p10 * (1 - p10)) / (4 * n))


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def edges(r):
    return r["calibration"].get("edges", [])


def edge_maps(r):
    measured = {(min(e["a"], e["b"]), max(e["a"], e["b"])): e["gate_error_2q"] for e in edges(r)}
    vendor = {(min(e["a"], e["b"]), max(e["a"], e["b"])): e["reported_gate_error_2q"] for e in edges(r)}
    return measured, vendor


def result(r, layout, bench):
    return next(x for x in r["results"] if x["layout"] == layout and x["benchmark"] == bench)


def zne_ok(res):
    s = res["scores"]
    if "zne_ok" in s:
        return s["zne_ok"]
    f = sorted(s["raw_by_factor"], key=int)
    return zne_valid([int(k) for k in f], [s["raw_by_factor"][k] for k in f])


def panel(ax, letter):
    ax.text(-0.08, 1.04, f"({letter})", transform=ax.transAxes, fontweight="bold", fontsize=12)


def save(fig, out, name):
    fig.savefig(out / name)
    plt.close(fig)
    print("wrote", out / name)


# ------------------------------------------------------------------ figures
def fig_architecture(out):
    fig, ax = plt.subplots(figsize=(10.5, 3.9))
    ax.set_xlim(0, 100), ax.set_ylim(0, 38), ax.axis("off")
    lanes = [(26, 11, "#e6ebfd", "GitHub Actions (cloud runner)"),
             (13.5, 11, "#fdefdc", "IBM Quantum (real hardware)"),
             (1, 11, "#e3f3ec", "Repository and web")]
    for y, h, c, t in lanes:
        ax.add_patch(FancyBboxPatch((0.5, y), 99, h, boxstyle="round,pad=0,rounding_size=1.2", fc=c, ec="none"))
        ax.text(1.5, y + 0.9, t, fontweight="bold", fontsize=10.5, color=INK)

    def box(x, y, w, h, text, ec=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc="white", ec=ec, lw=1.4))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9.6, linespacing=1.25)
        return (x, y, w, h)

    def arrow(p, q, rad=0.0):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11, lw=1.3, color=INK,
                                     connectionstyle=f"arc3,rad={rad}"))

    a = box(2, 29.5, 14, 6.3, "Monday 03:17 UTC\nor manual run")
    b = box(20, 29.5, 17, 6.3, "Guards: time left > 0\nqueue limit 30 min / job\nworkflow limit 90 min")
    c = box(43, 29.5, 22, 6.3, "Choose 3 chains (Eq. 5)\nselected · vendor-guided\n· first five")
    d = box(71, 29.5, 27, 6.3, "Score 4 methods on the same shots\nZNE validity check (Eq. 9)\nbootstrap 95% intervals (Eq. 10)")
    j1 = box(20, 16.3, 17, 6.6, "Job 1: calibration\n10 circuits × 2000 shots\nreadout, 1q, CZ decay", ec=VENDOR)
    j2 = box(43, 16.3, 22, 6.6, "Job 2: benchmarks\n18 circuits × 4000 shots\n3 chains, 2 circuits, λ = 1, 3, 5", ec=VENDOR)
    f = box(43, 3.3, 22, 6.6, "data/runs/*.json\nscores, intervals, raw counts")
    g = box(71, 3.3, 27, 6.6, "history.json → static dashboard\n(GitHub Pages, per device)", ec="#1a8a5a")
    arrow((16.3, 32.6), (19.7, 32.6))
    arrow((28.5, 29.2), (28.5, 23.2))
    arrow((37.3, 19.6), (44, 29.2), rad=-0.25)
    arrow((54, 29.2), (54, 23.2))
    arrow((65.3, 19.6), (75, 29.2), rad=-0.25)
    arrow((84.5, 29.2), (60, 10.2), rad=0.0)
    arrow((65.3, 6.6), (70.7, 6.6))
    save(fig, out, "fig09_architecture.png")


def fig_readout(runs, out):
    r = runs[-1]
    m, p, se = arr(r, "readout_error") * 100, arr(r, "reported_readout_error") * 100, readout_se(r) * 100
    far = np.abs(m - p) > 3 * se
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.1), gridspec_kw={"width_ratios": [1.05, 1]})
    lo, hi = 0.1, 60
    xs = np.array([lo, hi])
    a.fill_between(xs, xs / 2, xs * 2, color=BAND, zorder=0)
    a.plot(xs, xs, color=INK, lw=1.2)
    a.scatter(p[~far], m[~far], s=22, facecolors="none", edgecolors=OURS, lw=1.1, label="within 3 SE")
    a.scatter(p[far], m[far], s=22, color=BAD, label=f"beyond 3 SE ($n={far.sum()}$)")
    a.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi),
          xlabel="published readout error (%)", ylabel="measured readout error (%)")
    worst = int(np.argmax(m / p))
    a.annotate(f"q{worst}", (p[worst], m[worst]), xytext=(p[worst] * 0.35, m[worst] * 2.2),
               arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))
    a.legend(loc="lower right")
    panel(a, "a")

    for i, rr in enumerate(runs):
        ratio = arr(rr, "readout_error") / arr(rr, "reported_readout_error")
        q1, med, q3 = np.percentile(ratio, [25, 50, 75])
        col = OURS if rr["backend"] == "ibm_fez" else "#8a5cf6"
        b.vlines(i, q1, q3, color=col, lw=6, alpha=0.35)
        b.plot(i, med, DEVICE_MARK[rr["backend"]], color=col, ms=9)
        b.text(i + 0.1, med + 0.035, f"{med:.2f}", va="center", fontsize=9.5)
    b.axhline(1, color=INK, lw=1)
    b.set(xticks=range(len(runs)), xticklabels=[r["_label"] for r in runs], ylim=(0.6, 1.4),
          ylabel="measured / published readout error", xlim=(-0.5, len(runs) - 0.4))
    b.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=OURS, label="ibm_fez: median, IQR bar"),
                      plt.Line2D([], [], marker="s", ls="", color="#8a5cf6", label="ibm_kingston")], loc="upper left")
    panel(b, "b")
    save(fig, out, "fig10_readout_four_runs.png")


def fig_datasheet_over_runs(runs, out):
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.8))
    x = np.arange(len(runs))
    series = [("readout", lambda r: arr(r, "readout_error"), lambda r: arr(r, "reported_readout_error"), OURS, "o"),
              ("1q sequence", lambda r: arr(r, "gate_error_1q"), lambda r: arr(r, "reported_gate_error_1q"), VENDOR, "D"),
              ("CZ decay", lambda r: np.array([e["gate_error_2q"] for e in edges(r)]),
               lambda r: np.array([e["reported_gate_error_2q"] for e in edges(r)]), "#2a9d6f", "s")]
    for name, mf, pf, col, mk in series:
        med, rho, xs = [], [], []
        for i, r in enumerate(runs):
            mm, pp = mf(r), pf(r)
            if mm.size == 0:
                continue
            ok = pp > 0
            med.append(np.median(mm[ok] / pp[ok]))
            rho.append(spearman(mm, pp))
            xs.append(i)
        a.plot(xs, med, marker=mk, color=col, lw=1.4, label=name)
        for xi, v in zip(xs, med):
            a.text(xi + 0.08, v * 1.08, f"{v:.1f}×" if v > 1.5 else f"{v:.2f}×", fontsize=9, color=col)
        b.plot(xs, rho, marker=mk, color=col, lw=1.4, label=name)
    a.axhline(1, color=INK, lw=1)
    a.set(yscale="log", xticks=x, xticklabels=[r["_label"] for r in runs], ylim=(0.5, 90), xlim=(-0.3, len(runs) - 0.5),
          ylabel="median measured / published")
    a.legend(loc="upper center", ncol=3, fontsize=9.5)
    b.axhline(0, color=INK, lw=1)
    b.set(xticks=x, xticklabels=[r["_label"] for r in runs], ylim=(-0.3, 1.0), ylabel="Spearman ρ, measured vs published")
    panel(a, "a"), panel(b, "b")
    save(fig, out, "fig11_datasheet_over_runs.png")


def fig_repeatability(runs, out):
    fez = [r for r in runs if r["backend"] == "ibm_fez"]
    if len(fez) < 3:
        return
    r1, r2, r4 = fez[0], fez[1], fez[-1]
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.8))
    pairs = [(r1, r2, "readout_error", "7 minutes apart"), (r2, r4, "readout_error", "four days apart"),
             (r2, r4, "gate_error_1q", "four days apart")]
    for ax, (u, v, key, when), letter in zip(axs, pairs, "abc"):
        x, y = arr(u, key) * 100, arr(v, key) * 100
        lo, hi = max(min(x.min(), y.min()) * 0.8, 1e-3), max(x.max(), y.max()) * 1.25
        ax.plot([lo, hi], [lo, hi], color=INK, lw=1)
        ax.scatter(x, y, s=16, facecolors="none", edgecolors=OURS if key == "readout_error" else VENDOR, lw=1)
        nm = "readout" if key == "readout_error" else "1q sequence"
        ax.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi),
               xlabel=f"{nm} error, {u['timestamp_utc'][5:16].replace('T', ' ')} (%)",
               ylabel=f"{nm} error, {v['timestamp_utc'][5:16].replace('T', ' ')} (%)")
        ax.set_title(f"{nm}, {when}: Spearman {spearman(x, y):.2f}", fontsize=10.5)
        panel(ax, letter)
    fig.tight_layout()
    save(fig, out, "fig12_repeatability_drift.png")


def fig_three_chains(runs, out):
    r = next((x for x in reversed(runs) if "vendor" in x["layouts"]), None)
    if r is None:
        return
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
    for ax, method, letter in zip(axs, ("raw", "readout+zne"), "ab"):
        for bi, bench in enumerate(("ghz", "mirror")):
            for li, lay in enumerate(("best", "vendor", "naive")):
                s = result(r, lay, bench)["scores"]
                v, ci = s[method], (s.get("ci95") or {}).get(method)
                x = bi * 3.6 + li
                st = LAYOUT_STYLE[lay]
                ax.bar(x, v, width=0.85, color=st["color"], alpha=0.55, hatch=st["hatch"], edgecolor=st["color"],
                       label=st["label"] if bi == 0 else None)
                if ci:
                    ax.errorbar(x, v, yerr=[[v - ci[0]], [ci[1] - v]], color=INK, capsize=4, lw=1.1)
                ax.text(x, (ci[1] if ci else v) + 0.006, f"{v:.3f}", ha="center", fontsize=8.8)
        ax.set(xticks=[1, 4.6], xticklabels=["GHZ", "mirror"], ylim=(0.78, 1.02),
               title=f"{'raw score' if method == 'raw' else 'readout + ZNE'} (95% bootstrap interval)")
        panel(ax, letter)
    axs[0].set_ylabel("probability of the correct output")
    fig.legend(*axs[0].get_legend_handles_labels(), loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.07))
    save(fig, out, "fig13_three_chains.png")


def fig_cost_breakdown(runs, out):
    r = next((x for x in reversed(runs) if "vendor" in x["layouts"]), None)
    if r is None:
        return
    q = {x["qubit"]: x for x in r["calibration"]["qubits"]}
    meas_e, vend_e = edge_maps(r)
    vq = reported_qubit_cost(r["calibration"]["qubits"])

    def parts(chain, measured):
        ro = sum(q[i]["readout_error" if measured else "reported_readout_error"] for i in chain)
        g = sum(3 * q[i]["gate_error_1q" if measured else "reported_gate_error_1q"] for i in chain)
        em = meas_e if measured else vend_e
        cz = sum(em.get(tuple(sorted(p)), 0.05) for p in zip(chain, chain[1:]))
        return ro, g, cz

    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    names = [("best", "selected\n(ours)"), ("vendor", "vendor-guided\n(on hardware)"), ("naive", "first five\nqubits")]
    cols = [(OURS, "", "readout"), ("#2a9d6f", "///", "3 × 1q sequence"), (VENDOR, "..", "CZ decay")]
    yt, yl = [], []
    for i, (lay, lab) in enumerate(names):
        chain = r["layouts"][lay]["chain"]
        for j, measured in enumerate((False, True)):
            y = i * 3 + (1 - j)
            left = 0
            for (c, h, _), w in zip(cols, parts(chain, measured)):
                ax.barh(y, w, left=left, color=c, alpha=0.75 if measured else 0.3, hatch=h, edgecolor=c, height=0.8)
                left += w
            ax.text(left + 0.004, y, f"{left:.3f}", va="center", fontsize=9.5)
            ax.text(-0.004, y, "measured" if measured else "published", ha="right", va="center", fontsize=9,
                    color=INK if measured else "#7b8496")
        yt.append(i * 3 + 0.5), yl.append(lab)
        assert abs(chain_cost(chain, {k: v["readout_error"] + 3 * v["gate_error_1q"] for k, v in q.items()}, meas_e)
                   - sum(parts(chain, True))) < 1e-9
        assert abs(chain_cost(chain, vq, vend_e) - sum(parts(chain, False))) < 1e-9
    ax.set_yticks(yt, yl)
    ax.tick_params(axis="y", pad=62, length=0)
    ax.invert_yaxis()
    ax.set_xlabel("chain cost, Eq. (5)")
    ax.legend(handles=[Patch(facecolor=c, alpha=0.75, hatch=h, edgecolor=c, label=l) for c, h, l in cols], loc="upper right")
    ax.grid(axis="y", visible=False)
    save(fig, out, "fig14_cost_breakdown.png")


def fig_zne_check(runs, out):
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.0), gridspec_kw={"width_ratios": [1.25, 1]})
    lam = np.array([1, 3, 5])
    slopes = []
    for r in runs:
        for res in r["results"]:
            s = res["scores"]["raw_by_factor"]
            y = np.array([s["1"], s["3"], s["5"]])
            ok = zne_ok(res)
            col = BAD if not ok else LAYOUT_STYLE[res["layout"]]["color"]
            a.plot(lam, y, marker=DEVICE_MARK[r["backend"]], color=col, lw=2.2 if not ok else 1.0,
                   alpha=1 if not ok else 0.6, ls="-" if res["benchmark"] == "ghz" else "--", ms=4.5)
            slope = np.polyfit(lam, y, 1)[0]
            slopes.append((slope, ok, r["_n"], res["layout"], res["benchmark"]))
    a.set(xticks=lam, xlabel="noise amplification factor λ", ylabel="raw score", ylim=(0.3, 1.0))
    a.legend(handles=[plt.Line2D([], [], color=OURS, label="selected"), plt.Line2D([], [], color=VENDOR, label="vendor-guided"),
                      plt.Line2D([], [], color=NAIVE, label="first five"),
                      plt.Line2D([], [], color=BAD, lw=2.2, label="rejected: score rose with noise"),
                      plt.Line2D([], [], color=INK, label="GHZ"), plt.Line2D([], [], color=INK, ls="--", label="mirror")],
             loc="lower left", fontsize=9, ncol=2)
    panel(a, "a")
    slopes.sort()
    for i, (sl, ok, n, lay, bench) in enumerate(slopes):
        b.plot(sl, i, "o", color=BAD if not ok else LAYOUT_STYLE[lay]["color"], ms=6)
        if not ok:
            b.text(sl - 0.002, i, f"run {n}, {LAYOUT_STYLE[lay]['label']}, {'GHZ' if bench == 'ghz' else bench}  ", ha="right", va="center", fontsize=8.8, color=BAD)
    b.axvline(0, color=INK, lw=1)
    b.set(yticks=[], xlabel="fitted slope b in s(λ) ≈ a + bλ", ylabel=f"all {len(slopes)} cases, sorted")
    panel(b, "b")
    save(fig, out, "fig15_zne_check.png")


def fig_mitigation_by_device(runs, out):
    devices = sorted({r["backend"] for r in runs}, key=lambda d: d != "ibm_fez")
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    width = 0.8 / len(devices)
    for di, dev in enumerate(devices):
        cases = [x for r in runs if r["backend"] == dev for x in r["results"] if x["layout"] == "best" and zne_ok(x)]
        errs = np.array([[100 * (1 - c["scores"][m]) for m in METHODS] for c in cases])
        mean = errs.mean(0)
        x = np.arange(len(METHODS)) + (di - (len(devices) - 1) / 2) * width
        col = OURS if dev == "ibm_fez" else "#8a5cf6"
        n_runs = len({r["timestamp_utc"] for r in runs if r["backend"] == dev})
        ax.bar(x, mean, width=width * 0.92, color=col, alpha=0.55, hatch="///" if di == 0 else "xx", edgecolor=col,
               label=f"{dev}: {n_runs} run(s), {len(cases)} cases")
        ax.errorbar(x, mean, yerr=[mean - errs.min(0), errs.max(0) - mean], fmt="none", color=INK, capsize=3, lw=1)
        for xi, v, top in zip(x, mean, errs.max(0)):
            ax.text(xi, top + 0.2, f"{v:.1f}", ha="center", fontsize=9.5, fontweight="bold")
    ax.set(xticks=range(len(METHODS)), xticklabels=[METHOD_LABEL[m] for m in METHODS], ylabel="wrong answers (%)")
    ax.legend(loc="upper right")
    save(fig, out, "fig16_mitigation_by_device.png")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", default="data/runs")
    ap.add_argument("--out", default="paper/figures")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    runs = load_runs(a.runs)
    if not runs:
        raise SystemExit("no real runs found")
    fig_architecture(out)
    fig_readout(runs, out)
    fig_datasheet_over_runs(runs, out)
    fig_repeatability(runs, out)
    fig_three_chains(runs, out)
    fig_cost_breakdown(runs, out)
    fig_zne_check(runs, out)
    fig_mitigation_by_device(runs, out)


if __name__ == "__main__":
    main()
