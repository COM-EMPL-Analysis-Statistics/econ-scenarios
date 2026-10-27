"""Three sets of 2030 results, as a CSV and one figure per outcome.

    uv run python european_values/output/compare_scenarios.py

The sets:
    us          "US Economy": the paper as published, US economy and US scenarios (the code's defaults)
    us_on_eu    "EU Economy w. US Scenarios": the paper's three scenarios run on the EU economy:
                every Calibration.* parameter with an EU value in calibration_parameters.yaml
                (Sections A and D, plus the 2026 anchors m_anchor and d_anchor and the wage
                stickiness xi), the Scenario.* values (m_2030, d_2030, a, psi, rho, mu, theta_H)
                left at the paper's
    eu          "EU Economy w. EMPL Scenarios": EU economy, EU scenarios (load("eu"))

Writes, beside this script:
    results_2030.csv     one row per (set, scenario) with every readout row of Table 3
    parameters.csv       every parameter with an EU value: US value, EU value, and which sets use it
    figures/<outcome>.png   one figure per outcome in PANELS, the three sets as three lines
"""

from __future__ import annotations

import csv
import dataclasses
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from load_params import SCENARIO_NAMES, _spec, load, overrides  # noqa: E402
from econ_scenarios import SCENARIOS, Calibration, readout, simulate  # noqa: E402

matplotlib.use("Agg")

SETS = {
    "us": "US Economy",
    "us_on_eu": "EU Economy w. US Scenarios",
    "eu": "EU Economy w. EMPL Scenarios",
}
# EC corporate colours: the benchmark in grey, the hybrid in EC orange, the EU in EC blue.
COLORS = {"us": "#8C8C8C", "us_on_eu": "#FF712C", "eu": "#003399"}

# outcome: (title, y label, value at 'no AI'; None leaves the point out)
PANELS = {
    "gdp": ("GDP", "% vs no-AI", 0.0),
    "wage_avg": ("Average wage", "% vs no-AI", 0.0),
    "wage_C": ("Cognitive wage", "% vs no-AI", 0.0),
    "wage_N": ("Other wage", "% vs no-AI", 0.0),
    "gdp_growth": ("GDP growth", "% / yr", None),
    "net_return": ("Net return to capital", "% / yr", None),
    "labor_share": ("Labor share", "pp vs no-AI", 0.0),
    "employment_C": ("Cognitive employment", "% since mid-2026", None),
    "unemployment_C": ("Cognitive unemployment", "%", None),
    "unemployment": ("Unemployment", "%", None),
}
X_LABELS = ["no AI", *SCENARIO_NAMES]

# Drivers of the two gaps at the extreme scenario, as two-sided arrows with short labels:
# (economy gap, grey to orange: US to EU economy under the paper's scenarios;
#  scenario gap, orange to blue: the paper's scenarios to ours on the EU economy).
# From switching one parameter at a time in 2030. Economy gap: the cognitive wage stickiness
# (0.5 to 0.7) leads everywhere, the vacancy-filling rate (0.65 to 0.45) second; the labour
# share gap is nil once measured as a change. Scenario gap: adoption 2030 leads for GDP,
# unemployment and employment, new tasks for the cognitive wage. None skips that arrow.
DRIVERS = {
    "gdp": ("stickier wages,\nslower hiring", "lower\nadoption"),
    "unemployment": ("stickier wages,\nslower hiring", "lower adoption,\nmore new tasks"),
    "wage_C": ("stickier\nwages", "more new tasks,\nless automation"),
    "employment_C": ("stickier\nwages", "lower adoption,\nmore new tasks"),
    "labor_share": (None, "lower adoption,\nmore new tasks"),
}


def load_set(name: str):
    """(Calibration, {scenario: Scenario}) of one set."""
    if name == "us_on_eu":
        cal_kw, _ = overrides("eu")
        return Calibration(**cal_kw), dict(SCENARIOS)
    return load(name)


