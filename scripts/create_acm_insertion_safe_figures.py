#!/usr/bin/env python3
"""Regenerate quantitative manuscript figures for stable ACM insertion.

The canvas size is fixed, no tight bounding-box crop is used, and every panel
reserves space for titles, labels, legends, and annotations inside its border.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.ticker import FuncFormatter, FixedLocator


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
PREVIEW = ROOT / "tmp" / "acm_figure_previews"
PREVIEW.mkdir(parents=True, exist_ok=True)

BLUE = "#2F72B7"
BLUE_DARK = "#1F5FAA"
ORANGE = "#EF8A17"
GREEN = "#4A9E49"
RED = "#D95F5F"
PURPLE = "#8064A2"
GRAY = "#747B83"
LIGHT_GRID = "#D9DDE2"
BLACK = "#1F1F1F"

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7.4,
        "axes.titlesize": 8.4,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 7.1,
        "ytick.labelsize": 7.1,
        "legend.fontsize": 7.0,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    }
)


def panel_frame(fig: plt.Figure, rect: tuple[float, float, float, float], title: str) -> None:
    x, y, w, h = rect
    frame = FancyBboxPatch(
        (x, y),
        w,
        h,
        transform=fig.transFigure,
        boxstyle="round,pad=0.006,rounding_size=0.012",
        linewidth=0.9,
        edgecolor=BLACK,
        facecolor="white",
        clip_on=False,
        zorder=-10,
    )
    fig.add_artist(frame)
    fig.text(x + w / 2, y + h - 0.045, title, ha="center", va="center",
             fontsize=8.4, weight="bold", color=BLACK)


def panel_axes(
    fig: plt.Figure,
    rect: tuple[float, float, float, float],
    *,
    left: float = 0.13,
    right: float = 0.055,
    bottom: float = 0.20,
    top: float = 0.18,
) -> plt.Axes:
    x, y, w, h = rect
    ax = fig.add_axes([x + left * w, y + bottom * h,
                       w * (1 - left - right), h * (1 - bottom - top)])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(width=0.7, length=3)
    ax.grid(axis="y", color=LIGHT_GRID, linewidth=0.55, linestyle="--", zorder=0)
    return ax


def export(fig: plt.Figure, name: str) -> None:
    # Intentionally omit bbox_inches="tight" so every file keeps its fixed MediaBox.
    fig.savefig(OUT / f"{name}.pdf", format="pdf")
    fig.savefig(OUT / f"{name}.svg", format="svg")
    fig.savefig(PREVIEW / f"{name}.png", format="png", dpi=600)
    fig.savefig(PREVIEW / f"{name}.tiff", format="tiff", dpi=600)
    plt.close(fig)


def content_axes(
    fig: plt.Figure,
    rect: tuple[float, float, float, float],
    *,
    left: float = 0.06,
    right: float = 0.06,
    bottom: float = 0.07,
    top: float = 0.16,
) -> plt.Axes:
    x, y, w, h = rect
    ax = fig.add_axes([x + left * w, y + bottom * h,
                       w * (1 - left - right), h * (1 - bottom - top)])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return ax


def node(
    ax: plt.Axes,
    x: float,
    y: float,
    label: str,
    *,
    feasible: bool = True,
    bridge: bool = False,
) -> None:
    face = "#EAF2FA" if feasible else ("#E4E7EA" if bridge else "white")
    edge = BLUE_DARK if feasible else GRAY
    ax.add_patch(Circle((x, y), 0.047, facecolor=face, edgecolor=edge,
                        linewidth=1.0, zorder=3))
    ax.text(x, y, label, ha="center", va="center", fontsize=7.2,
            color=BLACK, zorder=4)


def figure_core_idea() -> None:
    """Figure 1: query, attribute routing, and navigation/admission separation."""
    fig = plt.figure(figsize=(7.20, 2.80))
    rects = [
        (0.020, 0.055, 0.280, 0.890),
        (0.320, 0.055, 0.350, 0.890),
        (0.690, 0.055, 0.290, 0.890),
    ]
    titles = [
        "(a) Multi-attribute range query",
        "(b) Query-dependent attribute routing",
        "(c) Navigation vs. admission",
    ]
    for rect, title in zip(rects, titles):
        panel_frame(fig, rect, title)

    # Panel a: objects and the conjunctive range query.
    ax = content_axes(fig, rects[0], left=0.06, right=0.06, bottom=0.08, top=0.18)
    xs = np.linspace(0.12, 0.90, 6)
    ax.plot([xs[0] - 0.05, xs[-1] + 0.05], [0.75, 0.75], color=BLACK, lw=0.9, zorder=1)
    for x, label in zip(xs, ["$v_1$", "$v_2$", "$v_3$", "$v_4$", "$v_5$", "$v_6$"]):
        ax.add_patch(Circle((x, 0.75), 0.030, facecolor=BLUE,
                            edgecolor=BLACK, linewidth=0.75, zorder=3))
        ax.text(x, 0.86, label, ha="center", va="center", fontsize=7.4, zorder=4)
    ax.text(0.00, 0.58, "$a_1$:", ha="left", va="center", fontsize=7.3)
    ax.text(0.00, 0.46, "$a_2$:", ha="left", va="center", fontsize=7.3)
    for x, value in zip(xs, [1, 3, 4, 5, 6, 8]):
        ax.text(x, 0.58, str(value), ha="center", va="center", fontsize=7.1)
    for x, value in zip(xs, [7, 2, 6, 3, 5, 9]):
        ax.text(x, 0.46, str(value), ha="center", va="center", fontsize=7.1)
    query = FancyBboxPatch(
        (0.06, 0.13), 0.88, 0.22,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        facecolor="#EAF2FA", edgecolor=BLUE_DARK, linewidth=1.0,
    )
    ax.add_patch(query)
    ax.text(0.50, 0.275, "Query", ha="center", va="center", fontsize=7.4)
    ax.text(0.50, 0.205, r"$F=\{a_1\in[3,6],\,a_2\in[4,7]\}$",
            ha="center", va="center", fontsize=7.2)
    ax.text(0.50, 0.145, "$k=2$", ha="center", va="center", fontsize=7.2)

    # Panel b: the router compares rank spans without crowding the title zone.
    ax = content_axes(fig, rects[1], left=0.045, right=0.045, bottom=0.08, top=0.20)
    ax.text(0.58, 0.945, "attribute value increases $\\rightarrow$",
            ha="center", va="center", fontsize=6.8, color="#B1B6BA")

    def routing_row(y: float, name: str, order: list[str], values: list[int],
                    selected: tuple[int, int], interval: str, width: int) -> None:
        row_x = np.linspace(0.25, 0.92, 6)
        ax.text(0.03, y + 0.045, name, ha="left", va="center",
                fontsize=7.4, weight="bold")
        ax.plot([row_x[0] - 0.04, row_x[-1] + 0.04], [y, y], color=BLACK, lw=0.8, zorder=1)
        for i in range(selected[0], selected[1] + 1):
            ax.add_patch(Rectangle(
                (row_x[i] - 0.045, y - 0.060), 0.090, 0.120,
                facecolor="#EAF2FA", edgecolor=BLUE, linewidth=0.75,
                hatch="////", zorder=0,
            ))
        for x, obj, value in zip(row_x, order, values):
            ax.add_patch(Circle((x, y), 0.022, facecolor="white",
                                edgecolor=BLACK, linewidth=0.8, zorder=3))
            ax.text(x, y + 0.090, obj, ha="center", va="center", fontsize=7.4)
            ax.text(x, y - 0.095, str(value), ha="center", va="center", fontsize=6.7)
        ax.text(0.58, y - 0.165, f"{interval},   $w={width}$", ha="center",
                va="center", fontsize=7.1, color=BLUE_DARK)

    routing_row(0.775, "DSG($a_1$)", ["$v_1$", "$v_2$", "$v_3$", "$v_4$", "$v_5$", "$v_6$"],
                [1, 3, 4, 5, 6, 8], (1, 4), "[3, 6]", 4)
    routing_row(0.445, "DSG($a_2$)", ["$v_2$", "$v_4$", "$v_5$", "$v_3$", "$v_1$", "$v_6$"],
                [2, 3, 5, 6, 7, 9], (2, 4), "[4, 7]", 3)
    choice = FancyBboxPatch(
        (0.32, 0.070), 0.46, 0.118,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        facecolor="#EAF2FA", edgecolor=BLUE_DARK, linewidth=1.0,
    )
    ax.add_patch(choice)
    ax.text(0.55, 0.129, "select $a_2$:  $w_2<w_1$", ha="center",
            va="center", fontsize=7.4)

    # Panel c: a compact title and dedicated top padding keep the graph clear.
    ax = content_axes(fig, rects[2], left=0.06, right=0.06, bottom=0.07, top=0.20)
    positions = {
        "$v_1$": (0.50, 0.86),
        "$v_5$": (0.20, 0.69),
        "$v_3$": (0.80, 0.69),
        "$v_2$": (0.12, 0.51),
        "$v_4$": (0.50, 0.51),
        "$v_6$": (0.88, 0.51),
    }
    dashed_edges = [
        ("$v_1$", "$v_3$"), ("$v_5$", "$v_2$"),
        ("$v_2$", "$v_4$"), ("$v_4$", "$v_6$"), ("$v_3$", "$v_6$"),
    ]
    for u, v in dashed_edges:
        x0, y0 = positions[u]
        x1, y1 = positions[v]
        ax.plot([x0, x1], [y0, y1], color=BLACK, lw=0.75,
                ls=(0, (3, 2)), zorder=1)
    for u, v in [("$v_1$", "$v_5$"), ("$v_5$", "$v_3$")]:
        x0, y0 = positions[u]
        x1, y1 = positions[v]
        ax.plot([x0, x1], [y0, y1], color=BLUE_DARK, lw=1.35, zorder=2)
    for label, (x, y) in positions.items():
        bridge = label == "$v_1$"
        admitted = label in {"$v_5$", "$v_3$"}
        ax.add_patch(Circle(
            (x, y), 0.064, facecolor="#E4E7EA" if bridge else "white",
            edgecolor=BLACK, linewidth=0.85, zorder=3,
        ))
        ax.text(x, y, label, ha="center", va="center", fontsize=7.4, zorder=4)
        if admitted:
            ax.add_patch(Circle((x, y), 0.064, facecolor="none",
                                edgecolor=BLUE_DARK, linewidth=1.0, zorder=4))
    ax.text(0.50, 0.765, "bridge only", fontsize=6.3,
            ha="center", va="center", color=GRAY, zorder=5,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.10))
    ax.text(0.50, 0.325, "navigation  $\\ne$  result admission",
            ha="center", va="center", fontsize=6.8, color="#555B61", zorder=5)
    result = FancyBboxPatch(
        (0.22, 0.165), 0.56, 0.085,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        facecolor="#EAF2FA", edgecolor=BLUE_DARK, linewidth=1.0,
    )
    ax.add_patch(result)
    ax.text(0.50, 0.207, "Top-$k=\\{v_5,v_3\\}$", ha="center",
            va="center", fontsize=7.2)
    key_y = 0.055
    for x, label, fc, ec in [
        (0.08, "bridge", "#E4E7EA", BLACK),
        (0.41, "admitted", "white", BLUE_DARK),
    ]:
        ax.add_patch(Circle((x, key_y), 0.016, facecolor=fc,
                            edgecolor=ec, linewidth=0.8, clip_on=False))
        ax.text(x + 0.035, key_y, label, ha="left", va="center",
                fontsize=6.1, clip_on=False)
    ax.plot([0.72, 0.82], [key_y, key_y], color=BLUE_DARK, lw=1.35, clip_on=False)
    ax.text(0.84, key_y, "traversal", ha="left", va="center",
            fontsize=6.1, clip_on=False)
    export(fig, "fig1_core_idea")


def figure_snapshot_lifecycle() -> None:
    """Figure 2: update-induced rank invalidation and two-epoch reconstruction."""
    fig = plt.figure(figsize=(7.20, 2.45))
    left_rect = (0.020, 0.070, 0.350, 0.850)
    right_rect = (0.400, 0.070, 0.590, 0.850)

    # Fine gray boundaries preserve panel grouping without consuming visual area.
    for rect, title in [
        (left_rect, "(a) Update-induced rank change"),
        (right_rect, "(b) Snapshot rebuild lifecycle"),
    ]:
        x, y, w, h = rect
        fig.add_artist(Rectangle((x, y), w, h, transform=fig.transFigure,
                                 facecolor="white", edgecolor="#D9DEE3",
                                 linewidth=0.55, zorder=-10))
        fig.text(x + w / 2, y + h - 0.034, title, ha="center", va="center",
                 fontsize=8.1, weight="bold", color=BLACK)

    # Panel (a): one update with two causal consequences.
    ax = content_axes(fig, left_rect, left=0.045, right=0.045, bottom=0.045, top=0.135)

    def semantic_box(x: float, y: float, w: float, h: float, label: str,
                     fc: str, ec: str, *, ls: str = "-", fontsize: float = 7.0) -> None:
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.010,rounding_size=0.025",
            facecolor=fc, edgecolor=ec, linewidth=0.95, linestyle=ls, zorder=2,
        ))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                fontsize=fontsize, zorder=4)

    semantic_box(0.13, 0.55, 0.24, 0.18,
                 "Base version\n$a=10$\nrank = 20", "#EAF2FA", BLUE_DARK)
    semantic_box(0.58, 0.55, 0.24, 0.18,
                 "Updated version\n$a=90$\nrank = 500", "#FFF1DF", ORANGE)
    ax.add_patch(FancyArrowPatch((0.37, 0.64), (0.58, 0.64), arrowstyle="-|>",
                                 mutation_scale=8, color=ORANGE, linewidth=1.0, zorder=3))
    ax.text(0.475, 0.785, "update", ha="center", va="center", fontsize=6.8,
            color=ORANGE, bbox=dict(facecolor="white", edgecolor="none", pad=0.12), zorder=5)

    semantic_box(0.13, 0.25, 0.24, 0.18,
                 "Visible in $\\Delta$\nimmediately", "#FFF8EE", ORANGE, fontsize=6.9)
    semantic_box(0.58, 0.25, 0.24, 0.18,
                 "Old DSG labels\nstale", "#FBECEC", RED, ls="--", fontsize=6.9)
    ax.plot([0.70, 0.70], [0.55, 0.455], color=GRAY, linewidth=0.9, zorder=1)
    ax.plot([0.25, 0.70], [0.455, 0.455], color=GRAY, linewidth=0.9, zorder=1)
    ax.add_patch(FancyArrowPatch((0.25, 0.455), (0.25, 0.43), arrowstyle="-|>",
                                 mutation_scale=7, color=ORANGE, linewidth=0.9, zorder=2))
    ax.add_patch(FancyArrowPatch((0.70, 0.455), (0.70, 0.43), arrowstyle="-|>",
                                 mutation_scale=7, color=RED, linewidth=0.9, zorder=2))
    ax.text(0.70, 0.13, "repair at rebuild", ha="center", va="center",
            fontsize=6.3, color=GRAY)

    # Panel (b): orthogonal two-epoch flow anchored by t0/t1/t2.
    ax = content_axes(fig, right_rect, left=0.035, right=0.025, bottom=0.035, top=0.135)

    def lifecycle_box(x: float, y: float, w: float, h: float, label: str,
                      fc: str, ec: str, fontsize: float = 6.9) -> None:
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.010,rounding_size=0.025",
            facecolor=fc, edgecolor=ec, linewidth=0.95, zorder=2,
        ))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                fontsize=fontsize, zorder=4)

    t0, t1, t2 = 0.13, 0.52, 0.85
    for x, top in [(t0, 0.65), (t1, 0.65), (t2, 0.69)]:
        ax.plot([x, x], [0.18, top], color="#D9DEE3", lw=0.60,
                ls=(0, (2, 3)), zorder=0)

    lifecycle_box(0.045, 0.51, 0.15, 0.14, "Base B0", "#EAF2FA", BLUE_DARK)
    lifecycle_box(0.29, 0.505, 0.22, 0.15,
                  "captured state\nB0 + $\\Delta_{pre}$ + Tpre", "#FFF1DF", ORANGE, 6.3)
    lifecycle_box(0.44, 0.345, 0.18, 0.11,
                  "rebuild B1\nranks + DSGs", "#FFF1DF", ORANGE, 6.3)
    lifecycle_box(0.56, 0.185, 0.14, 0.09,
                  "post-cut updates\n$\\Delta_{post}$ + Tpost", "#FFF8EE", ORANGE, 5.8)
    lifecycle_box(0.77, 0.47, 0.17, 0.22,
                  "Published state\nB1 + $\\Delta_{post}$\n+ Tpost", "#EAF2FA", BLUE_DARK, 6.3)

    # Main capture/rebuild path.
    ax.add_patch(FancyArrowPatch((0.195, 0.58), (0.29, 0.58), arrowstyle="-|>",
                                 mutation_scale=7, color=BLACK, linewidth=0.9, zorder=3))
    ax.add_patch(FancyArrowPatch((0.40, 0.505), (0.40, 0.455), arrowstyle="-|>",
                                 mutation_scale=7, color=ORANGE, linewidth=0.9, zorder=3))
    ax.plot([0.62, 0.70, 0.70, 0.77], [0.40, 0.40, 0.58, 0.58],
            color=ORANGE, linewidth=0.9, zorder=1)
    ax.add_patch(FancyArrowPatch((0.70, 0.58), (0.77, 0.58), arrowstyle="-|>",
                                 mutation_scale=7, color=ORANGE, linewidth=0.9, zorder=3))

    # Post-cut updates form one independent preservation branch.
    ax.plot([t1, t1, 0.63, 0.63], [0.13, 0.16, 0.16, 0.185],
            color=ORANGE, linewidth=0.85, zorder=1)
    ax.add_patch(FancyArrowPatch((0.63, 0.16), (0.63, 0.185), arrowstyle="-|>",
                                 mutation_scale=7, color=ORANGE, linewidth=0.85, zorder=3))
    ax.plot([0.70, 0.73, 0.73, 0.77], [0.23, 0.23, 0.47, 0.47],
            color=ORANGE, linewidth=0.9, zorder=1)
    ax.add_patch(FancyArrowPatch((0.73, 0.47), (0.77, 0.47), arrowstyle="-|>",
                                 mutation_scale=7, color=ORANGE, linewidth=0.9, zorder=3))

    ax.text(0.40, 0.80, "trigger", ha="center", va="center",
            fontsize=6.4, color="#C96F08")
    ax.text(0.40, 0.755, "$|C|\\geq\\tau n_B$", ha="center", va="center",
            fontsize=6.6, color="#C96F08")
    ax.add_patch(FancyArrowPatch((0.40, 0.725), (0.40, 0.655), arrowstyle="-|>",
                                 mutation_scale=6, color="#C96F08", linewidth=0.75, zorder=3))
    ax.text(0.86, 0.80, "atomic publish", ha="center", va="center",
            fontsize=6.3, color="#4F78A7")
    ax.add_patch(FancyArrowPatch((0.86, 0.755), (0.86, 0.69), arrowstyle="-|>",
                                 mutation_scale=6, color="#4F78A7", linewidth=0.75, zorder=3))

    ax.add_patch(FancyArrowPatch((0.04, 0.13), (0.97, 0.13), arrowstyle="-|>",
                                 mutation_scale=7, color=GRAY, linewidth=0.7, zorder=1))
    for x, upper, lower in [(t0, "$t_0$", ""), (t1, "$t_1$", "cut"), (t2, "$t_2$", "swap")]:
        ax.plot([x, x], [0.10, 0.16], color=GRAY, lw=0.75, zorder=2)
        ax.text(x, 0.075, upper, ha="center", va="center", fontsize=7.0)
        if lower:
            ax.text(x, 0.035, lower, ha="center", va="center", fontsize=6.3, color=GRAY)
    export(fig, "fig2_snapshot_lifecycle")


def figure_running_example() -> None:
    """Three-stage running example; dynamic maintenance stays in Figure 3."""
    fig = plt.figure(figsize=(7.16, 3.20))
    rects = [
        (0.020, 0.060, 0.270, 0.885),
        (0.310, 0.060, 0.340, 0.885),
        (0.670, 0.060, 0.310, 0.885),
    ]
    titles = ["(a) Objects and query", "(b) Attribute-specific DSGs",
              "(c) Navigate and admit"]
    for rect, title in zip(rects, titles):
        panel_frame(fig, rect, title)

    ax = content_axes(fig, rects[0], left=0.06, right=0.06, bottom=0.07, top=0.17)
    xs = np.linspace(0.15, 0.92, 6)
    for xv, label in zip(xs, ["v1", "v2", "v3", "v4", "v5", "v6"]):
        node(ax, xv, 0.78, label)
    ax.text(0.01, 0.57, "a1", ha="left", va="center", fontsize=7.4, weight="bold")
    ax.text(0.01, 0.43, "a2", ha="left", va="center", fontsize=7.4, weight="bold")
    for xv, value in zip(xs, [1, 3, 4, 5, 6, 8]):
        ax.text(xv, 0.57, str(value), ha="center", va="center", fontsize=7.2)
    for xv, value in zip(xs, [7, 2, 6, 3, 5, 9]):
        ax.text(xv, 0.43, str(value), ha="center", va="center", fontsize=7.2)
    query = FancyBboxPatch((0.08, 0.08), 0.84, 0.20,
                           boxstyle="round,pad=0.012,rounding_size=0.025",
                           facecolor="#F5F8FB", edgecolor=BLACK, linewidth=0.9)
    ax.add_patch(query)
    ax.text(0.50, 0.205, "Query range", ha="center", va="center",
            fontsize=7.5, weight="bold")
    ax.text(0.50, 0.125, "a1 in [3, 6]   AND   a2 in [4, 7]",
            ha="center", va="center", fontsize=7.2)

    ax = content_axes(fig, rects[1], left=0.05, right=0.05, bottom=0.06, top=0.17)
    ax.text(0.23, 0.90, "DSG(a1)", ha="center", va="center", fontsize=7.7, weight="bold")
    ax.text(0.77, 0.90, "DSG(a2)", ha="center", va="center", fontsize=7.7, weight="bold")
    ax.text(0.23, 0.835, r"attribute value $\uparrow$", ha="center", va="center",
            fontsize=6.8, color=GRAY)
    ax.text(0.77, 0.835, r"attribute value $\uparrow$", ha="center", va="center",
            fontsize=6.8, color=GRAY)
    ax.plot([0.23, 0.23], [0.25, 0.80], color=BLACK, linewidth=1.0)
    ax.plot([0.77, 0.77], [0.25, 0.80], color=BLACK, linewidth=1.0)
    order1 = ["v1", "v2", "v3", "v4", "v5", "v6"]
    order2 = ["v2", "v4", "v5", "v3", "v1", "v6"]
    ys = np.linspace(0.29, 0.76, 6)
    ax.add_patch(Rectangle((0.13, ys[1] - 0.045), 0.20, ys[4] - ys[1] + 0.09,
                           facecolor="#EAF2FA", edgecolor=BLUE, linewidth=0.8, zorder=0))
    ax.add_patch(Rectangle((0.67, ys[2] - 0.045), 0.20, ys[4] - ys[2] + 0.09,
                           facecolor="#FFF1DF", edgecolor=ORANGE, linewidth=1.2, zorder=0))
    for yv, l1, l2 in zip(ys, order1, order2):
        node(ax, 0.23, yv, l1)
        node(ax, 0.77, yv, l2)
    ax.text(0.23, 0.18, "span w1 = 4", ha="center", va="center", fontsize=7.2, color=BLUE_DARK)
    ax.text(0.77, 0.18, "span w2 = 3", ha="center", va="center", fontsize=7.2,
            color=ORANGE, weight="bold")
    ax.text(0.48, 0.07, "Router selects a2", ha="center", va="center",
            fontsize=7.3, weight="bold")
    ax.add_patch(FancyArrowPatch((0.61, 0.07), (0.72, 0.16), arrowstyle="-|>",
                                 mutation_scale=9, color=ORANGE, linewidth=1.0))

    ax = content_axes(fig, rects[2], left=0.06, right=0.06, bottom=0.06, top=0.17)
    positions = {
        "v1": (0.50, 0.78), "v2": (0.18, 0.56), "v3": (0.78, 0.56),
        "v4": (0.25, 0.29), "v5": (0.52, 0.39), "v6": (0.83, 0.27),
    }
    edges = [("v1", "v2"), ("v1", "v3"), ("v1", "v5"), ("v2", "v4"), ("v2", "v5"),
             ("v5", "v3"), ("v3", "v6"), ("v5", "v6")]
    for u, v in edges:
        x1, y1 = positions[u]
        x2, y2 = positions[v]
        ax.plot([x1, x2], [y1, y2], color="#B8BEC6", linewidth=0.8, zorder=1)
    for u, v in [("v1", "v5"), ("v5", "v3")]:
        x1, y1 = positions[u]
        x2, y2 = positions[v]
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=8, color=BLUE_DARK,
                                     linewidth=1.6, zorder=2))
    feasible = {"v3", "v5"}
    for label, (xv, yv) in positions.items():
        node(ax, xv, yv, label, feasible=label in feasible, bridge=label == "v1")
    ax.annotate("seed / bridge-only", xy=positions["v1"], xytext=(0.37, 0.84),
                ha="right", va="center", fontsize=7.2, color=GRAY,
                arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.7,
                                shrinkA=2, shrinkB=5))
    ax.text(0.50, 0.91, "Navigate on DSG(a2)", ha="center", va="center",
            fontsize=7.5, weight="bold", color=BLUE_DARK)
    result = FancyBboxPatch((0.20, 0.02), 0.60, 0.17,
                            boxstyle="round,pad=0.010,rounding_size=0.025",
                            facecolor="#EAF2FA", edgecolor=BLUE_DARK, linewidth=1.0)
    ax.add_patch(result)
    ax.text(0.50, 0.125, "Full-predicate admission", ha="center", va="center",
            fontsize=7.2, weight="bold")
    ax.text(0.50, 0.070, "Top-k = {v5, v3}", ha="center", va="center",
            fontsize=7.2, weight="bold")
    export(fig, "fig1_extension_overview")


def figure_main_comparison() -> None:
    methods = ["HNSW\npost-filter", "HNSW\nin-search", "Multi-DSG"]
    dist = np.array([351_958.6, 334_501.3, 12_689.9])
    storage = np.array([5.0, 5.0, 106.6])
    x = np.arange(3)
    fig = plt.figure(figsize=(7.16, 2.80))
    left_rect = (0.025, 0.075, 0.462, 0.865)
    right_rect = (0.513, 0.075, 0.462, 0.865)
    panel_frame(fig, left_rect, "(a) Matched-recall graph work")
    panel_frame(fig, right_rect, "(b) Deployment cost")

    ax = panel_axes(fig, left_rect, left=0.17, right=0.06, bottom=0.22, top=0.17)
    bars = ax.bar(x, dist, width=0.60, color=BLUE, edgecolor=BLACK, linewidth=0.7, zorder=2)
    for bar, hatch in zip(bars, ("//", "..", "")):
        bar.set_hatch(hatch)
    ax.set_yscale("log")
    ax.set_ylim(8_000, 700_000)
    ax.yaxis.set_major_locator(FixedLocator([10_000, 100_000]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: {10_000: "10K", 100_000: "100K"}.get(v, "")))
    ax.set_ylabel("Distance evaluations / query", labelpad=5)
    ax.set_xticks(x, methods)
    for bar, value, label in zip(bars, dist, ("352K", "335K", "12.7K")):
        ax.text(bar.get_x() + bar.get_width() / 2, value * 1.07, label,
                ha="center", va="bottom", fontsize=7.1)
    ax.annotate(
        "$27.7\\times$ fewer",
        xy=(2, dist[2] * 1.12), xycoords="data",
        xytext=(2, 45_000), textcoords="data",
        ha="center", va="center", fontsize=7.1, color="#333333",
        bbox=dict(boxstyle="round,pad=0.20", fc="white", ec="none", alpha=0.94),
        arrowprops=dict(arrowstyle="-|>", color="#444444", lw=1.0,
                        shrinkA=2, shrinkB=3),
        zorder=6,
    )

    ax = panel_axes(fig, right_rect, left=0.17, right=0.06, bottom=0.22, top=0.17)
    bars = ax.bar(x, storage, width=0.60, color=BLUE, edgecolor=BLACK, linewidth=0.7, zorder=2)
    ax.set_yscale("log")
    ax.set_ylim(3.5, 180)
    ax.yaxis.set_major_locator(FixedLocator([5, 10, 100]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: {5: "5", 10: "10", 100: "100"}.get(v, "")))
    ax.set_ylabel("Index storage (GB)", labelpad=5)
    ax.set_xticks(x, methods)
    for bar, value, label in zip(bars, storage, ("5.0", "5.0", "106.6")):
        ax.text(bar.get_x() + bar.get_width() / 2, value * 1.08, label,
                ha="center", va="bottom", fontsize=7.1)
    ax.annotate(
        "$21.3\\times$ larger",
        xy=(2, storage[2] * 0.96), xycoords="data",
        xytext=(1.30, 42), textcoords="data",
        ha="center", va="center", fontsize=7.1, color="#D97706",
        bbox=dict(boxstyle="round,pad=0.20", fc="white", ec="none", alpha=0.94),
        arrowprops=dict(arrowstyle="-|>", color="#D97706", lw=1.1,
                        shrinkA=2, shrinkB=3),
        zorder=6,
    )
    export(fig, "fig_deep10m_work_comparison")


def figure_router_analysis() -> None:
    labels = ["Fixed a0", "Fixed a1", "Fixed a2", "Span", "Oracle", "Calib. test"]
    qps = np.array([107.5, 164.6, 59.9, 169.7, 158.8, 167.4])
    recall = np.array([0.4614, 0.9802, 0.8811, 0.9508, 0.9944, 0.9798])
    selected = np.array([
        [100.0, 0.0, 0.0],
        [0.0, 100.0, 0.0],
        [0.0, 0.0, 100.0],
        [7.9, 92.1, 0.0],
        [4.5, 91.3, 4.2],
        [0.2, 99.8, 0.0],
    ])
    colors = [BLUE, ORANGE, GREEN, RED, PURPLE, "#C96A50"]
    markers = ["o", "s", "^", "D", "P", "o"]
    fig = plt.figure(figsize=(7.16, 3.20))
    left_rect = (0.025, 0.060, 0.462, 0.885)
    right_rect = (0.513, 0.060, 0.462, 0.885)
    panel_frame(fig, left_rect, "(a) Router quality on App-Reviews")
    panel_frame(fig, right_rect, "(b) Navigation-attribute distribution")

    ax = panel_axes(fig, left_rect, left=0.15, right=0.06, bottom=0.31, top=0.17)
    for label, xv, yv, color, marker in zip(labels, qps, recall, colors, markers):
        held_out = label == "Calib. test"
        ax.scatter(xv, yv, s=42, facecolor="white" if held_out else color,
                   marker=marker, edgecolor=BLACK, linewidth=0.9 if held_out else 0.7,
                   zorder=3)
    ax.set_xlim(48, 190)
    ax.set_ylim(0.40, 1.055)
    ax.set_xlabel("QPS")
    ax.set_ylabel("Recall@10", labelpad=5)
    legend_labels = labels[:-1] + ["Calib. test (5K held-out)"]
    handles = [Line2D([0], [0], marker=marker, color="none",
                      markerfacecolor="white" if label == "Calib. test" else color,
                      markeredgecolor=BLACK,
                      markeredgewidth=0.9 if label == "Calib. test" else 0.6,
                      markersize=5.2,
                      label=display_label)
               for label, display_label, color, marker in zip(labels, legend_labels, colors, markers)]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.24),
              ncol=2, frameon=False, columnspacing=0.8, handletextpad=0.35,
              labelspacing=0.28)
    ax = panel_axes(fig, right_rect, left=0.22, right=0.06, bottom=0.20, top=0.25)
    bar_y = np.arange(len(labels))
    left = np.zeros(len(labels))
    route_colors = [BLUE, ORANGE, GREEN]
    route_labels = ["attr0", "attr1", "attr2"]
    for j in range(3):
        ax.barh(bar_y, selected[:, j], left=left, color=route_colors[j],
                edgecolor="white", linewidth=0.55, height=0.64,
                label=route_labels[j], zorder=2)
        left += selected[:, j]
    ax.set_xlim(0, 100)
    ax.set_xlabel("Queries routed to attribute (%)")
    ax.set_yticks(bar_y, labels)
    ax.invert_yaxis()
    ax.grid(axis="x", color=LIGHT_GRID, linewidth=0.55, linestyle="--", zorder=0)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.05), ncol=3,
              frameon=False, handlelength=1.1, columnspacing=1.0)
    # Fixed routes are visually self-evident; annotate only adaptive policies.
    for row, segments in [(3, selected[3]), (4, selected[4]), (5, selected[5])]:
        cumulative = 0.0
        for value in segments:
            if value >= 5.0:
                ax.text(cumulative + value / 2, row, f"{value:.1f}", ha="center",
                        va="center", fontsize=7.0, color=BLACK)
            cumulative += value
    export(fig, "fig_app_routing")


def figure_attribute_scaling() -> None:
    m = np.arange(1, 7)
    size = np.array([2.06, 4.13, 6.19, 9.47, 12.76, 16.04])
    build = np.array([14.18, 29.06, 42.85, 75.97, 109.10, 142.33])
    fixed = np.array([0.9992, 0.9989, 0.9964, 0.9849, 0.9217, 0.8498])
    tuned_m = np.array([4, 5, 6])
    tuned = np.array([0.9994, 0.9984, 0.9991])
    tuned_ef = [1536, 2048, 4096]
    fig = plt.figure(figsize=(7.16, 4.00))
    rects = [(0.025, 0.535, 0.462, 0.420), (0.513, 0.535, 0.462, 0.420),
             (0.025, 0.065, 0.950, 0.395)]
    titles = ["(a) Space growth", "(b) Build-time growth", "(c) Recall scaling"]
    for rect, title in zip(rects, titles):
        panel_frame(fig, rect, title)

    ax = panel_axes(fig, rects[0], left=0.15, right=0.05, bottom=0.25, top=0.18)
    bars = ax.bar(m, size, width=0.62, color=BLUE, edgecolor=BLACK, linewidth=0.6, zorder=2)
    ax.set_xlabel("Indexed attributes (m)")
    ax.set_ylabel("Index size (GB)", labelpad=4)
    ax.set_xticks(m)
    ax.set_ylim(0, 17.8)
    for idx in [0, 5]:
        bar = bars[idx]
        value = size[idx]
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.35, f"{value:.2f}",
                ha="center", va="bottom", fontsize=7.1)

    ax = panel_axes(fig, rects[1], left=0.15, right=0.05, bottom=0.25, top=0.18)
    ax.plot(m, build, color=BLUE_DARK, marker="o", markersize=4.2, linewidth=1.5,
            markeredgecolor=BLACK, markeredgewidth=0.45, zorder=3)
    ax.set_xlabel("Indexed attributes (m)")
    ax.set_ylabel("Cumulative build time (min)", labelpad=4)
    ax.set_xticks(m)
    ax.set_ylim(8, 153)
    for idx, offset, align in [(0, (4, 8), "left"), (5, (-4, 8), "right")]:
        xv = m[idx]
        value = build[idx]
        ax.annotate(f"{value:.2f}", xy=(xv, value), xytext=offset,
                    textcoords="offset points", ha=align, va="bottom", fontsize=7.1,
                    bbox=dict(facecolor="white", edgecolor="none", pad=0.08))

    ax = panel_axes(fig, rects[2], left=0.08, right=0.035, bottom=0.25, top=0.22)
    ax.plot(m, fixed, color=BLUE_DARK, marker="o", markersize=4.0, linewidth=1.4,
            markeredgecolor=BLACK, markeredgewidth=0.45,
            label="Fixed ef = 512", zorder=3)
    ax.scatter(tuned_m, tuned, marker="D", s=31, color=ORANGE, edgecolor=BLACK,
               linewidth=0.55,
               label="Tuned ef", zorder=4)
    ax.set_xlabel("Indexed attributes (m)")
    ax.set_ylabel("Recall@10", labelpad=4)
    ax.set_xticks(m)
    ax.set_ylim(0.82, 1.04)
    ax.legend(loc="lower left", frameon=False, handlelength=1.5, ncol=2)
    export(fig, "fig_attribute_scalability")


def figure_dynamic_maintenance() -> None:
    delta = np.array([0, 10, 20, 40, 50, 100, 200])
    latency = np.array([10.1345, 10.4959, 10.8661, 10.3740, 11.9353, 22.1365, 27.3521])
    qps = np.array([98.7, 95.3, 92.0, 96.4, 83.8, 45.2, 36.6])
    base = np.array([8.2247, 8.1576, 12.1005])
    scan = np.array([0.0002, 5.5674, 7.1490])
    merge = np.array([0.0030, 0.0569, 0.1236])
    other = np.array([0.0010, 0.0012, 0.0017])
    fig = plt.figure(figsize=(7.16, 4.00))
    left_rect = (0.025, 0.535, 0.462, 0.420)
    right_rect = (0.513, 0.535, 0.462, 0.420)
    bottom_rect = (0.025, 0.070, 0.950, 0.390)
    panel_frame(fig, left_rect, "(a) Delta growth cost")
    panel_frame(fig, right_rect, "(b) Dynamic query cost breakdown")
    panel_frame(fig, bottom_rect, "(c) Rebuild recovery")

    ax = panel_axes(fig, left_rect, left=0.14, right=0.14, bottom=0.25, top=0.18)
    latency_line, = ax.plot(delta, latency, color=BLUE_DARK, marker="o", markersize=3.8,
                            linewidth=1.4, label="Latency", zorder=3)
    ax.set_xlabel("Delta entries (K)")
    ax.set_ylabel("After-delete latency (ms)", color=BLUE_DARK, labelpad=4)
    ax.tick_params(axis="y", labelcolor=BLUE_DARK)
    ax.set_xlim(-5, 210)
    ax.set_ylim(9, 31)
    ax2 = ax.twinx()
    qps_line, = ax2.plot(delta, qps, color=ORANGE, marker="s", markersize=3.8,
                        markeredgecolor=BLACK, markeredgewidth=0.45,
                        linewidth=1.4, linestyle="--", label="QPS", zorder=3)
    ax2.set_ylabel("QPS", color=ORANGE, labelpad=4)
    ax2.tick_params(axis="y", labelcolor=ORANGE)
    ax2.set_ylim(32, 104)
    ax2.spines["top"].set_visible(False)
    callout_style = dict(
        boxstyle="round,pad=0.25", fc="white", ec="#666666", lw=0.6,
    )
    idx = 4
    ax.annotate("50K\n11.94 ms\n83.8 QPS", (delta[idx], latency[idx]),
                xytext=(78, 13.5), textcoords="data", ha="center", va="center",
                fontsize=6.7, color=BLACK, bbox=callout_style,
                arrowprops=dict(arrowstyle="-", color="#666666", lw=0.7,
                                shrinkA=2, shrinkB=3), zorder=6)
    idx = 6
    ax.annotate("200K\n27.35 ms\n36.6 QPS", (delta[idx], latency[idx]),
                xytext=(153, 19.0), textcoords="data", ha="center", va="center",
                fontsize=6.7, color=BLACK, bbox=callout_style,
                arrowprops=dict(arrowstyle="-", color="#666666", lw=0.7,
                                shrinkA=2, shrinkB=3), zorder=6)
    ax.legend([latency_line, qps_line], ["Latency", "QPS"], loc="upper center",
              bbox_to_anchor=(0.5, 1.04), frameon=False, ncol=2,
              handlelength=1.2, columnspacing=0.8)

    ax = panel_axes(fig, right_rect, left=0.15, right=0.06, bottom=0.25, top=0.30)
    states = np.arange(3)
    residual = merge + other
    bottom = np.zeros(3)
    values = [base, scan, residual]
    colors = [BLUE, ORANGE, GREEN]
    names = ["Base search", "Delta scan", "Merge + other"]
    for values_j, color, name in zip(values, colors, names):
        ax.bar(states, values_j, bottom=bottom, width=0.62, color=color,
               edgecolor="white", linewidth=0.5, label=name, zorder=2)
        bottom += values_j
    ax.set_xticks(states, ["0", "50K", "100K"])
    ax.set_xlabel("Delta entries")
    ax.set_ylabel("Query time (ms)", labelpad=4)
    ax.set_ylim(0, 21.5)
    totals = base + scan + residual
    for i in range(3):
        ax.text(i, base[i] / 2, f"{base[i]:.4f}", ha="center", va="center",
                fontsize=7.0, color="white")
        if scan[i] > 0.1:
            ax.text(i, base[i] + scan[i] / 2, f"{scan[i]:.4f}", ha="center",
                    va="center", fontsize=7.0, color="white")
        ax.text(i, totals[i] + 0.35, f"{totals[i]:.2f}",
                ha="center", va="bottom", fontsize=7.1, color=BLACK)
    ax.legend(handles=[
        Rectangle((0, 0), 1, 1, facecolor=BLUE, edgecolor="white", label="Base search"),
        Rectangle((0, 0), 1, 1, facecolor=ORANGE, edgecolor="white", label="Delta scan"),
    ], loc="upper left", bbox_to_anchor=(0.0, 1.16), frameon=False,
       ncol=2, handlelength=1.0, columnspacing=0.9)
    fig.text(right_rect[0] + right_rect[2] * 0.96,
             right_rect[1] + right_rect[3] * 0.78,
             "Merge + other < 0.13 ms", ha="right", va="center",
             fontsize=7.1, color=GREEN, weight="bold")

    ax = panel_axes(fig, bottom_rect, left=0.08, right=0.08, bottom=0.25, top=0.20)
    states = np.array([0, 1])
    recovery_qps = np.array([77.7, 417.8])
    recovery_latency = np.array([12.8665, 2.3936])
    bars = ax.bar(states, recovery_qps, width=0.46, color=BLUE, edgecolor=BLACK,
                  linewidth=0.6, label="QPS", zorder=2)
    ax.set_xticks(states, ["Before rebuild\nRecall = 0.9980",
                           "After rebuild\nRecall = 0.9987"])
    ax.set_ylabel("QPS", color=BLUE_DARK, labelpad=4)
    ax.set_ylim(0, 470)
    ax.tick_params(axis="y", labelcolor=BLUE_DARK)
    ax2 = ax.twinx()
    ax2.plot(states, recovery_latency, color=ORANGE, marker="o", linewidth=1.4,
             markersize=4.0, label="Latency", zorder=3)
    ax2.set_ylabel("Latency (ms)", color=ORANGE, labelpad=4)
    ax2.set_ylim(1.5, 14.0)
    ax2.tick_params(axis="y", labelcolor=ORANGE)
    ax2.spines["top"].set_visible(False)
    for i, (bar, q, lat) in enumerate(zip(bars, recovery_qps, recovery_latency)):
        ax.text(bar.get_x() + bar.get_width() / 2, q + 12,
                f"{q:.1f}", ha="center", va="bottom", fontsize=7.2)
        y_offset = 8 if i == 0 else 8
        ax2.annotate(f"{lat:.2f} ms", (i, lat), xytext=(0, y_offset),
                     textcoords="offset points", ha="center", va="bottom",
                     fontsize=7.1, color=ORANGE,
                     bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none",
                               alpha=0.90), zorder=6)
    ax.legend(loc="upper left", frameon=False, handlelength=1.2)
    ax2.legend(loc="upper left", bbox_to_anchor=(0.10, 1.0), frameon=False,
               handlelength=1.2)
    export(fig, "fig_dynamic_growth")


def main() -> None:
    figure_core_idea()
    figure_snapshot_lifecycle()
    figure_main_comparison()
    figure_router_analysis()
    figure_attribute_scaling()
    figure_dynamic_maintenance()
    print(f"Wrote ACM insertion-safe vector figures to {OUT}")


if __name__ == "__main__":
    main()
