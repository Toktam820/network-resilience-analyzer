"""Command-line interface for the network resilience analyzer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .analyzer import AnalysisThresholds, analyze_file
from .visualizer import create_delay_chart, create_loss_chart


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze packet delay, jitter, packet loss, throughput, and "
            "traffic-class resilience from a CSV file."
        )
    )
    parser.add_argument("csv_file", help="Path to the network experiment CSV file")
    parser.add_argument("--output", default="output", help="Directory for reports and charts")
    parser.add_argument("--max-mean-delay", type=float, default=15.0)
    parser.add_argument("--max-p95-delay", type=float, default=30.0)
    parser.add_argument("--max-jitter", type=float, default=6.0)
    parser.add_argument("--max-loss", type=float, default=2.0)
    parser.add_argument("--min-throughput", type=float, default=0.25)
    return parser


def _print_summary(report: dict) -> None:
    metrics = report["overall"]
    print("Network Resilience Summary")
    print("=" * 28)
    print(f"Status:              {metrics['status']}")
    print(f"Packets:             {metrics['delivered_packets']}/{metrics['total_packets']} delivered")
    print(f"Packet loss:         {metrics['packet_loss_percent']:.3f}%")
    print(f"Mean delay:          {metrics['mean_delay_ms']:.3f} ms")
    print(f"95th percentile:     {metrics['p95_delay_ms']:.3f} ms")
    print(f"Jitter:              {metrics['jitter_ms']:.3f} ms")
    print(f"Throughput:          {metrics['throughput_mbps']:.3f} Mbps")
    print(f"Threshold violations: {', '.join(metrics['violations']) or 'none'}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    thresholds = AnalysisThresholds(
        max_mean_delay_ms=args.max_mean_delay,
        max_p95_delay_ms=args.max_p95_delay,
        max_jitter_ms=args.max_jitter,
        max_packet_loss_percent=args.max_loss,
        min_throughput_mbps=args.min_throughput,
    )

    frame, report = analyze_file(args.csv_file, thresholds)

    report_path = output_dir / "resilience_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    create_delay_chart(frame, output_dir / "delay_over_time.png")
    create_loss_chart(report, output_dir / "packet_loss_by_class.png")

    _print_summary(report)
    print()
    print(f"Report written to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