def results() -> list[dict[str, object]]:
    rows = []
    for name in SETS:
        cal, scenarios = load_set(name)
        for s in SCENARIO_NAMES:
            rd = readout(simulate(scenarios[s], cal))
            # Labour share against the no-AI path, on which it stays at its base-period value.
            rd["labor_share_level"] = rd["labor_share"]
            rd["labor_share"] = rd["labor_share"] - 100.0 * cal.s_L
            rows.append({"set": name, "set_label": SETS[name], "scenario": s, **rd})
    return rows


def parameters() -> list[dict[str, object]]:
    """Every YAML parameter with an EU value: US and EU values and the side it sits on."""
    rows = []
    for pid, p in _spec().items():
        eu = p.get("eu", {}).get("value")
        code = p.get("code") or ""
        if eu is None or not code:
            continue
        side = "scenario" if code.startswith("Scenario.") else "economy"
        rows.append({
            "id": pid,
            "symbol": p.get("symbol", ""),
            "section": p.get("section", ""),
            "side": side,
            "us_value": _fmt(p.get("us_value")),
            "eu_value": _fmt(eu),
            "in_us_on_eu": "EU" if side == "economy" else "US",
        })
    return rows


def _fmt(v: object) -> str:
    if isinstance(v, dict):
        return "/".join(str(x) for x in v.values())
    return "" if v is None else str(v)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _label_positions(vals: dict[str, float], span: float) -> list[tuple]:
    """Where each point's value label goes at one x position.

    Returns (set name or None for a shared black label, y, text, offset in points, ha, va).
    Points closer than 18% of the plotted range form a cluster. Within a cluster, points that
    round to the same number share one label (black when it stands for several series). A lone
    label goes above its point; in a cluster the top label goes above, the bottom one below, and
    any in between to the right.
    """
    thr = 0.18 * span
    names = sorted(vals, key=vals.__getitem__)
    clusters: list[list[str]] = [[names[0]]]
    for a, b in zip(names, names[1:]):
        if vals[b] - vals[a] < thr:
            clusters[-1].append(b)
        else:
            clusters.append([b])
    out = []
    for cl in clusters:
        groups: list[tuple[str, list[str]]] = []  # (rounded text, series) in rising order
        for n in cl:
            text = _whole(vals[n])
            if groups and groups[-1][0] == text:
                groups[-1][1].append(n)
            else:
                groups.append((text, [n]))
        for k, (text, members) in enumerate(groups):
            owner = members[0] if len(members) == 1 else None
            ys = [vals[n] for n in members]
            if k == len(groups) - 1:
                out.append((owner, max(ys), text, (0, 9), "center", "bottom"))
            elif k == 0:
                out.append((owner, min(ys), text, (0, -9), "center", "top"))
            else:
                out.append((owner, sum(ys) / len(ys), text, (11, 0), "left", "center"))
    return out


def _whole(y: float) -> str:
    """A whole number as text, without a '-0'."""
    text = f"{y:.0f}"
    return "0" if text == "-0" else text


