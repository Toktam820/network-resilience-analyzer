"""Charts for network experiment reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


def create_delay_chart(frame: pd.DataFrame, output_path: str | Path) -> Path:
    """Plot one-way delay over experiment time for each traffic class."""

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    delivered = frame.loc[frame["delivered"] == 1].copy()
    start_ms = float(frame["sent_time_ms"].min())
    delivered["experiment_time_s"] = (delivered["sent_time_ms"] - start_ms) / 1000.0

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for traffic_class, group in delivered.groupby("traffic_class", sort=True):
        ax.scatter(
            group["experiment_time_s"],
            group["delay_ms"],
            s=18,
            alpha=0.7,
            label=str(traffic_class),
        )

    ax.set_title("Packet Delay Over Experiment Time")
    ax.set_xlabel("Experiment time (seconds)")
    ax.set_ylabel("One-way delay (ms)")
    ax.grid(True, alpha=0.25)
    ax.legend(title="Traffic class")
    fig.tight_layout()
    fig.savefig(target, dpi=160)
    plt.close(fig)
    return target


def create_loss_chart(report: dict[str, Any], output_path: str | Path) -> Path:
    """Plot packet loss percentage for each traffic class."""

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    class_metrics = report["by_traffic_class"]
    labels = list(class_metrics)
    values = [class_metrics[label]["packet_loss_percent"] for label in labels]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    bars = ax.bar(labels, values)
    ax.axhline(
        report["thresholds"]["max_packet_loss_percent"],
        linestyle="--",
        linewidth=1.5,
        label="Configured threshold",
    )
    ax.set_title("Packet Loss by Traffic Class")
    ax.set_xlabel("Traffic class")
    ax.set_ylabel("Packet loss (%)")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()

    for bar, value in zip(bars, values, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.2f}%",
            ha="center",
            va="bottom",
        )

    fig.tight_layout()
    fig.savefig(target, dpi=160)
    plt.close(fig)
    return target
