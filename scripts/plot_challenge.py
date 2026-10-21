"""Plot all directions of the first frozen new-topic run; never rerun retrieval."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    modes = ("bm25", "semantic", "hybrid")
    directions = ("fr->fr", "ar->ar", "fr->ar", "ar->fr")
    reports = {
        mode: json.loads((ROOT / f"reports/challenge-v2/{mode}.json").read_text(encoding="utf-8"))
        for mode in modes
    }
    metrics = [
        ("recall_at_5", "Article attendu retrouvé · Recall@5", "12 thèmes positifs par direction"),
        (
            "positive_answer_rate",
            "Questions positives acceptées",
            "12 thèmes positifs par direction",
        ),
        (
            "negative_abstention_rate",
            "Questions hors corpus refusées",
            "8 thèmes négatifs par direction",
        ),
    ]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig, axes = plt.subplots(1, 3, figsize=(14.3, 4.7))
    for axis, (metric, title, denominator) in zip(axes, metrics, strict=True):
        matrix = np.array(
            [
                [
                    next(
                        row for row in reports[mode]["aggregate"] if row["direction"] == direction
                    )[metric]
                    for mode in modes
                ]
                for direction in directions
            ]
        )
        picture = axis.imshow(matrix, vmin=0, vmax=1, cmap="Blues", aspect="auto")
        axis.set_xticks(range(3), ["BM25", "Sémantique", "Hybride"])
        axis.set_yticks(range(4), [value.replace("->", " → ").upper() for value in directions])
        axis.set_title(title + "\n" + denominator, fontsize=11, pad=12)
        axis.tick_params(length=0, pad=8)
        for spine in axis.spines.values():
            spine.set_visible(False)
        for row in range(4):
            for column in range(3):
                value = matrix[row, column]
                axis.text(
                    column,
                    row,
                    f"{value:.0%}",
                    ha="center",
                    va="center",
                    color="white" if value > 0.55 else "#123047",
                    fontsize=13,
                )
    fig.suptitle(
        "Nouveaux thèmes internes · politique transférée sans recalibration",
        x=0.05,
        ha="left",
        fontsize=16,
        fontweight="bold",
        y=0.98,
    )
    fig.text(
        0.05,
        0.86,
        "Loi 103-12, édition BAM du 31 mars 2022 · modèle et index figés",
        fontsize=11,
        color="#475569",
    )
    fig.subplots_adjust(left=0.07, right=0.91, bottom=0.22, top=0.71, wspace=0.5)
    color_axis = fig.add_axes((0.94, 0.24, 0.013, 0.47))
    bar = fig.colorbar(picture, cax=color_axis)
    bar.set_ticks([0, 0.5, 1], labels=["0 %", "50 %", "100 %"])
    bar.outline.set_visible(False)
    fig.text(
        0.05,
        0.07,
        "20 thèmes / 80 couples question-langue source. Les quatre directions d'un thème sont liées.\n"
        "Annotation et audit internes ; aucune mesure de fidélité d'une réponse générée.",
        fontsize=10,
        color="#475569",
    )
    folder = ROOT / "reports/figures"
    folder.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "svg"):
        fig.savefig(folder / f"challenge_v2.{extension}", dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
