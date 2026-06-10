#!/usr/bin/env python3
"""Smoke checks for the DailyBrief IP-only Vultr deployment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


DEFAULT_HOST = "149.28.156.116"
DEFAULT_SSH_TARGET = "root@149.28.156.116"
DEFAULT_SSH_KEY = "~/.ssh/research_stack_vultr"
DEFAULT_REPORT_TZ = "Asia/Shanghai"
CORE_ARTIFACTS = ("index", "archive", "html", "json", "articles")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke check DailyBrief on the Vultr host.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Public host or IP.")
    parser.add_argument("--ssh-target", default=DEFAULT_SSH_TARGET, help="SSH target.")
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY, help="SSH private key.")
    parser.add_argument("--report-tz", default=DEFAULT_REPORT_TZ, help="Report date timezone.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)

    try:
        payload = run_checks(args)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_summary(payload)

    if payload["status"] == "ok":
        return 0
    if payload.get("connection_error"):
        return 1
    return 2


def run_checks(args: argparse.Namespace) -> dict[str, Any]:
    ssh_key = Path(args.ssh_key).expanduser()
    if not ssh_key.is_file():
        raise UsageError(f"SSH key not found: {ssh_key}")
    try:
        today = datetime.now(ZoneInfo(args.report_tz)).date().isoformat()
    except Exception as exc:  # noqa: BLE001 - argparse-compatible message
        raise UsageError(f"invalid --report-tz {args.report_tz!r}: {exc}") from exc

    checks: list[Check] = []
    connection_error = False

    remote_payload = remote_json(args.ssh_target, ssh_key)
    if remote_payload.get("_error"):
        checks.append(Check("ssh", False, remote_payload["_error"]))
        connection_error = True
    else:
        checks.extend(check_remote_payload(remote_payload, today))

    checks.extend(check_public_auth(args.host))

    return {
        "status": "ok" if checks and all(check.ok for check in checks) else "failed",
        "checked_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "host": args.host,
        "ssh_target": args.ssh_target,
        "report_tz": args.report_tz,
        "expected_report_date": today,
        "checks": [check.as_dict() for check in checks],
        "connection_error": connection_error,
    }


def remote_json(ssh_target: str, ssh_key: Path) -> dict[str, Any]:
    script = r'''
set -Eeuo pipefail
python3 - <<'PY'
from __future__ import annotations

import json
import subprocess
import urllib.request


def run(cmd: list[str], cwd: str | None = None) -> dict:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20)
    return {
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def fetch_caddy(path: str) -> dict:
    proc = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "caddy",
            "wget",
            "-q",
            "-O",
            "-",
            f"http://127.0.0.1:8080{path}",
        ],
        cwd="/opt/research-stack",
    )
    if proc["returncode"] != 0:
        return {"ok": False, "error": proc["stderr"] or proc["stdout"] or "docker compose exec failed"}
    try:
        payload = json.loads(proc["stdout"])
        return {"ok": True, "status_code": 200, "json": payload}
    except Exception as exc:
        return {"ok": False, "error": f"could not parse caddy response: {exc}"}


payload = {
    "timer_active": run(["systemctl", "is-active", "dailybrief.timer"]),
    "timer_enabled": run(["systemctl", "is-enabled", "dailybrief.timer"]),
    "service": run([
        "systemctl",
        "show",
        "dailybrief.service",
        "--property=Result,ActiveState,ExecMainStatus",
        "--no-pager",
    ]),
    "services": fetch_caddy("/api/services"),
    "health": fetch_caddy("/api/health"),
    "brief_health": fetch_caddy("/brief/health.json"),
}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
PY
'''
    cmd = [
        "ssh",
        "-i",
        str(ssh_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        ssh_target,
        script,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except Exception as exc:  # noqa: BLE001 - returned as smoke check failure
        return {"_error": str(exc)}
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"ssh exited {proc.returncode}").strip()
        return {"_error": detail[:500]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {"_error": f"could not parse remote JSON: {exc}"}


def check_remote_payload(payload: dict[str, Any], today: str) -> list[Check]:
    checks = [
        command_check("dailybrief.timer active", payload.get("timer_active"), "active"),
        command_check("dailybrief.timer enabled", payload.get("timer_enabled"), "enabled"),
    ]
    checks.append(check_service_result(payload.get("service")))
    checks.append(fetch_check("Research Hub /api/services", payload.get("services")))
    checks.append(fetch_check("Research Hub /api/health", payload.get("health")))
    checks.append(fetch_check("DailyBrief /brief/health.json", payload.get("brief_health")))
    checks.extend(check_brief_health(payload.get("brief_health", {}).get("json"), today))
    return checks


def command_check(name: str, result: Any, expected: str) -> Check:
    if not isinstance(result, dict):
        return Check(name, False, "missing command result")
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    ok = stdout == expected
    return Check(name, ok, stdout or stderr or f"expected {expected}")


def check_service_result(result: Any) -> Check:
    if not isinstance(result, dict):
        return Check("dailybrief.service result", False, "missing command result")
    values = parse_systemctl_show(str(result.get("stdout") or ""))
    active_state = values.get("ActiveState", "")
    service_result = values.get("Result", "")
    exec_status = values.get("ExecMainStatus", "")
    failed = active_state == "failed" or service_result in {"failed", "timeout", "exit-code", "signal"}
    ok = not failed and (service_result in {"success", ""} or exec_status == "0")
    detail = f"Result={service_result or '-'} ActiveState={active_state or '-'} ExecMainStatus={exec_status or '-'}"
    return Check("dailybrief.service result", ok, detail)


def parse_systemctl_show(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def fetch_check(name: str, result: Any) -> Check:
    if not isinstance(result, dict):
        return Check(name, False, "missing fetch result")
    if result.get("ok") is True:
        return Check(name, True, f"HTTP {result.get('status_code')}")
    return Check(name, False, str(result.get("error") or "fetch failed")[:300])


def check_brief_health(health: Any, today: str) -> list[Check]:
    if not isinstance(health, dict):
        return [Check("DailyBrief health payload", False, "health JSON missing or invalid")]
    checks = [
        Check("DailyBrief health status", health.get("status") == "ok", f"status={health.get('status')}"),
        Check(
            "DailyBrief latest report date",
            health.get("latest_report_date") == today,
            f"latest_report_date={health.get('latest_report_date')} expected={today}",
        ),
        Check("DailyBrief missing artifacts", health.get("missing") == [], f"missing={health.get('missing')}"),
    ]
    artifacts = health.get("artifacts")
    if isinstance(artifacts, dict):
        missing = [name for name in CORE_ARTIFACTS if artifacts.get(name) is not True]
        checks.append(Check("DailyBrief core artifacts", not missing, f"missing_or_false={','.join(missing) or '-'}"))
    else:
        checks.append(Check("DailyBrief core artifacts", False, "artifacts missing"))
    return checks


def check_public_auth(host: str) -> list[Check]:
    checks = []
    for name, path in (("public / Basic Auth", "/"), ("public /brief/ Basic Auth", "/brief/")):
        code, detail = http_status(f"http://{host}{path}")
        checks.append(Check(name, code == 401, f"HTTP {code}" if code else detail))
    return checks


def http_status(url: str) -> tuple[int | None, str]:
    request = Request(url, headers={"User-Agent": "research-stack-smoke/0.1"})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - operator-provided URL
            response.read(128)
            return int(response.status), ""
    except HTTPError as exc:
        return int(exc.code), ""
    except URLError as exc:
        return None, str(exc.reason)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def print_summary(payload: dict[str, Any]) -> None:
    print(f"status={payload['status']}")
    print(f"host={payload['host']}")
    print(f"expected_report_date={payload['expected_report_date']} ({payload['report_tz']})")
    for check in payload["checks"]:
        mark = "ok" if check["ok"] else "FAIL"
        print(f"{mark} {check['name']}: {check['detail']}")


class UsageError(Exception):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
