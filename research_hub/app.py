"""Stdlib-only HTTP server for Research Hub."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import socket
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3030
DEFAULT_TIMEOUT_SECONDS = 1.5
DEFAULT_CATALOG_MODE = "local"

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "catalog" / "services.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None

PUBLIC_SERVICE_FIELDS = {
    "id",
    "name",
    "role",
    "component_type",
    "local_url",
    "public_url",
    "public_health_check_url",
    "health_check_url",
    "dependencies",
    "notes",
}

SERVICE_PUBLIC_ENV = {
    "market-data-lab-api": ("MARKET_DATA_LAB_API_PUBLIC_URL", "MARKET_DATA_LAB_API_PUBLIC_HEALTH_CHECK_URL"),
    "market-data-lab-ui": ("MARKET_DATA_LAB_UI_PUBLIC_URL", "MARKET_DATA_LAB_UI_PUBLIC_HEALTH_CHECK_URL"),
    "firn-api": ("FIRN_API_PUBLIC_URL", "FIRN_API_PUBLIC_HEALTH_CHECK_URL"),
    "firn-ui": ("FIRN_UI_PUBLIC_URL", "FIRN_UI_PUBLIC_HEALTH_CHECK_URL"),
    "tradingagents-api": ("TRADINGAGENTS_API_PUBLIC_URL", "TRADINGAGENTS_API_PUBLIC_HEALTH_CHECK_URL"),
    "tradingagents-ui": ("TRADINGAGENTS_UI_PUBLIC_URL", "TRADINGAGENTS_UI_PUBLIC_HEALTH_CHECK_URL"),
    "moomoo-account-web": ("MOOMOO_ACCOUNT_WEB_PUBLIC_URL", "MOOMOO_ACCOUNT_WEB_PUBLIC_HEALTH_CHECK_URL"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("catalog root must be a JSON object")
    services = payload.get("services")
    if not isinstance(services, list):
        raise ValueError("catalog.services must be a list")
    return payload


def catalog_mode() -> str:
    raw = os.getenv("RESEARCH_HUB_CATALOG_MODE", DEFAULT_CATALOG_MODE).strip().lower()
    if raw in {"prod", "production"}:
        return "production"
    return "local"


def env_text(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def join_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def apply_runtime_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    service = dict(raw)
    service_id = service.get("id")
    if service_id == "research-hub":
        public_url = env_text("RESEARCH_HUB_PUBLIC_URL")
        if public_url:
            service["public_url"] = public_url
        health_url = env_text("RESEARCH_HUB_HEALTH_CHECK_URL")
        if health_url:
            service["public_health_check_url"] = health_url
    elif service_id == "dailybrief-pipeline":
        reports_url = env_text("DAILYBRIEF_PUBLIC_REPORTS_URL")
        if reports_url:
            service["public_url"] = reports_url
        reports_health_url = env_text("DAILYBRIEF_REPORTS_HEALTH_CHECK_URL")
        if reports_health_url:
            service["public_health_check_url"] = reports_health_url
    elif service_id in SERVICE_PUBLIC_ENV:
        public_env, health_env = SERVICE_PUBLIC_ENV[service_id]
        public_url = env_text(public_env)
        if public_url:
            service["public_url"] = public_url
        health_url = env_text(health_env)
        if health_url:
            service["public_health_check_url"] = health_url
    return service


def include_in_catalog(service: dict[str, Any], mode: str) -> bool:
    if mode != "production":
        return True
    if service.get("production_visible") is True:
        return True
    public_url = service.get("public_url")
    return isinstance(public_url, str) and bool(public_url.strip())


def list_services() -> list[dict[str, Any]]:
    mode = catalog_mode()
    services = []
    for raw in load_catalog()["services"]:
        if not isinstance(raw, dict):
            continue
        service = apply_runtime_overrides(raw)
        if not include_in_catalog(service, mode):
            continue
        public = {key: service.get(key) for key in PUBLIC_SERVICE_FIELDS if key in service}
        public.setdefault("dependencies", [])
        public.setdefault("notes", [])
        services.append(public)
    return services


def build_health_payload(timeout_seconds: float) -> dict[str, Any]:
    services = list_services()
    return {
        "checked_at": utc_now(),
        "timeout_seconds": timeout_seconds,
        "results": [check_service(service, timeout_seconds) for service in services],
    }


def build_control_status_payload(timeout_seconds: float) -> dict[str, Any]:
    """Return read-only control-loop signals for the local research workflow."""

    signals = [
        market_data_universe_signal(timeout_seconds),
        firn_watchlist_signal(timeout_seconds),
        tradingagents_market_data_signal(timeout_seconds),
        dailybrief_local_signal(),
    ]
    counts = {"ok": 0, "warn": 0, "down": 0, "skipped": 0}
    for signal in signals:
        status = signal.get("status")
        if status in counts:
            counts[status] += 1
    overall = "ok" if counts["down"] == 0 and counts["warn"] == 0 else "down"
    if counts["down"] == 0 and counts["warn"] > 0:
        overall = "warn"
    return {
        "checked_at": utc_now(),
        "timeout_seconds": timeout_seconds,
        "status": overall,
        "summary": counts,
        "signals": signals,
    }


def market_data_universe_signal(timeout_seconds: float) -> dict[str, Any]:
    base_url = env_text("MARKET_DATA_API_URL") or "http://127.0.0.1:8010"
    target = join_url(base_url, "/universes")
    try:
        payload = fetch_json(target, timeout_seconds)
        groups = payload.get("groups") if isinstance(payload.get("groups"), dict) else {}
        group_count = int(payload.get("group_count") or len(groups))
        ticker_count = int(payload.get("ticker_count") or unique_ticker_count(groups))
        synced_at = payload.get("synced_at")
        message = f"{group_count} groups, {ticker_count} tickers"
        if isinstance(synced_at, str) and synced_at.strip():
            message = f"{message}; synced {synced_at.strip()}"
        return control_signal(
            "market-data-universe",
            "Market Data Lab universe",
            "ok",
            target,
            message=message,
            data={
                "group_count": group_count,
                "ticker_count": ticker_count,
                "synced_at": synced_at,
            },
        )
    except Exception as exc:  # noqa: BLE001 - status endpoint must not crash
        return control_signal("market-data-universe", "Market Data Lab universe", "down", target, message=safe_error(exc))


def firn_watchlist_signal(timeout_seconds: float) -> dict[str, Any]:
    base_url = env_text("FIRN_API_URL") or "http://127.0.0.1:8000"
    target = join_url(base_url, "/api/config/watchlist")
    try:
        payload = fetch_json(target, timeout_seconds)
        categories = payload.get("categories") if isinstance(payload.get("categories"), dict) else {}
        category_count = len(categories)
        ticker_count = unique_ticker_count(
            {
                key: (value.get("tickers") if isinstance(value, dict) else [])
                for key, value in categories.items()
            }
        )
        editable = payload.get("editable")
        message = f"{category_count} categories, {ticker_count} tickers"
        if isinstance(editable, bool):
            message = f"{message}; editable={str(editable).lower()}"
        return control_signal(
            "firn-watchlist",
            "Firn watchlist",
            "ok",
            target,
            message=message,
            data={
                "category_count": category_count,
                "ticker_count": ticker_count,
                "editable": editable,
                "managed_by": payload.get("managed_by"),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return control_signal("firn-watchlist", "Firn watchlist", "down", target, message=safe_error(exc))


def tradingagents_market_data_signal(timeout_seconds: float) -> dict[str, Any]:
    base_url = env_text("TRADINGAGENTS_API_URL") or "http://127.0.0.1:8002"
    target = join_url(base_url, "/api/market-data/universes")
    try:
        payload = fetch_json(target, timeout_seconds)
        groups = payload.get("groups") if isinstance(payload.get("groups"), dict) else {}
        group_count = len(groups)
        ticker_count = unique_ticker_count(groups)
        status = "ok" if payload.get("status") == "ok" else "warn"
        message = payload.get("message") if isinstance(payload.get("message"), str) else f"{group_count} groups, {ticker_count} tickers"
        return control_signal(
            "tradingagents-market-data",
            "TradingAgents Market Data Lab adapter",
            status,
            target,
            message=message,
            data={
                "group_count": group_count,
                "ticker_count": ticker_count,
                "adapter_status": payload.get("status"),
                "base_url": payload.get("base_url"),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return control_signal(
            "tradingagents-market-data",
            "TradingAgents Market Data Lab adapter",
            "down",
            target,
            message=safe_error(exc),
        )


def dailybrief_local_signal() -> dict[str, Any]:
    reports_path = Path(env_text("DAILYBRIEF_REPORTS_PATH") or "/Users/yongnahwa/Desktop/DailyBrief/daily_reports")
    today = datetime.now().date().isoformat()
    target = str(reports_path)
    if not reports_path.exists():
        return control_signal("dailybrief-local-report", "DailyBrief local reports", "down", target, message="reports path missing")
    try:
        latest_date = latest_report_date(reports_path)
    except OSError as exc:
        return control_signal(
            "dailybrief-local-report",
            "DailyBrief local reports",
            "down",
            target,
            message=f"reports path unreadable: {safe_error(exc)}",
        )
    index_exists = (reports_path / "index.html").is_file()
    if latest_date == today and index_exists:
        status = "ok"
        message = f"latest report {latest_date}"
    elif latest_date:
        status = "warn"
        message = f"latest report {latest_date}; expected {today}"
    else:
        status = "down"
        message = "no dated report directories found"
    return control_signal(
        "dailybrief-local-report",
        "DailyBrief local reports",
        status,
        target,
        message=message,
        data={
            "latest_report_date": latest_date,
            "expected_report_date": today,
            "index_exists": index_exists,
        },
    )


def control_signal(
    signal_id: str,
    label: str,
    status: str,
    target: str | None,
    *,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": signal_id,
        "label": label,
        "status": status,
        "target": target,
        "message": message,
        "data": data or {},
    }


def fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "research-hub/control-status"})
    opener = build_opener(NoRedirectHandler)
    try:
        with opener.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - local operator URLs only
            status_code = int(getattr(response, "status", response.getcode()))
            body = response.read(1024 * 256)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from None
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    if not (200 <= status_code < 300):
        raise RuntimeError(f"HTTP {status_code}")
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"invalid JSON: {safe_error(exc)}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("JSON response must be an object")
    return payload


def unique_ticker_count(groups: dict[str, Any]) -> int:
    seen = set()
    for tickers in groups.values():
        if isinstance(tickers, str):
            candidates = [tickers]
        else:
            try:
                candidates = list(tickers)
            except TypeError:
                candidates = []
        for ticker in candidates:
            text = str(ticker).strip().upper()
            if text:
                seen.add(text)
    return len(seen)


def latest_report_date(reports_path: Path) -> str | None:
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    dates = [
        child.name
        for child in reports_path.iterdir()
        if child.is_dir() and date_re.match(child.name)
    ]
    return max(dates) if dates else None


def check_service(service: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    target = check_target(service)
    if target is None:
        return base_result(service, "skipped", target, message="no checkable target")

    started = time.perf_counter()
    try:
        if target.startswith("tcp://"):
            detail = check_tcp(target, timeout_seconds)
        elif target.startswith(("http://", "https://")):
            detail = check_http(target, timeout_seconds)
        else:
            return base_result(service, "skipped", target, message="unsupported target")
    except Exception as exc:  # noqa: BLE001 - health checks must never crash the hub
        latency = elapsed_ms(started)
        return base_result(
            service,
            "down",
            target,
            latency_ms=latency,
            message=safe_error(exc),
        )

    latency = elapsed_ms(started)
    return {
        **base_result(service, detail["status"], target, latency_ms=latency),
        **{key: value for key, value in detail.items() if key != "status"},
    }


def check_target(service: dict[str, Any]) -> str | None:
    if catalog_mode() == "production":
        public_health_url = service.get("public_health_check_url")
        if isinstance(public_health_url, str) and public_health_url.strip():
            return public_health_url.strip()
        public_url = service.get("public_url")
        if isinstance(public_url, str) and public_url.strip():
            return public_url.strip()

    health_url = service.get("health_check_url")
    if isinstance(health_url, str) and health_url.strip():
        return health_url.strip()
    local_url = service.get("local_url")
    if isinstance(local_url, str) and local_url.startswith("tcp://"):
        return local_url
    return None


def check_http(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "research-hub/0.1"})
    opener = build_opener(NoRedirectHandler)
    try:
        with opener.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - local operator URLs only
            status_code = int(getattr(response, "status", response.getcode()))
            content_type = response.headers.get("Content-Type", "")
            # Read a small amount so servers complete the response without loading
            # large HTML pages into memory.
            body = response.read(4096)
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            return {
                "status": "ok",
                "status_code": exc.code,
                "message": f"redirect {exc.code}",
            }
        return {
            "status": "down",
            "status_code": exc.code,
            "message": f"HTTP {exc.code}",
        }
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc

    if 200 <= status_code < 400:
        health_detail = json_health_detail(body, content_type)
        if health_detail is not None:
            return {"status_code": status_code, **health_detail}
        return {"status": "ok", "status_code": status_code, "message": "reachable"}
    return {"status": "down", "status_code": status_code, "message": f"HTTP {status_code}"}


def json_health_detail(body: bytes, content_type: str) -> dict[str, str] | None:
    sample = body.lstrip()
    if not sample:
        return None
    if "json" not in content_type.lower() and not sample.startswith(b"{"):
        return None
    try:
        payload = json.loads(sample.decode("utf-8"))
    except Exception:  # noqa: BLE001 - non-JSON health endpoints are allowed
        return None
    if not isinstance(payload, dict):
        return None
    if not any(key in payload for key in ("status", "latest_report_date", "artifacts", "missing")):
        return None

    raw_status = payload.get("status")
    status_text = str(raw_status).strip() if raw_status is not None else ""
    result_status = "ok" if not status_text or status_text.lower() == "ok" else "down"

    message_parts = []
    latest = payload.get("latest_report_date")
    if isinstance(latest, str) and latest.strip():
        message_parts.append(f"latest report {latest.strip()}")
    if status_text and status_text.lower() != "ok":
        message_parts.append(f"health {status_text}")
    missing = payload.get("missing")
    if isinstance(missing, list) and missing:
        message_parts.append("missing " + ",".join(str(item) for item in missing[:5]))
    message = "; ".join(message_parts) or "health JSON reachable"
    return {"status": result_status, "message": message}


def check_tcp(url: str, timeout_seconds: float) -> dict[str, Any]:
    parsed = urlparse(url)
    if not parsed.hostname or not parsed.port:
        return {"status": "skipped", "message": "invalid tcp target"}
    with socket.create_connection((parsed.hostname, parsed.port), timeout=timeout_seconds):
        return {"status": "ok", "message": "tcp reachable"}


def base_result(
    service: dict[str, Any],
    status: str,
    target: str | None,
    *,
    latency_ms: int | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "id": service.get("id"),
        "name": service.get("name"),
        "status": status,
        "target": target,
        "latency_ms": latency_ms,
        "message": message,
    }


def elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def safe_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    return text[:180] or exc.__class__.__name__


class ResearchHubHandler(BaseHTTPRequestHandler):
    server_version = "ResearchHub/0.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/":
                self.serve_static("index.html")
            elif path == "/api/services":
                self.send_json({"services": list_services()})
            elif path == "/api/health":
                timeout = getattr(self.server, "health_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
                self.send_json(build_health_payload(timeout))
            elif path == "/api/control/status":
                timeout = getattr(self.server, "health_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
                self.send_json(build_control_status_payload(timeout))
            elif path.startswith("/static/"):
                self.serve_static(path.removeprefix("/static/"))
            else:
                self.send_json({"error": "not found"}, status=404)
        except Exception as exc:  # noqa: BLE001 - return safe API errors
            self.send_json({"error": safe_error(exc)}, status=500)

    def serve_static(self, relative_path: str) -> None:
        target = (STATIC_DIR / relative_path).resolve()
        if not target.is_file() or not target.is_relative_to(STATIC_DIR.resolve()):
            self.send_json({"error": "not found"}, status=404)
            return
        content = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.name == "index.html":
            content_type = "text/html; charset=utf-8"
        elif target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")


class ResearchHubServer(ThreadingHTTPServer):
    health_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    health_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ResearchHubServer:
    server = ResearchHubServer((host, port), ResearchHubHandler)
    server.health_timeout_seconds = health_timeout_seconds
    return server


def run(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    health_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    server = create_server(host, port, health_timeout_seconds=health_timeout_seconds)
    url = f"http://{host}:{port}"
    print(f"Research Hub running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Research Hub.")
    finally:
        server.server_close()
