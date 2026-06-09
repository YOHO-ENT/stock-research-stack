"""Command-line entry point for Research Hub."""

from __future__ import annotations

import argparse
import os

from research_hub.app import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TIMEOUT_SECONDS, run


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Research Hub.")
    parser.add_argument("--host", default=os.getenv("RESEARCH_HUB_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=_int_env("RESEARCH_HUB_PORT", DEFAULT_PORT))
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=_float_env("RESEARCH_HUB_HEALTH_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        help="Per-service health-check timeout in seconds.",
    )
    args = parser.parse_args()
    run(host=args.host, port=args.port, health_timeout_seconds=args.health_timeout)


if __name__ == "__main__":
    main()

