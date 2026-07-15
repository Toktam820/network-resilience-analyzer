"""Core metrics for network resilience experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "packet_id",
    "sent_time_ms",
    "received_time_ms",
    "packet_size_bytes",
    "delivered",
    "traffic_class",
}


@dataclass(frozen=True)
class AnalysisThresholds:
    """Service targets used to classify an experiment as healthy or degraded."""

    max_mean_delay_ms: float = 15.0
    max_p95_delay_ms: float = 30.0
    max_jitter_ms: float = 6.0
    max_packet_loss_percent: float = 2.0
    min_throughput_mbps: float = 0.25


def load_network_data(csv_path: str | Path) -> pd.DataFrame:
    """Load and validate one network experiment CSV file."""

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Missing required columns: {missing_text}")

    if frame.empty:
        raise ValueError("The CSV file contains no packet records.")

    frame = frame.copy()
    frame["delivered"] = frame["delivered"].astype(int)
    frame["packet_size_bytes"] = pd.to_numeric(frame["packet_size_bytes"], errors="raise")
    frame["sent_time_ms"] = pd.to_numeric(frame["sent_time_ms"], errors="raise")
    frame["received_time_ms"] = pd.to_numeric(frame["received_time_ms"], errors="coerce")

    invalid_delivery = ~frame["delivered"].isin([0, 1])
    if invalid_delivery.any():
        raise ValueError("Column 'delivered' must contain only 0 or 1.")

    delivered_without_timestamp = (frame["delivered"] == 1) & frame["received_time_ms"].isna()
    if delivered_without_timestamp.any():
        raise ValueError("Delivered packets must have a received_time_ms value.")

    frame["delay_ms"] = frame["received_time_ms"] - frame["sent_time_ms"]
    negative_delay = (frame["delivered"] == 1) & (frame["delay_ms"] < 0)
    if negative_delay.any():
        raise ValueError("Received time cannot be earlier than sent time.")

    return frame.sort_values(["sent_time_ms", "packet_id"]).reset_index(drop=True)


def _round(value: float | int, digits: int = 3) -> float:
    return round(float(value), digits)


def _metric_block(
    frame: pd.DataFrame,
    thresholds: AnalysisThresholds,
    *,
    check_throughput: bool = True,
) -> dict[str, Any]:
    total_packets = int(len(frame))
    delivered = frame.loc[frame["delivered"] == 1].copy()
    delivered_packets = int(len(delivered))

    packet_loss_percent = 100.0 * (total_packets - delivered_packets) / total_packets

    if delivered_packets:
        delays = delivered["delay_ms"].astype(float)
        mean_delay_ms = delays.mean()
        p95_delay_ms = delays.quantile(0.95)
        max_delay_ms = delays.max()
        jitter_ms = delays.diff().abs().dropna().mean() if delivered_packets > 1 else 0.0
    else:
        mean_delay_ms = p95_delay_ms = max_delay_ms = jitter_ms = 0.0

    duration_ms = float(frame["sent_time_ms"].max() - frame["sent_time_ms"].min())
    duration_seconds = max(duration_ms / 1000.0, 0.001)
    delivered_bits = float(delivered["packet_size_bytes"].sum()) * 8.0
    throughput_mbps = delivered_bits / duration_seconds / 1_000_000.0

    metrics = {
        "total_packets": total_packets,
        "delivered_packets": delivered_packets,
        "packet_loss_percent": _round(packet_loss_percent),
        "mean_delay_ms": _round(mean_delay_ms),
        "p95_delay_ms": _round(p95_delay_ms),
        "max_delay_ms": _round(max_delay_ms),
        "jitter_ms": _round(jitter_ms),
        "throughput_mbps": _round(throughput_mbps),
    }

    violations: list[str] = []
    if metrics["mean_delay_ms"] > thresholds.max_mean_delay_ms:
        violations.append("mean_delay")
    if metrics["p95_delay_ms"] > thresholds.max_p95_delay_ms:
        violations.append("p95_delay")
    if metrics["jitter_ms"] > thresholds.max_jitter_ms:
        violations.append("jitter")
    if metrics["packet_loss_percent"] > thresholds.max_packet_loss_percent:
        violations.append("packet_loss")
    if check_throughput and metrics["throughput_mbps"] < thresholds.min_throughput_mbps:
        violations.append("throughput")

    metrics["status"] = "HEALTHY" if not violations else "DEGRADED"
    metrics["violations"] = violations
    return metrics


def analyze_dataframe(
    frame: pd.DataFrame,
    thresholds: AnalysisThresholds | None = None,
) -> dict[str, Any]:
    """Calculate overall and per-traffic-class network metrics."""

    thresholds = thresholds or AnalysisThresholds()
    if frame.empty:
        raise ValueError("Cannot analyze an empty data frame.")

    if "delay_ms" not in frame.columns:
        frame = frame.copy()
        frame["delay_ms"] = frame["received_time_ms"] - frame["sent_time_ms"]

    by_class = {
        str(name): _metric_block(group, thresholds, check_throughput=False)
        for name, group in frame.groupby("traffic_class", sort=True)
    }

    return {
        "thresholds": asdict(thresholds),
        "overall": _metric_block(frame, thresholds),
        "by_traffic_class": by_class,
    }


def analyze_file(
    csv_path: str | Path,
    thresholds: AnalysisThresholds | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load one CSV file and return both normalized data and calculated metrics."""

    frame = load_network_data(csv_path)
    return frame, analyze_dataframe(frame, thresholds)
