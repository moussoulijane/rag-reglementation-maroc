"""Tracer les métriques exportées, sans réexécuter recherche ni génération."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def row(folder, mode, direction):
    report = json.loads((ROOT / "reports" / folder / f"{mode}.json").read_text(encoding="utf-8"))
    return next(item for item in report["aggregate"] if item["direction"] == direction)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True)
    colors = ["#B5BEC8", "#137D75"]
    methods = ["bm25", "semantic", "hybrid"]
    x = np.arange(3)
    for offset, folder, label, color in [
        (-0.18, "reference", "Initial pilot", colors[0]),
        (0.18, "diagnostic-normalization", "Normalization diagnostic", colors[1]),
    ]:
        values = [row(folder, mode, "overall")["recall_at_5"] for mode in methods]
        bars = axes[0].bar(x + offset, values, 0.34, label=label, color=color)
        axes[0].bar_label(bars, labels=[f"{v:.0%}" for v in values], padding=4, fontsize=8)
    axes[0].set_xticks(x, ["BM25", "Semantic", "Hybrid"])
    axes[0].set_title("All directions · article Recall@5", loc="left", fontsize=12)
    directions = ["fr->fr", "ar->ar", "fr->ar", "ar->fr"]
    x = np.arange(4)
    for offset, folder, color in [
        (-0.18, "reference", colors[0]),
        (0.18, "diagnostic-normalization", colors[1]),
    ]:
        values = [row(folder, "hybrid", d)["recall_at_5"] for d in directions]
        bars = axes[1].bar(x + offset, values, 0.34, color=color)
        axes[1].bar_label(bars, labels=[f"{v:.0%}" for v in values], padding=4, fontsize=8)
    axes[1].set_xticks(x, ["FR → FR", "AR → AR", "FR → AR", "AR → FR"])
    axes[1].set_title("Hybrid by question → source language", loc="left", fontsize=12)
    for axis in axes:
        axis.set_ylim(0, 1.13)
        axis.set_yticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#E5E9EE", linewidth=0.8)
    axes[0].set_ylabel("Relevant article found among 5 results")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.12), ncol=2, frameon=False
    )
    fig.suptitle(
        "Arabic PDF normalization: an exploratory pipeline diagnostic",
        x=0.08,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.03,
        "Same 5 positive topics per direction; the test was inspected before the fix.\n"
        "The fix changes tokenization and chunking. Article recall does not measure answer faithfulness.",
        fontsize=9,
        color="#46515F",
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.80, bottom=0.29, wspace=0.18)
    target = ROOT / "reports/figures"
    target.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(target / f"normalization_diagnostic.{suffix}", dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
