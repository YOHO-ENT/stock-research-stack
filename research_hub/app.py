"""Stdlib-only HTTP server for Research Hub."""

from __future__ import annotations

import json
import mimetypes
import os
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
