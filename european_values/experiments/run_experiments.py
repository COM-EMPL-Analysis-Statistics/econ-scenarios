"""Run every experiment file and tabulate the 2030 readouts against the baseline.

    uv run python european_values/experiments/run_experiments.py              # every *.yaml here
    uv run python european_values/experiments/run_experiments.py eps_table5    # one or more files

Writes results.csv beside this script, one row per (experiment, run, scenario) with the parameter
values of the run and every readout row, and prints a short comparison for the rows in SHOW.
The first block of the table is the untouched baseline of each base (eu, us) that the experiments
start from, so a run can be read against it.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from load_params import SCENARIO_NAMES, Run, load, load_experiment  # noqa: E402
from econ_scenarios import readout, simulate  # noqa: E402

SHOW = ("gdp", "wage_avg", "wage_C", "wage_N", "net_return", "labor_share", "employment_C", "unemployment")


def files(args: list[str]) -> list[Path]:
    if not args:
        return sorted(p for p in HERE.glob("*.yaml"))
    out = []
    for a in args:
        p = Path(a)
        if not p.exists():
            p = HERE / (a if a.endswith(".yaml") else a + ".yaml")
        out.append(p)
    return out


def main() -> None:
    runs: list[Run] = []
    for f in files(sys.argv[1:]):
        runs.extend(load_experiment(f))
    bases = sorted({r.base for r in runs}) or ["eu"]
    baseline = [Run("baseline", f"baseline ({b})", b, {}, *load(b)) for b in bases]

    records = []
    for run in baseline + runs:
        for s in SCENARIO_NAMES:
            rd = readout(simulate(run.scenarios[s], run.calibration))
            records.append({"experiment": run.experiment, "run": run.label, "base": run.base, "scenario": s,
                            **{f"param:{k}": v for k, v in run.point.items()}, **rd})

    param_cols = sorted({k for r in records for k in r if k.startswith("param:")})
    readout_cols = [k for k in records[0] if k not in ("experiment", "run", "base", "scenario") and not k.startswith("param:")]
    out = HERE / "results.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["experiment", "run", "base", "scenario", *param_cols, *readout_cols])
        w.writeheader()
        for r in records:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    width = max(len(r["run"]) for r in records) + 2
    for s in SCENARIO_NAMES:
        print(f"\n=== {s}, 2030 readout ===")
        print(f"{'':<{width}}" + "".join(f"{k:>13}" for k in SHOW))
        for r in records:
            if r["scenario"] == s:
                print(f"{r['run']:<{width}}" + "".join(f"{r[k]:>13.2f}" for k in SHOW))
    print(f"\nwrote {out.relative_to(HERE.parents[1])}: {len(records)} rows")


if __name__ == "__main__":
    main()
