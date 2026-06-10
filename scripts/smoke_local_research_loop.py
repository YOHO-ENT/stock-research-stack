#!/usr/bin/env python3
"""Read-only smoke check for the local research loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_hub.app import build_control_status_payload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check local research loop status without starting services.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON payload.")
    parser.add_argument("--timeout", type=float, default=1.5, help="Per-service timeout in seconds.")
    args = parser.parse_args()

    if args.timeout <= 0:
        print("ERROR: --timeout must be positive", file=sys.stderr)
        return 1

    try:
        payload = build_control_status_payload(args.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status={payload['status']}")
        print(f"checked_at={payload['checked_at']}")
        for signal in payload.get("signals", []):
            status = signal.get("status", "unknown")
            label = signal.get("label", signal.get("id", "signal"))
            message = signal.get("message") or "-"
            target = signal.get("target") or "-"
            print(f"{status} {label}: {message} ({target})")

    return 0 if payload.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
