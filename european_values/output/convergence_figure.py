"""Closing the adoption gap: several 2030 outcomes on one slide.

    uv run python european_values/output/convergence_figure.py

Three sets, four panels in one row:
    us           "US Economy": the paper as published (grey, reference)
    eu           "EU Economy w. EMPL Scenarios": the baseline (blue)
    eu_converge  "EU w. US adoption by 2030": the baseline with d_2030 at the paper's
                 0.2 / 0.4 / 0.6 instead of 0.12 / 0.24 / 0.36, i.e. experiments/d_2030_convergence.yaml
                 (dashed blue). Everything else, including today's anchor d_anchor = 0.06, stays EU.

Writes, beside this script: results_convergence.csv and figures/convergence.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from compare_scenarios import COLORS, PANELS, _label_positions, load_set, write_csv  # noqa: E402
from load_params import SCENARIO_NAMES, load_experiment  # noqa: E402
from econ_scenarios import readout, simulate  # noqa: E402

matplotlib.use("Agg")

EXPERIMENT = HERE.parent / "experiments" / "d_2030_convergence.yaml"
SETS = {
    "us": "US Economy",
    "eu": "EU Economy w. EMPL Scenarios",
    "eu_converge": "EU Economy w. US Adoption",
}
STYLE = {
    "us": {"color": COLORS["us"], "linestyle": "-"},
    "eu": {"color": COLORS["eu"], "linestyle": "-"},
    "eu_converge": {"color": COLORS["eu"], "linestyle": (0, (4, 2))},
}
OUTCOMES = ("gdp", "unemployment", "wage_C", "employment_C")


def results() -> list[dict[str, object]]:
    sets = {name: load_set(name) for name in ("us", "eu")}
    (run,) = load_experiment(EXPERIMENT)
    sets["eu_converge"] = (run.calibration, run.scenarios)
    rows = []
    for name, (cal, scenarios) in sets.items():
        for s in SCENARIO_NAMES:
            rd = readout(simulate(scenarios[s], cal))
            rd["labor_share_level"] = rd["labor_share"]
            rd["labor_share"] = rd["labor_share"] - 100.0 * cal.s_L
            rows.append({"set": name, "set_label": SETS[name], "scenario": s, **rd})
    return rows


def figure(rows: list[dict[str, object]], out: Path) -> None:
    plt.rcParams["font.family"] = "Arial"
    fig, axes = plt.subplots(1, len(OUTCOMES), figsize=(11, 4.4), dpi=200)
    fig.patch.set_facecolor("white")
    xs = list(range(len(SCENARIO_NAMES)))
    for ax, outcome in zip(axes, OUTCOMES):
        title, ylabel, _ = PANELS[outcome]
        ax.set_facecolor("white")
        for side, spine in ax.spines.items():
            spine.set_visible(side == "bottom")
            spine.set_color("#bfbfbf")
        ax.grid(True, axis="y", color="#e6e6e6", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.axhline(0, color="#404040", linestyle="--", linewidth=1)

        series: dict[str, list[float]] = {}
        for name, label in SETS.items():
            ys = [r[outcome] for r in rows if r["set"] == name]
            series[name] = ys
            ax.plot(xs, ys, linewidth=2.5, marker="o", markersize=8, markeredgecolor="white",
                    markeredgewidth=1.5, label=label, zorder=3, **STYLE[name])

        span = max(max(v) for v in series.values()) - min(min(v) for v in series.values()) or 1.0
        for i, x in enumerate(xs):
            for name, y, text, xytext, ha, va in _label_positions({n: v[i] for n, v in series.items()}, span):
                ax.annotate(text, (x, y), textcoords="offset points", xytext=xytext, ha=ha, va=va,
                            fontsize=10, fontweight="bold",
                            color="#202020" if name is None else STYLE[name]["color"], zorder=4,
                            bbox={"boxstyle": "round,pad=0.15", "facecolor": "white",
                                  "edgecolor": "none", "alpha": 0.9})

        ax.set_title(title, fontsize=12, color="#202020", pad=10)
        ax.set_xticks(xs, SCENARIO_NAMES, fontsize=10)
        ax.set_xlim(-0.45, len(xs) - 0.55)
        ax.margins(y=0.2)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
        ax.set_ylabel(ylabel, fontsize=10, color="#404040")
        ax.tick_params(axis="y", length=0, labelsize=9, colors="#404040")
        ax.tick_params(axis="x", length=0)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=11, loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, 0.03), handlelength=4, columnspacing=2.5)
    fig.text(0.5, 0.01, "EU w. US Adoption: our scenarios for capability, automation and new tasks; "
             "only adoption in 2030 raised to the paper's 20 / 40 / 60%", ha="center", va="bottom",
             fontsize=10, color="#7f7f7f", style="italic")
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def main() -> None:
    rows = results()
    write_csv(HERE / "results_convergence.csv", rows)
    figure(rows, HERE / "figures" / "convergence.png")
    width = max(len(v) for v in SETS.values()) + 2
    for s in SCENARIO_NAMES:
        print(f"\n=== {s}, 2030 ===")
        print(f"{'':<{width}}" + "".join(f"{k:>16}" for k in OUTCOMES))
        for r in rows:
            if r["scenario"] == s:
                print(f"{r['set_label']:<{width}}" + "".join(f"{r[k]:>16.2f}" for k in OUTCOMES))
    print("\nwrote results_convergence.csv, figures/convergence.png")


if __name__ == "__main__":
    main()
