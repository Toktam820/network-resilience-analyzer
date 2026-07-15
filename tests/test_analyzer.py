from __future__ import annotations

import pandas as pd
import pytest

from network_resilience_analyzer.analyzer import (
    AnalysisThresholds,
    analyze_dataframe,
    load_network_data,
)


def test_calculates_expected_metrics() -> None:
    frame = pd.DataFrame(
        {
            "packet_id": [1, 2, 3, 4],
            "sent_time_ms": [0.0, 100.0, 200.0, 300.0],
            "received_time_ms": [10.0, 112.0, None, 314.0],
            "packet_size_bytes": [1000, 1000, 1000, 1000],
            "delivered": [1, 1, 0, 1],
            "traffic_class": ["control", "control", "control", "control"],
        }
    )
    frame["delay_ms"] = frame["received_time_ms"] - frame["sent_time_ms"]

    report = analyze_dataframe(
        frame,
        AnalysisThresholds(
            max_mean_delay_ms=20,
            max_p95_delay_ms=20,
            max_jitter_ms=10,
            max_packet_loss_percent=30,
            min_throughput_mbps=0.01,
        ),
    )

    overall = report["overall"]
    assert overall["total_packets"] == 4
    assert overall["delivered_packets"] == 3
    assert overall["packet_loss_percent"] == 25.0
    assert overall["mean_delay_ms"] == 12.0
    assert overall["jitter_ms"] == 2.0
    assert overall["status"] == "HEALTHY"


def test_marks_threshold_violation_as_degraded() -> None:
    frame = pd.DataFrame(
        {
            "packet_id": [1, 2],
            "sent_time_ms": [0.0, 100.0],
            "received_time_ms": [50.0, None],
            "packet_size_bytes": [1000, 1000],
            "delivered": [1, 0],
            "traffic_class": ["best_effort", "best_effort"],
        }
    )
    frame["delay_ms"] = frame["received_time_ms"] - frame["sent_time_ms"]

    report = analyze_dataframe(frame)

    assert report["overall"]["status"] == "DEGRADED"
    assert "packet_loss" in report["overall"]["violations"]


def test_load_rejects_missing_columns(tmp_path) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("packet_id,sent_time_ms\n1,0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required columns"):
        load_network_data(csv_path)


def test_per_class_throughput_does_not_create_false_violation() -> None:
    frame = pd.DataFrame(
        {
            "packet_id": [1, 2],
            "sent_time_ms": [0.0, 1000.0],
            "received_time_ms": [5.0, 1005.0],
            "packet_size_bytes": [64, 64],
            "delivered": [1, 1],
            "traffic_class": ["control", "control"],
        }
    )
    frame["delay_ms"] = frame["received_time_ms"] - frame["sent_time_ms"]

    report = analyze_dataframe(frame)

    assert report["by_traffic_class"]["control"]["status"] == "HEALTHY"
    assert "throughput" not in report["by_traffic_class"]["control"]["violations"]
    assert "throughput" in report["overall"]["violations"]
