#!/usr/bin/env python3
"""Create paper-ready vector figures for the DANA paper."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle
from matplotlib.lines import Line2D
import numpy as np


OUT = Path(__file__).resolve().parents[1] / "paper_figures"
OUT.mkdir(parents=True, exist_ok=True)


COLORS = {
    "blue": "#2C5F8A",
    "blue_mid": "#6287A5",
    "blue_light": "#E4EDF4",
    "green": "#2E8B57",
    "green_light": "#E3F1E8",
    "orange": "#D9791F",
    "orange_light": "#F8E8D6",
    "red": "#B22222",
    "red_light": "#F3DDDD",
    "gray": "#666666",
    "gray_light": "#F0F0F0",
    "dark": "#222222",
    "purple": "#6F4BB3",
    "purple_light": "#EAE2F8",
}


def setup_ax(figsize=(7.2, 3.6)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def box(ax, xy, wh, text, fc, ec=None, fontsize=9, lw=1.25, radius=0.02):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        linewidth=lw,
        edgecolor=ec or COLORS["gray"],
        facecolor=fc,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=COLORS["dark"],
        linespacing=1.2,
        zorder=4,
    )
    return patch


def arrow(
    ax,
    start,
    end,
    color=None,
    lw=1.45,
    style="-|>",
    mutation=11,
    rad=0.0,
    shrink_a=0.0,
    shrink_b=1.2,
):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=mutation,
        linewidth=lw,
        color=color or COLORS["gray"],
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=shrink_a,
        shrinkB=shrink_b,
        capstyle="round",
        joinstyle="round",
        zorder=3,
    )
    ax.add_patch(patch)
    return patch


def save(fig, name):
    export = dict(bbox_inches="tight", pad_inches=0.025,
                  transparent=False, facecolor="white")
    fig.savefig(OUT / f"{name}.pdf", **export)
    fig.savefig(OUT / f"{name}.svg", **export)
    fig.savefig(OUT / f"{name}.png", dpi=600, **export)
    plt.close(fig)


def fig_intro_dynamic_framework():
    fig, ax = setup_ax((7.0, 2.55))

    ax.text(0.16, 0.92, "COUPLED FILTERING", ha="center", fontsize=9.2,
            weight="bold", color=COLORS["red"])
    ax.text(0.68, 0.92, "DANA", ha="center", fontsize=9.2,
            weight="bold", color=COLORS["blue"])
    ax.plot([0.31, 0.31], [0.12, 0.88], color="#C7CDD3", linewidth=1.1)

    # Existing post-filtering spends work on objects that are later rejected.
    ax.text(0.04, 0.74, "Post-filter", fontsize=8.6, weight="bold", color=COLORS["gray"])
    xs = [0.07, 0.12, 0.17, 0.22, 0.27]
    for i, x in enumerate(xs):
        fc = COLORS["green_light"] if i in (0, 4) else COLORS["red_light"]
        ec = COLORS["green"] if i in (0, 4) else COLORS["red"]
        ax.add_patch(Circle((x, 0.64), 0.016, facecolor=fc, edgecolor=ec, linewidth=1.4))
        if i < len(xs) - 1:
            ax.plot([x + 0.016, xs[i + 1] - 0.016], [0.64, 0.64],
                    color=COLORS["gray"], linewidth=1.5)
    ax.text(0.17, 0.55, "wasted work", ha="center", fontsize=8.5, color=COLORS["red"])

    # Hard pruning removes a bridge and breaks the route.
    ax.text(0.04, 0.39, "Hard pruning", fontsize=8.6, weight="bold", color=COLORS["gray"])
    for x, c in zip((0.08, 0.16, 0.25), (COLORS["blue"], COLORS["red"], COLORS["green"])):
        ax.add_patch(Circle((x, 0.28), 0.017, facecolor="white", edgecolor=c, linewidth=1.5))
    ax.plot([0.097, 0.143], [0.28, 0.28], color=COLORS["gray"], linewidth=1.5)
    ax.plot([0.177, 0.233], [0.28, 0.28], color=COLORS["gray"], linewidth=1.5,
            linestyle="--", alpha=0.35)
    ax.plot([0.148, 0.172], [0.268, 0.292], color=COLORS["red"], linewidth=1.7)
    ax.plot([0.148, 0.172], [0.292, 0.268], color=COLORS["red"], linewidth=1.7)
    ax.text(0.17, 0.19, "broken path", ha="center", fontsize=8.5, color=COLORS["red"])

    # DANA separates ordered navigation from full-predicate admission.
    box(ax, (0.35, 0.56), (0.10, 0.12), "Query", "white", COLORS["blue"], fontsize=8.6)
    box(ax, (0.49, 0.56), (0.11, 0.12), "Router", COLORS["blue_light"], COLORS["blue"], fontsize=8.6)
    arrow(ax, (0.45, 0.62), (0.49, 0.62), COLORS["blue"], mutation=10)
    ax.text(0.68, 0.77, "NAVIGATION", ha="center", fontsize=8.5,
            weight="bold", color=COLORS["blue"])
    ax.text(0.88, 0.77, "ADMISSION", ha="center", fontsize=8.5,
            weight="bold", color=COLORS["green"])
    for y, y0, label in zip(
        (0.64, 0.50, 0.36),
        (0.662, 0.620, 0.578),
        ("DSG a1", "DSG a2", "DSG am"),
    ):
        box(ax, (0.64, y), (0.10, 0.08), label, COLORS["blue_light"], COLORS["blue"], fontsize=8.5)
        selected = y == 0.50
        arrow(ax, (0.60, y0), (0.638, y + 0.04),
              COLORS["blue"] if selected else "#AAB4BF",
              lw=1.65 if selected else 0.95, mutation=9)
    box(ax, (0.81, 0.50), (0.14, 0.12), "Full predicate", COLORS["green_light"], COLORS["green"], fontsize=8.5)
    box(ax, (0.835, 0.31), (0.09, 0.10), "Top-k", COLORS["green_light"], COLORS["green"], fontsize=8.5)
    arrow(ax, (0.74, 0.54), (0.81, 0.56), COLORS["green"], lw=1.65, mutation=10)
    arrow(ax, (0.88, 0.50), (0.88, 0.41), COLORS["green"], lw=1.65, mutation=10)
    ax.plot([0.775, 0.775], [0.28, 0.74], color="#B8BEC5", linewidth=1.0,
            linestyle="--")
    ax.text(0.67, 0.17, "bridges remain\ntraversable", ha="center",
            fontsize=8.3, color=COLORS["gray"], linespacing=1.0)
    ax.text(0.88, 0.17, "feasible\nresults only", ha="center",
            fontsize=8.3, color=COLORS["green"], linespacing=1.0)

    save(fig, "fig_intro_dynamic_framework")


def fig_method_architecture():
    fig, ax = setup_ax((7.4, 3.25))
    ax.text(0.50, 0.91, "Why full-predicate hard filtering fails", ha="center",
            fontsize=9.4, weight="bold", color=COLORS["dark"])

    coords = {
        "start": (0.15, 0.48),
        "u1": (0.29, 0.66),
        "u2": (0.29, 0.31),
        "cut1": (0.48, 0.62),
        "cut2": (0.48, 0.35),
        "v1": (0.67, 0.66),
        "v2": (0.67, 0.31),
        "target": (0.84, 0.48),
    }
    edges = [
        ("start", "u1"), ("start", "u2"),
        ("u1", "cut1"), ("u1", "cut2"),
        ("u2", "cut1"), ("u2", "cut2"),
        ("cut1", "v1"), ("cut1", "v2"),
        ("cut2", "v1"), ("cut2", "v2"),
        ("v1", "target"), ("v2", "target"),
    ]
    for a, b in edges:
        x1, y1 = coords[a]
        x2, y2 = coords[b]
        alpha = 0.32 if a.startswith("cut") or b.startswith("cut") else 1.0
        ax.plot([x1, x2], [y1, y2], color="#8190A3", linewidth=1.25,
                alpha=alpha, solid_capstyle="round", zorder=1)

    ax.add_patch(FancyBboxPatch(
        (0.425, 0.22), 0.11, 0.52,
        boxstyle="round,pad=0.008,rounding_size=0.015",
        linewidth=1.0, linestyle="--", edgecolor=COLORS["red"],
        facecolor="#FBECEC", alpha=0.55,
    ))
    for name, (x, y) in coords.items():
        if name == "start":
            fc, ec = COLORS["blue_light"], COLORS["blue"]
        elif name.startswith("cut"):
            fc, ec = COLORS["red_light"], COLORS["red"]
        else:
            fc, ec = COLORS["green_light"], COLORS["green"]
        ax.add_patch(Circle((x, y), 0.030, facecolor=fc, edgecolor=ec, linewidth=1.4))
        if name.startswith("cut"):
            ax.plot([x - 0.020, x + 0.020], [y - 0.020, y + 0.020], color=COLORS["red"], lw=1.7)
            ax.plot([x - 0.020, x + 0.020], [y + 0.020, y - 0.020], color=COLORS["red"], lw=1.7)

    ax.text(0.15, 0.38, "query seed", ha="center", fontsize=9.0, color=COLORS["blue"])
    ax.text(0.48, 0.17, "infeasible cut set", ha="center", fontsize=9.0, color=COLORS["red"])
    ax.text(0.84, 0.38, "feasible target", ha="center", fontsize=9.0, color=COLORS["green"])

    save(fig, "fig1_extension_overview")


def fig_bridge_path():
    fig, ax = setup_ax((7.4, 3.20))
    ax.text(0.24, 0.90, "Hard pruning", ha="center", fontsize=9.7, weight="bold", color=COLORS["red"])
    ax.text(0.75, 0.90, "Bridge navigation", ha="center", fontsize=9.7, weight="bold", color=COLORS["blue"])

    def draw_path(x0, y, pruned):
        xs = [x0 + i * 0.064 for i in range(6)]
        offsets = [0.00, 0.06, -0.02, 0.07, -0.01, 0.06]
        ys = [y + offset for offset in offsets]
        types = ["start", "valid", "invalid", "invalid", "valid", "answer"]
        for i in range(5):
            style = "--" if pruned and i >= 2 else "-"
            alpha = 0.28 if pruned and i >= 2 else 1.0
            ax.plot([xs[i], xs[i + 1]], [ys[i], ys[i + 1]], linestyle=style,
                    color="#758398", linewidth=1.5, alpha=alpha)
        for i, (x, yy, kind) in enumerate(zip(xs, ys, types)):
            if kind == "start":
                fc, ec = COLORS["blue_light"], COLORS["blue"]
            elif kind == "invalid":
                fc, ec = COLORS["red_light"], COLORS["red"]
            else:
                fc, ec = COLORS["green_light"], COLORS["green"]
            alpha = 0.28 if pruned and i >= 3 else 1.0
            ax.add_patch(Circle((x, yy), 0.028, facecolor=fc, edgecolor=ec, linewidth=1.4, alpha=alpha))
        if pruned:
            x = xs[2]
            yy = ys[2]
            ax.plot([x - 0.020, x + 0.020], [yy - 0.020, yy + 0.020], color=COLORS["red"], lw=1.8)
            ax.plot([x - 0.020, x + 0.020], [yy + 0.020, yy - 0.020], color=COLORS["red"], lw=1.8)
        else:
            branch1 = (xs[2] + 0.025, y - 0.18)
            branch2 = (xs[4] - 0.010, y - 0.18)
            ax.plot([xs[2], branch1[0]], [ys[2], branch1[1]], color="#758398", lw=1.1)
            ax.plot([branch1[0], branch2[0]], [branch1[1], branch2[1]], color="#758398", lw=1.1)
            ax.plot([branch2[0], xs[4]], [branch2[1], ys[4]], color="#758398", lw=1.1)
            ax.add_patch(Circle(branch1, 0.022, facecolor=COLORS["gray_light"], edgecolor=COLORS["gray"], linewidth=1.1))
            ax.add_patch(Circle(branch2, 0.022, facecolor=COLORS["green_light"], edgecolor=COLORS["green"], linewidth=1.1))
        return xs, ys

    left_xs, left_ys = draw_path(0.06, 0.58, True)
    right_xs, right_ys = draw_path(0.54, 0.58, False)
    ax.text(left_xs[2], 0.40, "pruned", ha="center", fontsize=9.0, color=COLORS["red"])
    ax.text(left_xs[5], 0.40, "unreachable", ha="center", fontsize=9.0, color=COLORS["gray"])
    ax.text((right_xs[2] + right_xs[3]) / 2, 0.42, "infeasible bridges", ha="center", fontsize=9.0, color=COLORS["red"])
    box(ax, (0.68, 0.20), (0.18, 0.09), "admit feasible Top-k", COLORS["green_light"], COLORS["green"], fontsize=8.8)
    arrow(ax, (right_xs[5], right_ys[5] - 0.01), (0.77, 0.29), COLORS["green"], rad=-0.13, mutation=9)

    save(fig, "fig3_adaptive_query_pipeline")


def fig_snapshot_maintenance():
    fig, ax = setup_ax((7.0, 2.55))
    ax.add_patch(FancyBboxPatch(
        (0.015, 0.055), 0.31, 0.815,
        boxstyle="round,pad=0.006,rounding_size=0.015",
        facecolor="white", edgecolor="#C7CDD3", linewidth=0.9, zorder=0,
    ))
    ax.add_patch(FancyBboxPatch(
        (0.345, 0.055), 0.63, 0.815,
        boxstyle="round,pad=0.006,rounding_size=0.015",
        facecolor="white", edgecolor="#C7CDD3", linewidth=0.9, zorder=0,
    ))
    ax.text(0.03, 0.92, "(a) Rank semantics", ha="left", fontsize=8.4,
            weight="bold", color=COLORS["dark"])
    ax.text(0.36, 0.92, "(b) Snapshot lifecycle", ha="left", fontsize=8.4,
            weight="bold", color=COLORS["dark"])

    box(ax, (0.025, 0.47), (0.10, 0.16), "a=10\nrank 20",
        COLORS["blue_light"], COLORS["blue"], fontsize=8.2)
    box(ax, (0.155, 0.47), (0.10, 0.16), "a=90\nrank 500",
        COLORS["orange_light"], COLORS["orange"], fontsize=8.2)
    box(ax, (0.275, 0.485), (0.06, 0.13), "stale\nlabels",
        COLORS["red_light"], COLORS["red"], fontsize=8.0)
    arrow(ax, (0.125, 0.55), (0.155, 0.55), COLORS["orange"], mutation=9)
    arrow(ax, (0.255, 0.55), (0.275, 0.55), COLORS["red"], mutation=9)
    ax.text(0.14, 0.69, "update", ha="center", fontsize=7.8, color=COLORS["orange"])
    ax.text(0.265, 0.69, "rank shift", ha="center", fontsize=7.8, color=COLORS["red"])

    box(ax, (0.36, 0.48), (0.115, 0.15), "old Base $B_0$",
        COLORS["blue_light"], COLORS["blue"], fontsize=8.0)
    box(ax, (0.49, 0.49), (0.105, 0.13), "Delta /\nTombstone",
        COLORS["orange_light"], COLORS["orange"], fontsize=7.8)
    box(ax, (0.625, 0.58), (0.10, 0.13), "Rebuild $B_1$",
        COLORS["orange_light"], COLORS["orange"], fontsize=7.8)
    box(ax, (0.625, 0.38), (0.13, 0.11),
        "$(D_{\\mathrm{post}},T_{\\mathrm{post}})$", "white",
        COLORS["orange"], fontsize=7.3)
    box(ax, (0.79, 0.49), (0.15, 0.13),
        "$B_1 +$\n$D_{\\mathrm{post}}+T_{\\mathrm{post}}$",
        COLORS["blue_light"], COLORS["blue"], fontsize=7.3)
    arrow(ax, (0.475, 0.555), (0.49, 0.555), COLORS["orange"], mutation=8)
    arrow(ax, (0.595, 0.575), (0.625, 0.635), COLORS["orange"], mutation=8)
    arrow(ax, (0.595, 0.535), (0.625, 0.435), COLORS["orange"], mutation=8)
    arrow(ax, (0.725, 0.645), (0.79, 0.575), COLORS["blue"], mutation=8)
    arrow(ax, (0.755, 0.435), (0.79, 0.525), COLORS["orange"], mutation=8)
    ax.text(0.555, 0.75, "$|C| \\geq \\tau n_B$", ha="center", fontsize=7.8,
            color=COLORS["orange"])
    ax.text(0.86, 0.75, "atomic publish", ha="center", fontsize=7.8,
            color=COLORS["blue"])

    y_axis = 0.25
    ax.plot([0.38, 0.94], [y_axis, y_axis], color="#8E99A5", linewidth=1.15)
    for x, label in ((0.40, "$t_0$"), (0.61, "$t_1$\ncut"), (0.88, "$t_2$\nswap")):
        ax.plot([x, x], [y_axis - 0.025, y_axis + 0.025], color="#65717D", linewidth=1.0)
        ax.text(x, 0.12, label, ha="center", fontsize=7.4, color=COLORS["gray"])

    save(fig, "fig5_dynamic_update_rebuild")


def fig_storage_qps_tradeoff():
    methods = ["HNSW post", "HNSW in", "DSG attr0", "DSG attr1", "DANA"]
    storage = np.array([5.0, 5.0, 35.5, 35.5, 106.6])
    dist = np.array([351958.6, 334501.3, 14939.6, 14977.9, 12689.9])
    recall = [0.9993, 0.9992, 0.9983, 0.9968, 0.9993]
    facecolors = ["white", "#555555", "white", COLORS["blue_mid"], COLORS["blue"]]
    markers = ["^", "v", "s", "D", "o"]

    fig, ax = plt.subplots(figsize=(3.45, 2.45))
    for name, x, y, r, fc, marker in zip(methods, storage, dist, recall, facecolors, markers):
        ax.scatter(x, y, s=72, facecolor=fc, marker=marker, edgecolor="#202020",
                   linewidth=0.9, zorder=3)
    ax.annotate("HNSW post\n$R$=.9993", (5.0, 351958.6), xytext=(12, 28),
                textcoords="offset points", ha="left", fontsize=7.7,
                arrowprops=dict(arrowstyle="-", color="#555555", lw=0.8))
    ax.annotate("HNSW in\n$R$=.9992", (5.0, 334501.3), xytext=(12, -29),
                textcoords="offset points", ha="left", fontsize=7.7,
                arrowprops=dict(arrowstyle="-", color="#555555", lw=0.8))
    ax.annotate("DSG attr0\n$R$=.9983", (35.5, 14939.6), xytext=(-70, 40),
                textcoords="offset points", ha="left", fontsize=7.7,
                arrowprops=dict(arrowstyle="-", color=COLORS["blue_mid"], lw=0.8))
    ax.annotate("DSG attr1\n$R$=.9968", (35.5, 14977.9), xytext=(12, 42),
                textcoords="offset points", ha="left", fontsize=7.7,
                arrowprops=dict(arrowstyle="-", color=COLORS["blue_mid"], lw=0.8))
    ax.annotate("DANA\n$R$=.9993", (106.6, 12689.9), xytext=(-8, 18),
                textcoords="offset points", ha="right", fontsize=7.7,
                arrowprops=dict(arrowstyle="-", color=COLORS["blue"], lw=0.8))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(3.5, 150)
    ax.set_ylim(8_000, 800_000)
    ax.set_xlabel("Index storage (GB, log)", fontsize=9.0)
    ax.set_ylabel("Distance evaluations/query (log)", fontsize=9.0)
    ax.tick_params(axis="both", labelsize=8.0, width=0.8, length=3)
    ax.grid(True, which="major", color="#D9DEE3", linewidth=0.55, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.subplots_adjust(left=0.20, right=0.97, bottom=0.18, top=0.96)
    save(fig, "fig_deep10m_work_comparison")


def fig_attribute_scalability():
    m = np.arange(1, 7)
    storage = np.array([2.06, 4.13, 6.19, 9.47, 12.76, 16.04])
    recall = np.array([0.9992, 0.9989, 0.9964, 0.9849, 0.9217, 0.8498])
    tuned_m = np.array([4, 5, 6])
    tuned_recall = np.array([0.9994, 0.9984, 0.9991])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(3.45, 3.05), sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.28},
    )
    ax1.bar(m, storage, width=0.58, color=COLORS["blue_mid"], edgecolor="#202020", linewidth=0.9)
    ax2.plot(m, recall, marker="o", color=COLORS["green"], linewidth=1.8,
             markersize=4.8, linestyle="-", markeredgecolor="#202020",
             markeredgewidth=0.7, label="Fixed ef = 512")
    ax2.scatter(tuned_m, tuned_recall, marker="D", s=27, facecolor="white",
                edgecolor=COLORS["blue"], linewidth=1.1, zorder=4,
                label="Tuned ef")
    ax1.set_ylabel("Index size (GB)", fontsize=9.0)
    ax2.set_ylabel("Recall", fontsize=9.0)
    ax2.set_xlabel("Number of deployed attributes", fontsize=9.0)
    ax2.set_xticks(m)
    ax1.set_ylim(0, 18)
    ax2.set_ylim(0.82, 1.01)
    for ax in (ax1, ax2):
        ax.grid(False)
        ax.tick_params(axis="both", labelsize=8.0, width=0.8, length=3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax1.text(0.02, 0.91, "a  Index storage", transform=ax1.transAxes, fontsize=8.5,
             weight="bold", color=COLORS["dark"])
    ax2.set_title("b  Fixed-budget recall", loc="left", fontsize=8.5,
                  weight="bold", color=COLORS["dark"], pad=5)
    for xi, value in zip(m, storage):
        ax1.text(xi, value + 0.35, f"{value:.2f}", ha="center", va="bottom",
                 fontsize=7.0, color=COLORS["dark"])
    ax2.text(5.86, 0.858, "0.8498", ha="right", va="bottom",
             fontsize=7.5, color=COLORS["green"])
    ax2.legend(loc="lower left", fontsize=7.5, frameon=False, handletextpad=0.4,
               borderaxespad=0.2)
    fig.subplots_adjust(left=0.20, right=0.98, bottom=0.15, top=0.98, hspace=0.28)
    save(fig, "fig_attribute_scalability")


def fig_bridge_ablation_chart():
    labels = ["Post-filter\nDSG", "DANA"]
    recall = [0.937, 1.000]
    colors = [COLORS["red"], COLORS["green"]]
    fig, ax = plt.subplots(figsize=(3.20, 2.15))
    bars = ax.bar(labels, recall, width=0.56, color=colors, edgecolor="#333333",
                  linewidth=0.9)
    bars[0].set_hatch("/")
    bars[1].set_hatch(".")
    for bar, value in zip(bars, recall):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.003,
                f"{value:.3f}", ha="center", va="bottom", fontsize=8.5,
                weight="bold")
    ax.set_ylim(0.0, 1.08)
    ax.set_ylabel("Recall", fontsize=9.0)
    ax.tick_params(axis="both", labelsize=8.3, width=0.8, length=3)
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    save(fig, "fig_bridge_ablation")


def fig_dynamic_growth():
    delta = np.array([0, 10, 20, 40, 50, 100, 200])
    latency = np.array([10.1345, 10.4959, 10.8661, 10.3740, 11.9353, 22.1365, 27.3521])
    qps = np.array([98.7, 95.3, 92.0, 96.4, 83.8, 45.2, 36.6])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(3.45, 3.05), sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12},
    )
    ax1.plot(delta, latency, marker="o", color=COLORS["orange"], linewidth=1.8,
             markersize=4.7, markeredgecolor="#202020", markeredgewidth=0.7, zorder=3)
    ax2.plot(delta, qps, marker="s", color=COLORS["gray"], linewidth=1.8,
             markersize=4.5, linestyle="--", markeredgecolor="#202020",
             markeredgewidth=0.7, zorder=3)
    for ax in (ax1, ax2):
        ax.grid(False)
        ax.tick_params(axis="both", labelsize=8.0, width=0.8, length=3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax1.set_ylabel("Latency (ms)", fontsize=9.0)
    ax2.set_ylabel("QPS", fontsize=9.0)
    ax2.set_xlabel("Retained Delta entries (K)", fontsize=9.0)
    ax1.set_xlim(-5, 215)
    ax1.set_ylim(4, 31)
    ax2.set_ylim(25, 105)
    ax1.text(0.03, 0.90, "(a) Latency", transform=ax1.transAxes,
             fontsize=8.5, weight="bold", color=COLORS["dark"])
    ax2.text(0.97, 0.89, "(b) Throughput", transform=ax2.transAxes,
             ha="right", fontsize=8.5, weight="bold", color=COLORS["dark"])
    fig.subplots_adjust(left=0.20, right=0.98, bottom=0.15, top=0.98, hspace=0.12)
    save(fig, "fig_dynamic_growth")


def fig_dana_overview():
    fig, ax = setup_ax((7.4, 3.7))
    ax.text(0.02, 0.95, "DANA overview", fontsize=12, weight="bold")

    box(ax, (0.04, 0.58), (0.16, 0.18), "Objects\nvectors + attrs", COLORS["gray_light"])
    box(ax, (0.04, 0.25), (0.16, 0.18), "Query\nq + ranges", COLORS["orange_light"], COLORS["orange"])

    attr_y = [0.72, 0.50, 0.28]
    for i, y in enumerate(attr_y):
        box(ax, (0.28, y), (0.16, 0.13), f"Sort by attr{i}\nrank space", COLORS["blue_light"], COLORS["blue"], fontsize=8)
        box(ax, (0.49, y), (0.16, 0.13), f"DSG attr{i}\nG{i}", COLORS["green_light"], COLORS["green"], fontsize=8)
        arrow(ax, (0.44, y + 0.065), (0.49, y + 0.065), COLORS["gray"])

    arrow(ax, (0.20, 0.67), (0.28, 0.785), COLORS["gray"])
    arrow(ax, (0.20, 0.67), (0.28, 0.565), COLORS["gray"])
    arrow(ax, (0.20, 0.67), (0.28, 0.345), COLORS["gray"])

    box(ax, (0.28, 0.06), (0.16, 0.13), "Range-to-rank\nconversion", COLORS["orange_light"], COLORS["orange"], fontsize=8)
    arrow(ax, (0.20, 0.34), (0.28, 0.125), COLORS["orange"])

    box(ax, (0.70, 0.56), (0.20, 0.15), "Adaptive selection\nmin rank span", COLORS["purple_light"], COLORS["purple"], fontsize=8.5)
    for y in attr_y:
        arrow(ax, (0.65, y + 0.065), (0.70, 0.635), COLORS["green"], lw=1.0)
    arrow(ax, (0.44, 0.125), (0.70, 0.59), COLORS["orange"], lw=1.0, rad=0.12)

    box(ax, (0.70, 0.28), (0.20, 0.15), "In-search\nconjunctive filter", COLORS["red_light"], COLORS["red"], fontsize=8.5)
    arrow(ax, (0.80, 0.56), (0.80, 0.43), COLORS["purple"])

    box(ax, (0.70, 0.06), (0.20, 0.13), "Top-k valid\noriginal IDs", COLORS["gray_light"], COLORS["gray"], fontsize=8.5)
    arrow(ax, (0.80, 0.28), (0.80, 0.19), COLORS["red"])

    ax.text(0.50, 0.235, "rank -> original_id", fontsize=8, color=COLORS["gray"])
    arrow(ax, (0.66, 0.30), (0.72, 0.18), COLORS["gray"], lw=1.0)

    save(fig, "fig_dana_overview")


def fig_in_search_filtering():
    fig, ax = setup_ax((7.4, 3.6))
    ax.text(0.02, 0.95, "In-search filtering: navigation is separated from result admission", fontsize=12, weight="bold")

    xs = np.linspace(0.10, 0.54, 6)
    ys = [0.62, 0.75, 0.51, 0.68, 0.43, 0.57]
    valid = [True, False, False, True, False, True]
    for i, (x, y) in enumerate(zip(xs, ys)):
        fc = COLORS["green_light"] if valid[i] else COLORS["red_light"]
        ec = COLORS["green"] if valid[i] else COLORS["red"]
        ax.add_patch(Circle((x, y), 0.035, facecolor=fc, edgecolor=ec, linewidth=1.2))
        ax.text(x, y, f"v{i}", ha="center", va="center", fontsize=8)
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 5), (4, 5)]
    for a, b in edges:
        ax.add_line(Line2D([xs[a], xs[b]], [ys[a], ys[b]], color="#9AA0A6", linewidth=1.1, zorder=0))

    box(ax, (0.06, 0.16), (0.18, 0.12), "Invalid node\ncan be expanded", COLORS["red_light"], COLORS["red"], fontsize=8)
    arrow(ax, (0.20, 0.28), (xs[2], ys[2] - 0.04), COLORS["red"], rad=-0.1)
    box(ax, (0.34, 0.16), (0.18, 0.12), "Valid node\ncan enter results", COLORS["green_light"], COLORS["green"], fontsize=8)
    arrow(ax, (0.43, 0.28), (xs[3], ys[3] - 0.04), COLORS["green"], rad=0.1)

    box(ax, (0.63, 0.69), (0.25, 0.12), "candidate_set\nnodes to expand", COLORS["blue_light"], COLORS["blue"])
    box(ax, (0.63, 0.48), (0.25, 0.12), "exploration_top\nbounded by search_ef", COLORS["purple_light"], COLORS["purple"])
    box(ax, (0.63, 0.27), (0.25, 0.12), "result_top\nvalid top-k only", COLORS["green_light"], COLORS["green"])

    arrow(ax, (0.54, 0.63), (0.63, 0.75), COLORS["blue"])
    arrow(ax, (0.54, 0.58), (0.63, 0.54), COLORS["purple"])
    arrow(ax, (0.54, 0.53), (0.63, 0.33), COLORS["green"])

    ax.text(0.63, 0.17, "Full predicate is checked only for result admission.", fontsize=8.5, color=COLORS["gray"])
    save(fig, "fig_in_search_filtering")


def fig_dynamic_dana():
    fig, ax = setup_ax((7.4, 4.0))
    ax.text(0.02, 0.95, "Dynamic DANA: Base + Delta + Tombstone + rebuild", fontsize=12, weight="bold")

    box(ax, (0.06, 0.58), (0.22, 0.17), "Base DANA\nstatic snapshot", COLORS["blue_light"], COLORS["blue"])
    box(ax, (0.06, 0.28), (0.22, 0.16), "Tombstone\nmasked base IDs", COLORS["red_light"], COLORS["red"])
    box(ax, (0.36, 0.60), (0.16, 0.13), "Epoch 0\nD0 / T0", COLORS["orange_light"], COLORS["orange"], fontsize=8.2)
    box(ax, (0.54, 0.60), (0.16, 0.13), "Epoch 1\nD1 / T1", COLORS["orange_light"], COLORS["orange"], fontsize=8.2)
    box(ax, (0.38, 0.28), (0.22, 0.16), "Exact scan\non effective Delta", COLORS["orange_light"], COLORS["orange"], fontsize=8.0)

    box(ax, (0.72, 0.58), (0.20, 0.17), "Merge\nBase + Delta", COLORS["green_light"], COLORS["green"])
    box(ax, (0.72, 0.28), (0.20, 0.16), "Top-k latest\nstable IDs", COLORS["gray_light"], COLORS["gray"])

    arrow(ax, (0.28, 0.665), (0.72, 0.665), COLORS["blue"])
    arrow(ax, (0.52, 0.665), (0.54, 0.665), COLORS["orange"])
    arrow(ax, (0.70, 0.665), (0.72, 0.665), COLORS["orange"])
    arrow(ax, (0.17, 0.58), (0.17, 0.44), COLORS["red"])
    arrow(ax, (0.46, 0.60), (0.46, 0.44), COLORS["orange"])
    arrow(ax, (0.62, 0.60), (0.55, 0.44), COLORS["orange"])
    arrow(ax, (0.82, 0.58), (0.82, 0.44), COLORS["green"])

    box(ax, (0.08, 0.07), (0.22, 0.13), "Rebuild trigger\nchanged IDs >= tau nB", COLORS["purple_light"], COLORS["purple"], fontsize=7.6)
    box(ax, (0.36, 0.07), (0.25, 0.13), "Absorb captured\nD0 / T0 into B1", COLORS["purple_light"], COLORS["purple"], fontsize=7.4)
    box(ax, (0.68, 0.07), (0.25, 0.13), "Retain post-cutoff\nD1 / T1", COLORS["purple_light"], COLORS["purple"], fontsize=7.4)
    arrow(ax, (0.30, 0.135), (0.39, 0.135), COLORS["purple"])
    arrow(ax, (0.61, 0.135), (0.68, 0.135), COLORS["purple"])
    arrow(ax, (0.81, 0.20), (0.24, 0.58), COLORS["purple"], rad=0.24)

    ax.text(0.33, 0.235, "rank -> snapshot local ID -> stable original ID", fontsize=8, color=COLORS["gray"])
    save(fig, "fig_dynamic_dana")


def fig_indexed_attrs_tradeoff():
    attrs = ["{0}", "{0,1}", "{0,1,2}"]
    size = np.array([35.5, 71.0, 106.6])
    recall = np.array([0.9983, 0.9988, 0.9993])
    qps = np.array([91.2, 87.2, 79.8])
    dist = np.array([14939.6, 13822.6, 12689.9])

    fig, ax1 = plt.subplots(figsize=(6.4, 3.6))
    x = np.arange(len(attrs))
    ax1.bar(x - 0.18, size, width=0.36, color=COLORS["blue"], label="Index size (GB)")
    ax1.set_ylabel("Index size (GB)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(attrs)
    ax1.set_xlabel("Indexed attributes")
    ax1.set_ylim(0, 120)
    ax1.grid(axis="y", color="#E0E0E0", linewidth=0.7)

    ax2 = ax1.twinx()
    ax2.plot(x, qps, marker="o", color=COLORS["orange"], linewidth=2, label="QPS")
    ax2.plot(x, dist / 200, marker="s", color=COLORS["green"], linewidth=2, label="Dist / 200")
    ax2.set_ylabel("QPS / scaled distance")
    ax2.set_ylim(55, 100)

    for i, r in enumerate(recall):
        ax1.text(i, size[i] + 4, f"R={r:.4f}", ha="center", fontsize=8)

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper left", fontsize=8, frameon=False)
    ax1.set_title("Index-budget trade-off on DEEP-10M", fontsize=11, weight="bold")
    fig.tight_layout()
    save(fig, "fig_indexed_attrs_tradeoff")


def fig_hybrid_boundary():
    profiles = ["tiny", "small", "medium", "attr0", "attr1", "attr2", "balanced", "broad"]
    pref_ms = np.array([2.5390, 4.6250, 22.2341, 145.4736, 149.6556, 149.7868, 123.0043, 725.8097])
    dsg_ms = np.array([3.2443, 4.0396, 14.0083, 9.9573, 8.1526, 18.7339, 11.2424, 13.3896])
    dsg_recall = np.array([0.2920, 0.0137, 0.4176, 0.9976, 0.9992, 0.9992, 0.9976, 1.0000])

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    x = np.arange(len(profiles))
    w = 0.35
    ax.bar(x - w / 2, pref_ms, width=w, color=COLORS["gray"], label="Prefilter ms")
    ax.bar(x + w / 2, dsg_ms, width=w, color=COLORS["blue"], label="DANA ms")
    ax.set_yscale("log")
    ax.set_ylabel("Latency (ms, log scale)")
    ax.set_xticks(x)
    ax.set_xticklabels(profiles, rotation=25, ha="right")
    ax.grid(axis="y", color="#E0E0E0", linewidth=0.7)
    ax.set_title("Selectivity boundary and Hybrid routing", fontsize=11, weight="bold")

    for i, r in enumerate(dsg_recall):
        color = COLORS["red"] if r < 0.95 else COLORS["green"]
        ax.text(i + w / 2, max(dsg_ms[i] * 1.18, 0.2), f"R={r:.2f}", ha="center", fontsize=7, color=color)

    ax.axvline(2.5, color=COLORS["red"], linestyle="--", linewidth=1)
    ax.text(1.2, 500, "Prefilter fallback", ha="center", fontsize=8, color=COLORS["red"])
    ax.text(5.4, 500, "Use DANA", ha="center", fontsize=8, color=COLORS["blue"])
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    fig.tight_layout()
    save(fig, "fig_hybrid_boundary")


def fig_bigvectorbench_curve():
    ef = np.array([128, 256, 512, 768, 1024, 1536, 2048, 3072, 4096])
    recall = np.array([0.8008, 0.8519, 0.8846, 0.9010, 0.9117, 0.9266, 0.9389, 0.9464, 0.9508])
    qps = np.array([2436.7, 1068.2, 858.9, 606.8, 493.0, 391.9, 257.9, 234.2, 189.6])
    dist = np.array([1065.2, 1685.2, 2665.3, 3450.5, 4118.1, 5245.7, 6209.7, 7818.1, 9165.4])

    post_recall = np.array([0.5182, 0.6149, 0.6873, 0.7431, 0.7807])
    post_dist = np.array([10398.8, 20292.4, 39562.8, 76157.2, 142860.1])
    ins_recall = np.array([0.8232, 0.8298, 0.8337, 0.8368, 0.8390])
    ins_dist = np.array([640554.5, 996686.4, 1392908.3, 1814964.6, 2219654.9])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.3))
    ax1.plot(recall, qps, marker="o", color=COLORS["blue"], label="DANA")
    ax1.set_xlabel("Recall")
    ax1.set_ylabel("QPS")
    ax1.grid(color="#E0E0E0", linewidth=0.7)
    ax1.set_title("Recall-QPS", fontsize=10, weight="bold")
    ax1.legend(fontsize=8, frameon=False)

    ax2.plot(recall, dist, marker="o", color=COLORS["blue"], label="DANA")
    ax2.plot(post_recall, post_dist, marker="s", color=COLORS["orange"], label="HNSW post-filter")
    ax2.plot(ins_recall, ins_dist, marker="^", color=COLORS["red"], label="HNSW in-search")
    ax2.set_yscale("log")
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Distance computations")
    ax2.grid(color="#E0E0E0", linewidth=0.7)
    ax2.set_title("Recall-search work", fontsize=10, weight="bold")
    ax2.legend(fontsize=7.5, frameon=False, loc="lower right")

    fig.suptitle("BigVectorBench app_reviews", fontsize=11, weight="bold")
    fig.tight_layout()
    save(fig, "fig_bigvectorbench_curve")


def fig_paper_structure():
    fig, ax = setup_ax((7.4, 4.0))
    ax.text(0.02, 0.95, "Paper structure", fontsize=12, weight="bold")

    box(ax, (0.05, 0.72), (0.20, 0.12), "Problem\nmulti-attribute\nfiltered ANN", COLORS["gray_light"])
    box(ax, (0.31, 0.72), (0.20, 0.12), "Background\nsingle-attribute\nDSG", COLORS["blue_light"], COLORS["blue"])
    box(ax, (0.57, 0.72), (0.20, 0.12), "Extension\nconjunctive\nrange filters", COLORS["orange_light"], COLORS["orange"])
    box(ax, (0.35, 0.49), (0.22, 0.13), "DANA\nmethod design", COLORS["green_light"], COLORS["green"])
    box(ax, (0.13, 0.28), (0.22, 0.13), "Static query\nadaptive navigation\n+ in-search filtering", COLORS["purple_light"], COLORS["purple"], fontsize=8)
    box(ax, (0.57, 0.28), (0.22, 0.13), "Dynamic layer\nBase + Delta\n+ Tombstone", COLORS["red_light"], COLORS["red"], fontsize=8)
    box(ax, (0.35, 0.08), (0.22, 0.13), "Evaluation\nlarge scale + public\nfiltered ANN", COLORS["gray_light"], COLORS["gray"], fontsize=8)

    arrow(ax, (0.25, 0.78), (0.31, 0.78))
    arrow(ax, (0.51, 0.78), (0.57, 0.78))
    arrow(ax, (0.67, 0.72), (0.51, 0.62), COLORS["orange"])
    arrow(ax, (0.41, 0.72), (0.43, 0.62), COLORS["blue"])
    arrow(ax, (0.46, 0.49), (0.30, 0.41), COLORS["purple"])
    arrow(ax, (0.46, 0.49), (0.68, 0.41), COLORS["red"])
    arrow(ax, (0.24, 0.28), (0.42, 0.21), COLORS["purple"])
    arrow(ax, (0.68, 0.28), (0.50, 0.21), COLORS["red"])

    save(fig, "fig_paper_structure")


def fig_dsg_to_dana():
    fig, ax = setup_ax((7.4, 3.8))
    ax.text(0.02, 0.95, "From DSG to DANA", fontsize=12, weight="bold")

    ax.text(0.19, 0.85, "Original DSG", fontsize=10, weight="bold", ha="center")
    box(ax, (0.06, 0.65), (0.26, 0.11), "one numeric attribute", COLORS["blue_light"], COLORS["blue"])
    box(ax, (0.06, 0.48), (0.26, 0.11), "one rank order", COLORS["blue_light"], COLORS["blue"])
    box(ax, (0.06, 0.31), (0.26, 0.11), "one DSG", COLORS["green_light"], COLORS["green"])
    box(ax, (0.06, 0.14), (0.26, 0.11), "range-filtered ANN", COLORS["gray_light"], COLORS["gray"])
    arrow(ax, (0.19, 0.65), (0.19, 0.59), COLORS["blue"])
    arrow(ax, (0.19, 0.48), (0.19, 0.42), COLORS["green"])
    arrow(ax, (0.19, 0.31), (0.19, 0.25), COLORS["gray"])

    ax.text(0.73, 0.85, "DANA", fontsize=10, weight="bold", ha="center")
    box(ax, (0.59, 0.65), (0.28, 0.11), "m numerical attributes", COLORS["orange_light"], COLORS["orange"])
    box(ax, (0.50, 0.48), (0.18, 0.11), "rank attr0", COLORS["blue_light"], COLORS["blue"], fontsize=8)
    box(ax, (0.70, 0.48), (0.18, 0.11), "rank attr1..m", COLORS["blue_light"], COLORS["blue"], fontsize=8)
    box(ax, (0.50, 0.31), (0.18, 0.11), "DSG attr0", COLORS["green_light"], COLORS["green"], fontsize=8)
    box(ax, (0.70, 0.31), (0.18, 0.11), "DSG attr1..m", COLORS["green_light"], COLORS["green"], fontsize=8)
    box(ax, (0.58, 0.14), (0.30, 0.11), "conjunctive filtered ANN", COLORS["gray_light"], COLORS["gray"], fontsize=8)
    arrow(ax, (0.64, 0.65), (0.59, 0.59), COLORS["orange"])
    arrow(ax, (0.80, 0.65), (0.80, 0.59), COLORS["orange"])
    arrow(ax, (0.59, 0.48), (0.59, 0.42), COLORS["green"])
    arrow(ax, (0.80, 0.48), (0.80, 0.42), COLORS["green"])
    arrow(ax, (0.59, 0.31), (0.68, 0.25), COLORS["gray"])
    arrow(ax, (0.80, 0.31), (0.73, 0.25), COLORS["gray"])

    arrow(ax, (0.34, 0.50), (0.48, 0.50), COLORS["purple"], lw=1.8)
    ax.text(0.41, 0.55, "preserve\n1D rank semantics", fontsize=8, ha="center", color=COLORS["purple"])

    save(fig, "fig_dsg_to_dana")


def fig_index_construction():
    fig, ax = setup_ax((7.4, 4.0))
    ax.text(0.02, 0.95, "Per-attribute index construction", fontsize=12, weight="bold")

    box(ax, (0.05, 0.62), (0.20, 0.14), "Original vectors\nX: N x d", COLORS["gray_light"])
    box(ax, (0.05, 0.35), (0.20, 0.14), "Attribute table\nA: N x m", COLORS["orange_light"], COLORS["orange"])

    rows = [(0.33, 0.72, "attr0"), (0.33, 0.50, "attr1"), (0.33, 0.28, "attrk")]
    for x, y, name in rows:
        box(ax, (x, y), (0.16, 0.10), f"sort by {name}", COLORS["blue_light"], COLORS["blue"], fontsize=8)
        box(ax, (0.54, y), (0.16, 0.10), f"reorder\nvectors", COLORS["purple_light"], COLORS["purple"], fontsize=8)
        box(ax, (0.75, y), (0.16, 0.10), f"DSG {name}", COLORS["green_light"], COLORS["green"], fontsize=8)
        arrow(ax, (0.49, y + 0.05), (0.54, y + 0.05), COLORS["purple"])
        arrow(ax, (0.70, y + 0.05), (0.75, y + 0.05), COLORS["green"])
        arrow(ax, (0.25, 0.42), (x, y + 0.05), COLORS["orange"], lw=1.0)
        arrow(ax, (0.25, 0.69), (0.54, y + 0.05), COLORS["gray"], lw=1.0)

    box(ax, (0.33, 0.08), (0.24, 0.12), "rank_to_original\nfor every indexed attr", COLORS["gray_light"], COLORS["gray"], fontsize=8)
    arrow(ax, (0.41, 0.28), (0.45, 0.20), COLORS["gray"])
    box(ax, (0.66, 0.08), (0.25, 0.12), "DANA index set\n{G_j, mappings}", COLORS["green_light"], COLORS["green"], fontsize=8)
    arrow(ax, (0.57, 0.14), (0.66, 0.14), COLORS["green"])
    arrow(ax, (0.83, 0.28), (0.80, 0.20), COLORS["green"])

    save(fig, "fig_index_construction")


def fig_adaptive_navigation():
    fig, ax = setup_ax((7.4, 3.6))
    ax.text(0.02, 0.95, "Adaptive navigation attribute selection", fontsize=12, weight="bold")

    box(ax, (0.04, 0.58), (0.18, 0.17), "Query\nq + ranges\nR0...Rm", COLORS["orange_light"], COLORS["orange"])
    box(ax, (0.30, 0.72), (0.18, 0.10), "rank interval 0\nspan0", COLORS["blue_light"], COLORS["blue"], fontsize=8)
    box(ax, (0.30, 0.53), (0.18, 0.10), "rank interval 1\nspan1", COLORS["blue_light"], COLORS["blue"], fontsize=8)
    box(ax, (0.30, 0.34), (0.18, 0.10), "rank interval m\nspanm", COLORS["blue_light"], COLORS["blue"], fontsize=8)
    box(ax, (0.58, 0.55), (0.19, 0.15), "choose\nminimum span", COLORS["purple_light"], COLORS["purple"])
    box(ax, (0.58, 0.29), (0.19, 0.12), "navigate in\nDSG attr j*", COLORS["green_light"], COLORS["green"])
    box(ax, (0.58, 0.08), (0.19, 0.12), "all-attribute\nresult filter", COLORS["red_light"], COLORS["red"])

    arrow(ax, (0.22, 0.67), (0.30, 0.77), COLORS["orange"])
    arrow(ax, (0.22, 0.67), (0.30, 0.58), COLORS["orange"])
    arrow(ax, (0.22, 0.67), (0.30, 0.39), COLORS["orange"])
    arrow(ax, (0.48, 0.77), (0.58, 0.64), COLORS["blue"])
    arrow(ax, (0.48, 0.58), (0.58, 0.62), COLORS["blue"])
    arrow(ax, (0.48, 0.39), (0.58, 0.60), COLORS["blue"])
    arrow(ax, (0.675, 0.55), (0.675, 0.41), COLORS["purple"])
    arrow(ax, (0.675, 0.29), (0.675, 0.20), COLORS["green"])

    ax.text(0.82, 0.59, r"$j^*=\arg\min_{j\in\mathcal{I}}(R_j-L_j+1)$", fontsize=11)
    ax.text(0.82, 0.37, "Unindexed attributes\nstill filter results", fontsize=8.5, color=COLORS["gray"])

    save(fig, "fig_adaptive_navigation")


def fig_no_hard_pruning():
    fig, ax = setup_ax((7.4, 3.8))
    ax.text(0.02, 0.94, "Why non-navigation predicates are not hard-pruned", fontsize=12, weight="bold")

    ax.text(0.25, 0.83, "Hard prune", fontsize=10, weight="bold", ha="center", color=COLORS["red"])
    ax.text(0.74, 0.83, "DANA", fontsize=10, weight="bold", ha="center", color=COLORS["green"])

    def path_nodes(x0, y, show_bridge=True):
        xs = [x0, x0 + 0.15, x0 + 0.30]
        labels = ["current", "invalid\nbridge", "valid\nnear"]
        cols = [(COLORS["blue_light"], COLORS["blue"]),
                (COLORS["red_light"], COLORS["red"]),
                (COLORS["green_light"], COLORS["green"])]
        for i, x in enumerate(xs):
            fc, ec = cols[i]
            alpha = 0.20 if i == 1 and not show_bridge else 1.0
            ax.add_patch(Circle((x, y), 0.048, facecolor=fc, edgecolor=ec, linewidth=1.3, alpha=alpha))
            ax.text(x, y, labels[i], ha="center", va="center", fontsize=6.8, alpha=alpha)
        ax.add_line(Line2D([xs[0] + 0.05, xs[1] - 0.05], [y, y], color=COLORS["gray"], linewidth=1.3, alpha=0.4 if not show_bridge else 1))
        ax.add_line(Line2D([xs[1] + 0.05, xs[2] - 0.05], [y, y], color=COLORS["gray"], linewidth=1.3, alpha=0.25 if not show_bridge else 1))
        if not show_bridge:
            ax.plot([xs[1] - 0.035, xs[1] + 0.035], [y - 0.035, y + 0.035], color=COLORS["red"], lw=2)
            ax.plot([xs[1] - 0.035, xs[1] + 0.035], [y + 0.035, y - 0.035], color=COLORS["red"], lw=2)

    path_nodes(0.08, 0.58, show_bridge=False)
    box(ax, (0.08, 0.22), (0.34, 0.15), "Invalid bridge is removed\nvalid near point is unreachable\nRecall decreases",
        COLORS["red_light"], COLORS["red"], fontsize=8)
    arrow(ax, (0.25, 0.53), (0.25, 0.37), COLORS["red"])

    path_nodes(0.57, 0.58, show_bridge=True)
    box(ax, (0.55, 0.22), (0.36, 0.15), "Invalid bridge is expanded\nbut never admitted to results\nConnectivity is preserved",
        COLORS["green_light"], COLORS["green"], fontsize=8)
    arrow(ax, (0.74, 0.53), (0.74, 0.37), COLORS["green"])

    save(fig, "fig_no_hard_pruning")


def fig_experiment_matrix():
    fig, ax = setup_ax((7.4, 4.0))
    ax.text(0.02, 0.95, "Experiment design matrix", fontsize=12, weight="bold")

    center = (0.46, 0.52)
    ax.add_patch(Circle(center, 0.075, facecolor=COLORS["gray_light"], edgecolor=COLORS["gray"], linewidth=1.4))
    ax.text(center[0], center[1], "Evaluation", ha="center", va="center", fontsize=9, weight="bold")

    items = [
        ((0.07, 0.72), "Correctness\nvector sanity\nexact baseline", COLORS["blue_light"], COLORS["blue"]),
        ((0.37, 0.76), "Static search\nDEEP-1M/10M\nHNSW baselines", COLORS["green_light"], COLORS["green"]),
        ((0.68, 0.72), "Index budget\n{0}, {0,1},\n{0,1,2}", COLORS["purple_light"], COLORS["purple"]),
        ((0.07, 0.24), "Hybrid boundary\ntiny to broad\nselectivity", COLORS["orange_light"], COLORS["orange"]),
        ((0.37, 0.16), "Dynamic updates\ninsert/update/delete\nrebuild", COLORS["red_light"], COLORS["red"]),
        ((0.68, 0.24), "Public dataset\nBigVectorBench\napp_reviews", COLORS["gray_light"], COLORS["gray"]),
    ]
    for (x, y), text, fc, ec in items:
        box(ax, (x, y), (0.22, 0.13), text, fc, ec, fontsize=8)
        arrow(ax, center, (x + 0.11, y + 0.065), ec, lw=1.0)

    save(fig, "fig_experiment_matrix")


def fig_main_findings():
    fig, ax = setup_ax((7.4, 3.6))
    ax.text(0.02, 0.95, "Main experimental findings", fontsize=12, weight="bold")

    cards = [
        ((0.05, 0.59), "DEEP-10M", "2.06x over\npost-filter\n26-28x fewer dist.", COLORS["blue_light"], COLORS["blue"]),
        ((0.29, 0.59), "Index budget", "more attrs improve\nrecall but reduce QPS", COLORS["purple_light"], COLORS["purple"]),
        ((0.53, 0.59), "Hybrid", "tiny valid sets\nneed prefiltering", COLORS["orange_light"], COLORS["orange"]),
        ((0.77, 0.59), "Dynamic", "updates keep recall\nrebuild restores QPS", COLORS["red_light"], COLORS["red"]),
        ((0.29, 0.20), "BigVectorBench", "real 3-attribute\nfiltered ANN case", COLORS["green_light"], COLORS["green"]),
        ((0.53, 0.20), "Boundary", "not a universal\npost-filter replacement", COLORS["gray_light"], COLORS["gray"]),
    ]
    for (x, y), title, body, fc, ec in cards:
        box(ax, (x, y), (0.18, 0.18), f"{title}\n{body}", fc, ec, fontsize=7.7)

    arrow(ax, (0.23, 0.68), (0.29, 0.68), COLORS["gray"])
    arrow(ax, (0.47, 0.68), (0.53, 0.68), COLORS["gray"])
    arrow(ax, (0.71, 0.68), (0.77, 0.68), COLORS["gray"])
    arrow(ax, (0.86, 0.59), (0.62, 0.38), COLORS["gray"], rad=-0.20)
    arrow(ax, (0.38, 0.59), (0.38, 0.38), COLORS["gray"])

    save(fig, "fig_main_findings")


def fig_contribution_map():
    fig, ax = setup_ax((7.4, 3.8))
    ax.text(0.02, 0.95, "Contribution map", fontsize=12, weight="bold")

    box(ax, (0.34, 0.39), (0.28, 0.17), "Multi-attribute\nrange-filtered\nANN system", COLORS["gray_light"], COLORS["gray"])
    items = [
        ((0.05, 0.68), "C1: DANA\none DSG per\nindexed attribute", COLORS["blue_light"], COLORS["blue"]),
        ((0.38, 0.70), "C2: In-search\nconjunctive\nfiltering", COLORS["green_light"], COLORS["green"]),
        ((0.70, 0.68), "C3: Dynamic\nBase/Delta/\nTombstone", COLORS["red_light"], COLORS["red"]),
        ((0.12, 0.12), "C4: Hybrid +\nindex-budget\nanalysis", COLORS["orange_light"], COLORS["orange"]),
        ((0.62, 0.12), "C5: Large-scale\n+ public data\nevaluation", COLORS["purple_light"], COLORS["purple"]),
    ]
    for (x, y), text, fc, ec in items:
        box(ax, (x, y), (0.22, 0.14), text, fc, ec, fontsize=8)
        arrow(ax, (x + 0.11, y + 0.07), (0.48, 0.48), ec, lw=1.0)

    ax.text(0.31, 0.30, "Pragmatic extension, not a lossless\nmulti-dimensional DSG theory.", fontsize=8.5, color=COLORS["gray"])
    save(fig, "fig_contribution_map")


def fig_applicability_boundary():
    fig, ax = setup_ax((7.4, 4.2))
    ax.text(0.02, 0.95, "Applicability boundary", fontsize=12, weight="bold")

    box(ax, (0.05, 0.72), (0.22, 0.12), "Multi-attribute\nrange query", COLORS["gray_light"], COLORS["gray"])
    box(ax, (0.37, 0.72), (0.22, 0.12), "Very few\nvalid objects?", COLORS["orange_light"], COLORS["orange"])
    box(ax, (0.69, 0.72), (0.22, 0.12), "Prefiltering\nfor recall", COLORS["orange_light"], COLORS["orange"])

    box(ax, (0.37, 0.49), (0.22, 0.12), "Strong attribute-vector\ncorrelation?", COLORS["blue_light"], COLORS["blue"], fontsize=8)
    box(ax, (0.69, 0.49), (0.22, 0.12), "HNSW post-filter\nmay be competitive", COLORS["blue_light"], COLORS["blue"], fontsize=8)

    box(ax, (0.37, 0.27), (0.22, 0.12), "Storage budget\nfor attributes?", COLORS["purple_light"], COLORS["purple"])
    box(ax, (0.69, 0.27), (0.22, 0.12), "Index high-value\nattributes only", COLORS["purple_light"], COLORS["purple"], fontsize=8)

    box(ax, (0.37, 0.07), (0.22, 0.12), "Weak correlation\nand enough budget", COLORS["green_light"], COLORS["green"], fontsize=8)
    box(ax, (0.69, 0.07), (0.22, 0.12), "DANA\nbest fit", COLORS["green_light"], COLORS["green"])

    arrow(ax, (0.27, 0.78), (0.37, 0.78), COLORS["gray"])
    arrow(ax, (0.59, 0.78), (0.69, 0.78), COLORS["orange"])
    ax.text(0.61, 0.81, "yes", fontsize=8, color=COLORS["orange"])
    arrow(ax, (0.48, 0.72), (0.48, 0.61), COLORS["blue"])
    ax.text(0.50, 0.66, "no", fontsize=8, color=COLORS["blue"])
    arrow(ax, (0.59, 0.55), (0.69, 0.55), COLORS["blue"])
    ax.text(0.61, 0.58, "yes", fontsize=8, color=COLORS["blue"])
    arrow(ax, (0.48, 0.49), (0.48, 0.39), COLORS["purple"])
    ax.text(0.50, 0.43, "no/weak", fontsize=8, color=COLORS["purple"])
    arrow(ax, (0.59, 0.33), (0.69, 0.33), COLORS["purple"])
    ax.text(0.61, 0.36, "limited", fontsize=8, color=COLORS["purple"])
    arrow(ax, (0.48, 0.27), (0.48, 0.19), COLORS["green"])
    ax.text(0.50, 0.22, "sufficient", fontsize=8, color=COLORS["green"])
    arrow(ax, (0.59, 0.13), (0.69, 0.13), COLORS["green"])

    save(fig, "fig_applicability_boundary")


def _panel(ax, label, x=0.01, y=0.98):
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="top",
            fontsize=8.2, weight="bold", color=COLORS["dark"])


def fig_intro_dynamic_framework_v2():
    """Figure 1: one visual thesis spanning search and update paths."""
    fig, ax = setup_ax((7.0, 2.85))
    ax.text(0.02, 0.94, "Dynamic multi-attribute range-filtered ANN",
            fontsize=8.2, weight="bold", color=COLORS["dark"])
    ax.plot([0.02, 0.98], [0.51, 0.51], color="#D7DCE1", lw=0.9)

    ax.text(0.02, 0.76, "SEARCH", fontsize=7.8, weight="bold", color=COLORS["blue"])
    search_y = 0.69
    box(ax, (0.11, search_y), (0.09, 0.11), "Query", "white",
        COLORS["blue"], fontsize=8.0)
    box(ax, (0.24, search_y), (0.11, 0.11), "Router",
        COLORS["blue_light"], COLORS["blue"], fontsize=8.0)
    box(ax, (0.40, search_y), (0.13, 0.11), "selected DSG\nattribute j*",
        COLORS["blue_light"], COLORS["blue"], fontsize=7.7)
    box(ax, (0.58, search_y), (0.15, 0.11), "bridge nodes\ntraversable",
        "white", COLORS["blue"], fontsize=7.6)
    box(ax, (0.79, search_y), (0.16, 0.11), "full predicate\nTop-$k$",
        COLORS["green_light"], COLORS["green"], fontsize=7.7)
    for x0, x1, color in ((0.20, 0.24, COLORS["blue"]),
                          (0.35, 0.40, COLORS["blue"]),
                          (0.53, 0.58, COLORS["blue"]),
                          (0.73, 0.79, COLORS["green"])):
        arrow(ax, (x0, 0.745), (x1, 0.745), color, mutation=9)
    ax.text(0.465, 0.84, "NAVIGATION", ha="center", fontsize=7.2,
            weight="bold", color=COLORS["blue"])
    ax.text(0.87, 0.84, "ADMISSION", ha="center", fontsize=7.2,
            weight="bold", color=COLORS["green"])

    ax.text(0.02, 0.34, "UPDATE", fontsize=7.8, weight="bold", color=COLORS["orange"])
    box(ax, (0.11, 0.23), (0.13, 0.11), "insert / update\n/ delete",
        "white", COLORS["orange"], fontsize=7.6)
    box(ax, (0.30, 0.23), (0.15, 0.11), "Delta +\nTombstone",
        COLORS["orange_light"], COLORS["orange"], fontsize=7.6)
    box(ax, (0.53, 0.23), (0.14, 0.11), "snapshot\nrebuild",
        COLORS["orange_light"], COLORS["orange"], fontsize=7.6)
    box(ax, (0.75, 0.23), (0.18, 0.11), "new ordered\nBase DSGs",
        COLORS["blue_light"], COLORS["blue"], fontsize=7.6)
    arrow(ax, (0.24, 0.285), (0.30, 0.285), COLORS["orange"], mutation=9)
    arrow(ax, (0.45, 0.285), (0.53, 0.285), COLORS["orange"], mutation=9)
    arrow(ax, (0.67, 0.285), (0.75, 0.285), COLORS["blue"], mutation=9)
    ax.text(0.49, 0.11, "updates stay visible while attribute-order semantics are restored",
            ha="center", fontsize=7.5, color=COLORS["gray"])
    save(fig, "fig_intro_dynamic_framework")


def fig_search_mechanism_v2():
    """Figure 2: running example of DANA query and update processing."""
    fig, ax = setup_ax((7.0, 3.05))
    ax.plot([0.335, 0.335], [0.08, 0.91], color="#D7DCE1", lw=0.9)
    ax.plot([0.705, 0.705], [0.08, 0.91], color="#D7DCE1", lw=0.9)

    # Panel a: the same objects induce different one-dimensional orderings.
    ax.text(0.025, 0.94, "a", fontsize=8.6, weight="bold")
    ax.text(0.060, 0.94, "Attribute-specific orders", fontsize=8.5,
            weight="bold", color=COLORS["dark"])
    box(ax, (0.055, 0.77), (0.245, 0.095),
        "$q$: $a_1\\in[3,6]$, $a_2\\in[4,7]$, $k=2$",
        "white", COLORS["gray"], fontsize=7.8, lw=1.0)

    def order_row(y, label, ids, values, interval):
        xs = np.linspace(0.09, 0.295, len(ids))
        left, right = interval
        ax.plot([xs[left] - 0.023, xs[right] + 0.023], [y, y],
                color=COLORS["blue_light"], lw=18, solid_capstyle="round",
                zorder=0)
        ax.text(0.045, y + 0.008, label, ha="left", va="center",
                fontsize=7.8, weight="bold", color=COLORS["blue"])
        for x, obj, value in zip(xs, ids, values):
            ax.add_patch(Circle((x, y), 0.017, facecolor="white",
                                edgecolor=COLORS["blue_mid"], linewidth=1.1,
                                zorder=2))
            ax.text(x, y, obj, ha="center", va="center", fontsize=6.8,
                    color=COLORS["dark"], zorder=3)
            ax.text(x, y - 0.055, str(value), ha="center", va="center",
                    fontsize=6.7, color=COLORS["gray"])
        ax.plot([xs[0] - 0.025, xs[-1] + 0.025], [y, y],
                color="#8A949D", lw=0.8, zorder=1)

    order_row(0.62, "$a_1$", ["v1", "v2", "v3", "v4", "v5", "v6"],
              [1, 3, 4, 5, 6, 8], (1, 4))
    order_row(0.40, "$a_2$", ["v2", "v4", "v5", "v3", "v1", "v6"],
              [2, 3, 5, 6, 7, 9], (2, 4))
    ax.text(0.175, 0.23, "$w_2=3 < w_1=4$", ha="center", fontsize=7.7,
            color=COLORS["blue"], weight="bold")
    box(ax, (0.105, 0.105), (0.145, 0.075), "route on DSG($a_2$)",
        COLORS["blue_light"], COLORS["blue"], fontsize=7.5, lw=1.0)

    # Panel b: a non-answer remains traversable; admission enforces conjunction.
    ax.text(0.355, 0.94, "b", fontsize=8.6, weight="bold")
    ax.text(0.390, 0.94, "Navigate, then admit", fontsize=8.5,
            weight="bold", color=COLORS["dark"])
    graph_nodes = {
        "v5": (0.405, 0.63),
        "v1": (0.505, 0.69),
        "v3": (0.615, 0.61),
        "v4": (0.455, 0.47),
        "v6": (0.625, 0.45),
    }
    graph_edges = [("v5", "v1"), ("v1", "v3"), ("v5", "v4"),
                   ("v4", "v3"), ("v3", "v6")]
    for u, v in graph_edges:
        x0, y0 = graph_nodes[u]
        x1, y1 = graph_nodes[v]
        ax.plot([x0, x1], [y0, y1], color="#84909A", lw=1.25, zorder=1)
    for obj, (x, y) in graph_nodes.items():
        if obj in ("v5", "v3"):
            fc, ec = COLORS["green_light"], COLORS["green"]
        elif obj == "v1":
            fc, ec = COLORS["red_light"], COLORS["red"]
        else:
            fc, ec = COLORS["gray_light"], COLORS["gray"]
        ax.add_patch(Circle((x, y), 0.025, facecolor=fc, edgecolor=ec,
                            linewidth=1.25, zorder=3))
        ax.text(x, y, obj, ha="center", va="center", fontsize=7.1,
                color=COLORS["dark"], zorder=4)
    arrow(ax, (0.425, 0.645), (0.480, 0.678), COLORS["blue"], mutation=9)
    arrow(ax, (0.530, 0.675), (0.590, 0.628), COLORS["blue"], mutation=9)
    ax.text(0.505, 0.785, "$v_1$: bridge only", ha="center", fontsize=7.3,
            color=COLORS["red"])
    ax.plot([0.380, 0.680], [0.335, 0.335], color="#D7DCE1", lw=0.9)
    box(ax, (0.380, 0.165), (0.155, 0.085), "full predicate",
        COLORS["green_light"], COLORS["green"], fontsize=7.6, lw=1.0)
    box(ax, (0.570, 0.165), (0.095, 0.085), "$v_5, v_3$",
        "white", COLORS["green"], fontsize=7.6, lw=1.0)
    arrow(ax, (0.535, 0.207), (0.570, 0.207), COLORS["green"], mutation=8)
    ax.text(0.522, 0.105, "navigation $\\ne$ result admission", ha="center",
            fontsize=7.5, color=COLORS["blue"], weight="bold")

    # Panel c: updates remain visible without mutating the immutable Base order.
    ax.text(0.725, 0.94, "c", fontsize=8.6, weight="bold")
    ax.text(0.760, 0.94, "Update and rebuild", fontsize=8.5,
            weight="bold", color=COLORS["dark"])
    box(ax, (0.745, 0.76), (0.215, 0.075), "$v_3$: $a_2$ 6 $\\rightarrow$ 1",
        COLORS["orange_light"], COLORS["orange"], fontsize=7.6, lw=1.0)
    ax.text(0.735, 0.655, "$B_0$", fontsize=7.8, weight="bold",
            color=COLORS["blue"])
    box(ax, (0.775, 0.615), (0.185, 0.075), "v2  v4  v5  v3  v1  v6",
        COLORS["blue_light"], COLORS["blue"], fontsize=7.0, lw=1.0)
    ax.text(0.735, 0.515, "$D/T$", fontsize=7.8, weight="bold",
            color=COLORS["orange"])
    box(ax, (0.775, 0.475), (0.185, 0.075), "new v3  /  tomb(v3)",
        COLORS["orange_light"], COLORS["orange"], fontsize=7.1, lw=1.0)
    arrow(ax, (0.865, 0.455), (0.865, 0.365), COLORS["orange"], mutation=9)
    ax.text(0.887, 0.410, "rebuild", fontsize=7.1, color=COLORS["orange"],
            va="center")
    ax.text(0.735, 0.285, "$B_1$", fontsize=7.8, weight="bold",
            color=COLORS["green"])
    box(ax, (0.775, 0.245), (0.185, 0.075), "v3  v2  v4  v5  v1  v6",
        COLORS["green_light"], COLORS["green"], fontsize=7.0, lw=1.0)
    ax.text(0.865, 0.135, "new attribute order", ha="center", fontsize=7.4,
            color=COLORS["green"], weight="bold")

    # Shared symbol key; shapes and outlines keep the meaning in grayscale.
    key = ((0.365, COLORS["green_light"], COLORS["green"], "feasible"),
           (0.470, COLORS["red_light"], COLORS["red"], "bridge"),
           (0.565, COLORS["gray_light"], COLORS["gray"], "other"))
    for x, fc, ec, label in key:
        ax.add_patch(Circle((x, 0.055), 0.009, facecolor=fc, edgecolor=ec,
                            linewidth=0.9))
        ax.text(x + 0.015, 0.055, label, va="center", fontsize=6.7,
                color=COLORS["dark"])
    save(fig, "fig1_extension_overview")


def fig_deep10m_evidence_v2():
    """Figure 4: matched-recall graph-work benefit and storage cost."""
    methods = ["HNSW\npost", "HNSW\nin-search", "DANA"]
    dist = np.array([351958.6, 334501.3, 12689.9])
    storage = np.array([5.0, 5.0, 106.6])
    colors = ["#B9BEC4", "#747B83", COLORS["blue"]]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.45), gridspec_kw={"wspace": 0.40})
    x = np.arange(3)
    bars1 = ax1.bar(x, dist, color=colors, edgecolor="#252525", lw=0.7, width=0.65)
    for bar, hatch in zip(bars1, ("//", "..", "")):
        bar.set_hatch(hatch)
    ax1.set_yscale("log")
    ax1.set_ylabel("Distance evaluations/query")
    ax1.set_xticks(x, methods)
    ax1.set_ylim(8e3, 8e5)
    _panel(ax1, "a  Matched-recall graph work")
    for bar, value, label in zip(bars1, dist, ("352K", "335K", "12.7K")):
        ax1.text(bar.get_x() + bar.get_width() / 2, value * 1.05, label,
                 ha="center", va="bottom", fontsize=7.0, color=COLORS["dark"])
    ax1.text(0.98, 0.53, "$27.7\\times$ fewer vs post-filter",
             transform=ax1.transAxes, ha="right", fontsize=7.4,
             color=COLORS["blue"])
    bars2 = ax2.bar(x, storage, color=colors, edgecolor="#252525", lw=0.7, width=0.65)
    for bar, hatch in zip(bars2, ("//", "..", "")):
        bar.set_hatch(hatch)
    ax2.set_yscale("log")
    ax2.set_ylabel("Index storage (GB)")
    ax2.set_xticks(x, methods)
    ax2.set_ylim(3, 230)
    _panel(ax2, "b  Deployment cost")
    for bar, value, label in zip(bars2, storage, ("5.0", "5.0", "106.6")):
        ax2.text(bar.get_x() + bar.get_width() / 2, value * 1.06, label,
                 ha="center", va="bottom", fontsize=7.0, color=COLORS["dark"])
    ax2.text(0.50, 0.53, "$21.3\\times$ larger",
             transform=ax2.transAxes, ha="center", fontsize=7.4,
             color=COLORS["blue"])
    for ax in (ax1, ax2):
        ax.grid(False)
        ax.tick_params(labelsize=7.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.23, top=0.95)
    save(fig, "fig_deep10m_work_comparison")


def fig_app_routing_v2():
    """Figure 5: same-scope App-Reviews routing policies."""
    labels = ["Text length", "Timestamp", "Star rating", "Span", "Oracle"]
    recall = np.array([0.4614, 0.9802, 0.8811, 0.9508, 0.9944])
    selected = np.array([
        [10000, 0, 0], [0, 10000, 0], [0, 0, 10000],
        [793, 9207, 0], [447, 9128, 425],
    ], dtype=float) / 10000.0
    y = np.arange(len(labels))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.75), gridspec_kw={"wspace": 0.42})
    point_colors = ["#A9AFB5", "#747B83", "#A9AFB5", COLORS["orange"], COLORS["blue"]]
    ax1.hlines(y, 0, recall, color="#D1D5D9", lw=1.2)
    ax1.scatter(recall, y, s=34, c=point_colors, edgecolor="#202020", lw=0.6, zorder=3)
    for yi, value in zip(y, recall):
        ax1.text(1.035, yi, f"{value:.4f}", va="center", ha="left",
                 fontsize=7.4, color=COLORS["dark"])
    ax1.set_yticks(y, labels)
    ax1.set_xlim(0.40, 1.13)
    ax1.set_ylim(4.45, -0.55)
    ax1.set_xlabel("Recall")
    ax1.set_title("a  Routing quality", loc="left", fontsize=8.2, weight="bold", pad=7)
    route_colors = ["#B8C8D8", COLORS["blue"], "#D5D8DC"]
    route_labels = ["Text length", "Timestamp", "Star rating"]
    left = np.zeros(len(labels))
    for j in range(3):
        ax2.barh(y, selected[:, j], left=left, color=route_colors[j],
                 edgecolor="white", lw=0.6, label=route_labels[j], height=0.62)
        left += selected[:, j]
    ax2.set_yticks(y, labels)
    ax2.set_xlim(0, 1)
    ax2.set_xlabel("Queries routed to attribute")
    ax2.set_xticks([0, 0.5, 1], ["0", "50%", "100%"])
    ax2.set_ylim(4.45, -0.55)
    ax2.set_title("b  Attribute selection", loc="left", fontsize=8.2,
                  weight="bold", pad=7, y=0.97)
    ax2.legend(loc="lower center", bbox_to_anchor=(0.5, 1.13), ncol=3,
               fontsize=7.0, frameon=False, handlelength=1.0, columnspacing=0.8)
    for ax in (ax1, ax2):
        ax.grid(False)
        ax.tick_params(labelsize=7.2)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.subplots_adjust(left=0.12, right=0.99, bottom=0.20, top=0.80)
    save(fig, "fig_app_routing")


def fig_dynamic_evidence_v2():
    """Figure 7: growth cost, phase attribution, and rebuild recovery."""
    delta = np.array([0, 10, 20, 40, 50, 100, 200])
    latency = np.array([10.1345, 10.4959, 10.8661, 10.3740, 11.9353, 22.1365, 27.3521])
    phases = np.array([[8.2247, 0.0002, 0.0030], [8.1576, 5.5674, 0.0569], [12.1005, 7.1490, 0.1236]])
    dstate = ["0", "50K", "100K"]
    recovery = [77.7, 417.8]
    fig = plt.figure(figsize=(7.0, 2.75))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.28, 1.05, 0.78], wspace=0.48)
    ax1, ax2, ax3 = [fig.add_subplot(gs[0, i]) for i in range(3)]
    ax1.plot(delta, latency, color=COLORS["orange"], marker="o", ms=4.2,
             mec="#202020", mew=0.6, lw=1.6)
    ax1.set_xlabel("Retained Delta entries (K)")
    ax1.set_ylabel("Query latency (ms)")
    ax1.set_xlim(-5, 210)
    ax1.set_title("a  Delta growth", loc="left", fontsize=8.2, weight="bold", pad=7)
    bottom = np.zeros(3)
    phase_colors = ["#AEB6BF", COLORS["orange"], COLORS["blue"]]
    phase_labels = ["Base", "Delta scan", "Merge"]
    for j in range(3):
        ax2.bar(dstate, phases[:, j], bottom=bottom, color=phase_colors[j],
                edgecolor="#252525", lw=0.45, width=0.62, label=phase_labels[j])
        bottom += phases[:, j]
    for i, total in enumerate(phases.sum(axis=1)):
        ax2.text(i, total + 0.35, f"{total:.2f}", ha="center", va="bottom",
                 fontsize=6.9, color=COLORS["dark"])
    ax2.set_xlabel("Live Delta")
    ax2.set_ylabel("Latency breakdown (ms)")
    ax2.set_title("b  Query-cost source", loc="left", fontsize=8.2, weight="bold", pad=7)
    ax2.legend(loc="upper left", bbox_to_anchor=(0.0, 0.91), fontsize=6.6,
               frameon=False, handlelength=1.0)
    bars = ax3.bar([0, 1], recovery, color=[COLORS["orange"], COLORS["blue"]],
                   edgecolor="#252525", lw=0.7, width=0.62)
    ax3.set_xticks([0, 1], ["Before", "After"])
    ax3.set_ylabel("QPS")
    ax3.set_ylim(0, 490)
    ax3.set_title("c  Rebuild recovery", loc="left", fontsize=8.2, weight="bold", pad=7)
    for bar, value in zip(bars, recovery):
        ax3.text(bar.get_x() + bar.get_width()/2, value + 10,
                 f"{value:.1f}", ha="center", va="bottom",
                 fontsize=7.2, color=COLORS["dark"])
    for ax in (ax1, ax2, ax3):
        ax.grid(False)
        ax.tick_params(labelsize=7.2)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.22, top=0.95)
    save(fig, "fig_dynamic_growth")


def main():
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "font.size": 8,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    # Submission figure suite: visual thesis, mechanism, lifecycle, and the
    # three principal evidence chains. Every plotted value is defined in the
    # corresponding function rather than inferred from rendered artwork.
    fig_intro_dynamic_framework_v2()
    fig_search_mechanism_v2()
    fig_snapshot_maintenance()
    fig_deep10m_evidence_v2()
    fig_app_routing_v2()
    fig_attribute_scalability()
    fig_dynamic_evidence_v2()
    print(f"Wrote figures to {OUT}")


if __name__ == "__main__":
    main()
