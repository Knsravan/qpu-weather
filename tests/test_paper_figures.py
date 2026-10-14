"""The paper's figure script must run on the real run files without hand-entered numbers."""

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

ROOT = Path(__file__).resolve().parents[1]


def test_paper_figures_build_from_run_files(tmp_path):
    spec = importlib.util.spec_from_file_location("paper_figures", ROOT / "scripts" / "paper_figures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main(["--runs", str(ROOT / "data" / "runs"), "--out", str(tmp_path)])
    made = sorted(p.name for p in tmp_path.glob("*.png"))
    assert "fig10_readout_four_runs.png" in made and "fig15_zne_check.png" in made
    assert all((tmp_path / n).stat().st_size > 10_000 for n in made)
