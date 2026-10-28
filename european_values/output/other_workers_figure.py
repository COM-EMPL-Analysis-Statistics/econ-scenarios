"""Other (non-cognitive) workers: wage and employment in 2030, two panels on one slide.

    uv run python european_values/output/other_workers_figure.py

The three sets of compare_scenarios.py. AI acts only on cognitive work, so the other group gains
by construction: complementarity raises its wage, and displaced cognitive workers move into it.

Writes, beside this script: figures/other_workers.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from compare_scenarios import COLORS, PANELS, SETS, _label_positions, results  # noqa: E402
from load_params import SCENARIO_NAMES  # noqa: E402

matplotlib.use("Agg")

OUTCOMES = ("wage_N", "employment_N")


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
            ax.plot(xs, ys, color=COLORS[name], linewidth=2.5, marker="o", markersize=8,
                    markeredgecolor="white", markeredgewidth=1.5, label=label, zorder=3)

        span = max(max(v) for v in series.values()) - min(min(v) for v in series.values()) or 1.0
        for i, x in enumerate(xs):
            for name, y, text, xytext, ha, va in _label_positions({n: v[i] for n, v in series.items()}, span):
                ax.annotate(text, (x, y), textcoords="offset points", xytext=xytext, ha=ha, va=va,
                            fontsize=10, fontweight="bold",
                            color="#202020" if name is None else COLORS[name], zorder=4,
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
               bbox_to_anchor=(0.5, -0.02), columnspacing=2.5)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def main() -> None:
    figure(results(), HERE / "figures" / "other_workers.png")
    print("wrote figures/other_workers.png")


if __name__ == "__main__":
    main()
