"""Draw the 'What the model does' flow diagram (model_diagram.png) for the slide deck.

    uv run python european_values/presentation/make_diagram.py

One source box forks into the two channels of the model: AI assisting workers (share 1 - psi,
more output from the same workers) and AI replacing them (share psi, displaced workers search,
new tasks absorb some). Both channels feed the 2030 outcomes.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

matplotlib.use("Agg")

EC_BLUE = "#003399"
LIGHT_BLUE = "#4F7CC9"
EC_ORANGE = "#FF712C"
GREY = "#404040"
ARROW = "#8C8C8C"

W, H = 11.4, 4.4  # figure, in inches; wide and flat so the pptx content area shows it large
BW, BH = 2.1, 1.05  # box
GAP = 0.8  # between columns, wide enough for the elbow arrows to run between boxes
X = [0.3 + i * (BW + GAP) for i in range(4)]  # column left edges: source, branch, next, outcomes
Y_TOP, Y_BOT = 3.05, 0.3  # row bottom edges


def box(ax, x, y, title, color, *, note="", implies="", w=BW, h=BH):
    """A block with, underneath, a clarification in grey and an implication marked by an arrow."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.15",
                                facecolor=color, edgecolor="none"))
    ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", color="white",
            fontsize=12, fontweight="bold", linespacing=1.2)
    yy = y - 0.14
    if note:
        ax.text(x + w / 2, yy, note, ha="center", va="top", color="#7f7f7f", fontsize=10,
                style="italic")
        yy -= 0.24
    if implies:
        ax.text(x + w / 2, yy, "→ " + implies, ha="center", va="top", color=GREY, fontsize=10,
                fontweight="bold")


def arrow(ax, p, q):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=20, color=ARROW,
                                 linewidth=2, connectionstyle="arc3,rad=0"))


def elbow(ax, p, q):
    """Arrow from p to q with a horizontal-vertical-horizontal path."""
    xm = (p[0] + q[0]) / 2
    ax.plot([p[0], xm, xm], [p[1], p[1], q[1]], color=ARROW, linewidth=2, solid_capstyle="round")
    arrow(ax, (xm, q[1]), q)


def main() -> None:
    plt.rcParams["font.family"] = "Arial"
    fig, ax = plt.subplots(figsize=(W, H), dpi=200)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    # Source and outcome boxes, centred between the two rows.
    y_c = (Y_TOP + Y_BOT + BH) / 2 - BH / 2
    box(ax, X[0], y_c, "AI performs more\ncognitive tasks", EC_BLUE, note="capability × adoption")
    box(ax, X[3], y_c, "Outcomes in 2030", EC_ORANGE, note="GDP, wages, unemployment")

    # Top branch: assisting.
    box(ax, X[1], Y_TOP, "AI assists workers", LIGHT_BLUE, note="share 1 − ψ",
        implies="worker keeps the task,\ndoes it faster")
    box(ax, X[2], Y_TOP, "Same workers,\nmore output", LIGHT_BLUE,
        note="by the gain per task", implies="productivity and wages up")

    # Bottom branch: replacing.
    box(ax, X[1], Y_BOT, "AI replaces workers", EC_BLUE, note="share ψ",
        implies="task gets automated,\nfewer cognitive jobs")
    box(ax, X[2], Y_BOT, "Displaced workers\nlook for new jobs", EC_BLUE,
        note="new tasks absorb some (ρ)", implies="unemployment up during search")

    # Arrows: fork out of the source, along each row, and merge into the outcomes.
    src_r = (X[0] + BW + 0.06, y_c + BH / 2)
    out_l = (X[3] - 0.06, y_c + BH / 2)
    for y in (Y_TOP, Y_BOT):
        yc = y + BH / 2
        elbow(ax, src_r, (X[1] - 0.06, yc))
        arrow(ax, (X[1] + BW + 0.06, yc), (X[2] - 0.06, yc))
        elbow(ax, (X[2] + BW + 0.06, yc), out_l)

    out = Path(__file__).resolve().parent / "model_diagram.png"
    fig.savefig(out, facecolor="white", bbox_inches="tight", pad_inches=0.1)
    print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
