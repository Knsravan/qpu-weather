"""Command line: `qpu-weather run` and `qpu-weather aggregate`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .aggregate import build_history
from .backend import get_backend
from .experiment import run_experiment


def cmd_run(args) -> int:
    handle = get_backend(args.backend, simulate=args.simulate)
    print(f"backend: {handle.name} (simulated={handle.simulated})")
    result = run_experiment(
        handle, shots=args.shots, cal_shots=args.cal_shots, chain_len=args.chain_len
    )
    sub = "simulated" if handle.simulated else "runs"
    out_dir = Path(args.data_dir) / sub
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = result["timestamp_utc"].replace(":", "").replace("-", "")
    out = out_dir / f"{stamp}_{handle.name}.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"saved {out}")
    for r in result["results"]:
        s = r["scores"]
        print(
            f"{r['layout']:>5} {r['benchmark']:>6} chain={r['chain']} "
            + " ".join(f"{m}={s[m]:.3f}" for m in result["methods"])
        )
    return 0


def cmd_aggregate(args) -> int:
    sub = "simulated" if args.include_simulated else "runs"
    n = build_history(
        Path(args.data_dir) / sub, Path(args.out), include_simulated=args.include_simulated
    )
    print(f"wrote {args.out} with {n} run(s)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="qpu-weather", description=__doc__)
    sp = p.add_subparsers(dest="cmd", required=True)

    r = sp.add_parser("run", help="run today's experiment")
    r.add_argument("--backend", help="IBM backend name (default: least busy)")
    r.add_argument("--simulate", action="store_true", help="local noisy simulator (dev only)")
    r.add_argument("--shots", type=int, default=4000)
    r.add_argument("--cal-shots", type=int, default=2000)
    r.add_argument("--chain-len", type=int, default=5)
    r.add_argument("--data-dir", default="data")
    r.set_defaults(fn=cmd_run)

    a = sp.add_parser("aggregate", help="build docs/data/history.json for the dashboard")
    a.add_argument("--data-dir", default="data")
    a.add_argument("--out", default="docs/data/history.json")
    a.add_argument("--include-simulated", action="store_true")
    a.set_defaults(fn=cmd_aggregate)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