def figure(outcome: str, rows: list[dict[str, object]], out: Path) -> None:
    """One outcome, styled for a slide: white background, whole numbers, legend below, no title
    (the slide carries it)."""
    from matplotlib.ticker import MaxNLocator

    _, ylabel, no_ai = PANELS[outcome]
    plt.rcParams["font.family"] = "Arial"
    fig, ax = plt.subplots(figsize=(11, 4.4), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
        spine.set_color("#bfbfbf")
    ax.grid(True, axis="y", color="#e6e6e6", linewidth=0.8)
    ax.set_axisbelow(True)
    if no_ai is not None:
        ax.axhline(0, color="#404040", linestyle="--", linewidth=1)

    # Change panels start from a 'no AI' point at zero; level panels show the three scenarios only.
    labels = X_LABELS if no_ai is not None else X_LABELS[1:]
    xs = list(range(len(labels)))
    series: dict[str, list[float]] = {}
    for name, label in SETS.items():
        ys = [r[outcome] for r in rows if r["set"] == name]
        if no_ai is not None:
            ys = [no_ai, *ys]
        series[name] = ys
        ax.plot(xs, ys, color=COLORS[name], linewidth=2.5, marker="o", markersize=9,
                markeredgecolor="white", markeredgewidth=1.5, label=label, zorder=3)

    # Value labels: none at the 'no AI' point; bold in the series colour; above the point unless
    # another point sits just above it (then below, or beside if crowded on both sides); one black
    # label when the points coincide and round to the same number.
    span = max(max(v) for v in series.values()) - min(min(v) for v in series.values()) or 1.0
    for i, x in enumerate(xs):
        if no_ai is not None and i == 0:
            continue
        for name, y, text, xytext, ha, va in _label_positions({n: v[i] for n, v in series.items()}, span):
            ax.annotate(text, (x, y), textcoords="offset points", xytext=xytext, ha=ha, va=va,
                        fontsize=11, fontweight="bold", color="#202020" if name is None else COLORS[name],
                        zorder=4, bbox={"boxstyle": "round,pad=0.15", "facecolor": "white",
                                        "edgecolor": "none", "alpha": 0.9})

    # Driver arrows: at the extreme point, to the right of the value labels, one per gap.
    right = len(labels) - 0.6
    if outcome in DRIVERS:
        x = xs[-1] + 0.28
        ends = [series[n][-1] for n in ("us", "us_on_eu", "eu")]
        # The two spans share the orange point. When it lies between the other two they stack on
        # one vertical; when it is the outer point they overlap, so the second arrow moves right.
        nested = not min(ends[0], ends[2]) <= ends[1] <= max(ends[0], ends[2])
        for k, ((lo, hi), text) in enumerate(zip(zip(ends, ends[1:]), DRIVERS[outcome])):
            if text is None:
                continue
            if k == 1 and nested and DRIVERS[outcome][0] is not None:
                x += 0.6
                right += 0.6
            ax.annotate("", (x, max(lo, hi)), (x, min(lo, hi)), zorder=4,
                        arrowprops={"arrowstyle": "<->", "color": "#404040", "linewidth": 1.4,
                                    "shrinkA": 2, "shrinkB": 2})
            ax.text(x + 0.05, (lo + hi) / 2, text, ha="left", va="center", fontsize=9,
                    style="italic", color="#404040", linespacing=1.1, zorder=4,
                    bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "none",
                          "alpha": 0.9})
        right += 0.55

    ax.set_xticks(xs, labels, fontsize=12)
    ax.set_xlim(-0.4, right)
    ax.margins(y=0.15)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    ax.set_ylabel(ylabel, fontsize=11, color="#404040")
    ax.tick_params(axis="y", length=0, labelsize=10, colors="#404040")
    ax.tick_params(axis="x", length=0)
    ax.legend(frameon=False, fontsize=11, loc="best")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def main() -> None:
    rows = results()
    write_csv(HERE / "results_2030.csv", rows)
    write_csv(HERE / "parameters.csv", parameters())
    figs = HERE / "figures"
    figs.mkdir(exist_ok=True)
    for outcome in PANELS:
        figure(outcome, rows, figs / f"{outcome}.png")

    width = max(len(v) for v in SETS.values()) + 2
    for s in SCENARIO_NAMES:
        print(f"\n=== {s}, 2030 ===")
        print(f"{'':<{width}}" + "".join(f"{k:>16}" for k in PANELS))
        for r in rows:
            if r["scenario"] == s:
                print(f"{r['set_label']:<{width}}" + "".join(f"{r[k]:>16.2f}" for k in PANELS))
    print(f"\nwrote results_2030.csv ({len(rows)} rows), parameters.csv, figures/ ({len(PANELS)} png)")


if __name__ == "__main__":
    main()
