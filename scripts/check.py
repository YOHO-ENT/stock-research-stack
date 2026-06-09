#!/usr/bin/env python3
"""Local validation for the research-stack control repo."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_FILES = {
    ".env.example",
    ".gitignore",
    "README.md",
    "pyproject.toml",
    "catalog/services.json",
    "docs/integration-map.md",
    "docs/local-start-plan.md",
    "docs/operating-model.md",
    "docs/ports.md",
    "docs/roadmap.md",
    "docs/service-catalog.md",
    "docs/vultr-deployment-plan.md",
    "research_hub/__init__.py",
    "research_hub/__main__.py",
    "research_hub/app.py",
    "research_hub/static/app.js",
    "research_hub/static/index.html",
    "research_hub/static/styles.css",
    "scripts/check.py",
}

FORBIDDEN_PATTERNS = {
    "/Users/yongnahwa/Desktop/Daily" + "Brief",
    "Daily" + "Brief",
    "<" + "ifr" + "ame",
}


def main() -> int:
    checks = [
        check_expected_files,
        check_catalog,
        check_forbidden_patterns,
        check_imports,
    ]
    failures: list[str] = []
    for check in checks:
        failures.extend(check())
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def check_expected_files() -> list[str]:
    failures = []
    for relative in sorted(EXPECTED_FILES):
        if not (ROOT / relative).is_file():
            failures.append(f"missing expected file: {relative}")
    return failures


def check_catalog() -> list[str]:
    failures = []
    path = ROOT / "catalog/services.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"catalog JSON error: {exc}"]

    services = payload.get("services")
    if not isinstance(services, list) or not services:
        return ["catalog.services must be a non-empty list"]

    ids = []
    for service in services:
        if not isinstance(service, dict):
            failures.append("catalog service must be an object")
            continue
        service_id = service.get("id")
        if not isinstance(service_id, str) or not service_id:
            failures.append("catalog service id is required")
            continue
        ids.append(service_id)
        frame_word = "ifr" + "ame"
        serialized = json.dumps(service).lower()
        if frame_word in serialized and f"not {frame_word}" not in serialized:
            failures.append(f"unexpected embedded-frame wording in service: {service_id}")

    if len(ids) != len(set(ids)):
        failures.append("catalog service ids must be unique")
    if "research-hub" not in ids:
        failures.append("catalog must include research-hub")
    return failures


def check_forbidden_patterns() -> list[str]:
    failures = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.name == "check.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                failures.append(f"forbidden pattern {pattern!r} in {path.relative_to(ROOT)}")
    return failures


def check_imports() -> list[str]:
    try:
        app = importlib.import_module("research_hub.app")
    except Exception as exc:  # noqa: BLE001
        return [f"could not import research_hub.app: {exc}"]
    for name in ("create_server", "list_services", "build_health_payload"):
        if not hasattr(app, name):
            return [f"research_hub.app missing {name}"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
