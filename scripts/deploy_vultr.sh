#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH_TARGET="${SSH_TARGET:-root@149.28.156.116}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/research_stack_vultr}"
REMOTE_DIR="${REMOTE_DIR:-/opt/research-stack}"
HUB_AUTH_USER="${HUB_AUTH_USER:-}"
HUB_AUTH_HASH="${HUB_AUTH_HASH:-}"
DAILYBRIEF_PUBLIC_REPORTS_URL="${DAILYBRIEF_PUBLIC_REPORTS_URL:-http://149.28.156.116/brief/}"
DAILYBRIEF_REPORTS_HEALTH_CHECK_URL="${DAILYBRIEF_REPORTS_HEALTH_CHECK_URL:-http://caddy:8080/brief/health.json}"
MARKET_DATA_LAB_REPO_URL="${MARKET_DATA_LAB_REPO_URL:-https://github.com/YOHO-ENT/market-data-lab.git}"
FIRN_REPO_URL="${FIRN_REPO_URL:-https://github.com/YOHO-ENT/firn-update.git}"
TRADINGAGENTS_REPO_URL="${TRADINGAGENTS_REPO_URL:-https://github.com/YOHO-ENT/trading-agents-update.git}"
PY_MOOMOO_API_REPO_URL="${PY_MOOMOO_API_REPO_URL:-https://github.com/YOHO-ENT/moomoo-api.git}"
MARKET_DATA_LAB_LOCAL_DIR="${MARKET_DATA_LAB_LOCAL_DIR:-$ROOT_DIR/../market-data-lab}"
FIRN_LOCAL_DIR="${FIRN_LOCAL_DIR:-$ROOT_DIR/../Firn}"
TRADINGAGENTS_LOCAL_DIR="${TRADINGAGENTS_LOCAL_DIR:-$ROOT_DIR/../TradingAgents}"
PY_MOOMOO_API_LOCAL_DIR="${PY_MOOMOO_API_LOCAL_DIR:-$ROOT_DIR/../py-moomoo-api}"
MARKET_DATA_LAB_REMOTE_DIR="${MARKET_DATA_LAB_REMOTE_DIR:-/opt/market-data-lab}"
FIRN_REMOTE_DIR="${FIRN_REMOTE_DIR:-/opt/Firn}"
TRADINGAGENTS_REMOTE_DIR="${TRADINGAGENTS_REMOTE_DIR:-/opt/TradingAgents}"
PY_MOOMOO_API_REMOTE_DIR="${PY_MOOMOO_API_REMOTE_DIR:-/opt/py-moomoo-api}"

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

b64() {
  printf '%s' "$1" | base64 | tr -d '\n'
}

value_from_lines() {
  local key="$1"
  awk -v key="$key" -F= '$1 == key { sub("^[^=]*=", ""); print; exit }'
}

strip_env_quotes() {
  local value="$1"
  if [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
    value="${value//\\\'/\'}"
  elif [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

run_local_checks() {
  log "running local validation"
  python3 scripts/check.py
  python3 -m json.tool catalog/services.json >/tmp/research-stack-services.json
  python3 -m compileall -q research_hub scripts/check.py
  node --check research_hub/static/app.js
  git diff --check
}

check_git_state() {
  log "checking git state"
  if ! git diff --quiet || ! git diff --cached --quiet; then
    fail "working tree has uncommitted changes"
  fi
  git fetch origin
  local branch
  branch="$(git branch --show-current)"
  [ "$branch" = "main" ] || fail "expected branch main, got ${branch}"
  local counts
  counts="$(git rev-list --left-right --count main...origin/main)"
  [ "$counts" = "0	0" ] || fail "main and origin/main are not in sync: ${counts}"
}

ssh_cmd() {
  ssh -i "$SSH_KEY" -o BatchMode=yes "$SSH_TARGET" "$@"
}

read_remote_auth() {
  local remote_dir_q
  printf -v remote_dir_q '%q' "$REMOTE_DIR"
  ssh_cmd "if [ -f ${remote_dir_q}/.env ]; then grep -E '^(HUB_AUTH_USER|HUB_AUTH_HASH)=' ${remote_dir_q}/.env || true; fi" 2>/dev/null || true
}

upload_repo_archive() {
  local name="$1"
  local local_dir="$2"
  local remote_dir="$3"
  local remote_dir_q
  [ -d "$local_dir/.git" ] || fail "${name} local git repo not found: ${local_dir}"
  printf -v remote_dir_q '%q' "$remote_dir"
  log "uploading ${name} source archive to ${SSH_TARGET}:${remote_dir}"
  git -C "$local_dir" archive --format=tar HEAD | ssh_cmd "rm -rf ${remote_dir_q} && install -d -m 0755 ${remote_dir_q} && tar -xf - -C ${remote_dir_q}"
}

upload_source_archives() {
  upload_repo_archive "market-data-lab" "$MARKET_DATA_LAB_LOCAL_DIR" "$MARKET_DATA_LAB_REMOTE_DIR"
  upload_repo_archive "Firn" "$FIRN_LOCAL_DIR" "$FIRN_REMOTE_DIR"
  upload_repo_archive "TradingAgents" "$TRADINGAGENTS_LOCAL_DIR" "$TRADINGAGENTS_REMOTE_DIR"
  upload_repo_archive "py-moomoo-api" "$PY_MOOMOO_API_LOCAL_DIR" "$PY_MOOMOO_API_REMOTE_DIR"
}

resolve_auth() {
  local existing_env existing_user existing_hash auth_password
  existing_env="$(read_remote_auth)"
  existing_user="$(strip_env_quotes "$(printf '%s\n' "$existing_env" | value_from_lines HUB_AUTH_USER || true)")"
  existing_hash="$(strip_env_quotes "$(printf '%s\n' "$existing_env" | value_from_lines HUB_AUTH_HASH || true)")"

  HUB_AUTH_USER="${HUB_AUTH_USER:-${existing_user:-admin}}"
  HUB_AUTH_HASH="${HUB_AUTH_HASH:-${existing_hash:-}}"
  auth_password=""

  if [ -n "${HUB_AUTH_PASSWORD_FILE:-}" ]; then
    [ -f "$HUB_AUTH_PASSWORD_FILE" ] || fail "HUB_AUTH_PASSWORD_FILE does not exist"
    auth_password="$(<"$HUB_AUTH_PASSWORD_FILE")"
  elif [ -n "${HUB_AUTH_PASSWORD:-}" ]; then
    auth_password="$HUB_AUTH_PASSWORD"
  elif [ -z "$HUB_AUTH_HASH" ]; then
    if [ ! -t 0 ]; then
      fail "HUB_AUTH_PASSWORD_FILE or HUB_AUTH_PASSWORD is required when no remote auth hash exists"
    fi
    read -r -s -p "Hub Basic Auth password for ${HUB_AUTH_USER}: " auth_password
    printf '\n'
  fi

  if [ -n "$auth_password" ]; then
    log "hashing Basic Auth password on remote Caddy image"
    HUB_AUTH_HASH="$(printf '%s\n' "$auth_password" | ssh_cmd "docker run -i --rm caddy:2-alpine caddy hash-password --algorithm bcrypt")"
  fi

  [ -n "$HUB_AUTH_USER" ] || fail "HUB_AUTH_USER is empty"
  [ -n "$HUB_AUTH_HASH" ] || fail "HUB_AUTH_HASH is empty"
}

deploy_remote() {
  log "deploying to ${SSH_TARGET}:${REMOTE_DIR}"
  local remote_dir_b64 auth_user_b64 auth_hash_b64 reports_url_b64 reports_health_b64
  local market_repo_b64 firn_repo_b64 trading_repo_b64 moomoo_repo_b64
  local market_dir_b64 firn_dir_b64 trading_dir_b64 moomoo_dir_b64
  remote_dir_b64="$(b64 "$REMOTE_DIR")"
  auth_user_b64="$(b64 "$HUB_AUTH_USER")"
  auth_hash_b64="$(b64 "$HUB_AUTH_HASH")"
  reports_url_b64="$(b64 "$DAILYBRIEF_PUBLIC_REPORTS_URL")"
  reports_health_b64="$(b64 "$DAILYBRIEF_REPORTS_HEALTH_CHECK_URL")"
  market_repo_b64="$(b64 "$MARKET_DATA_LAB_REPO_URL")"
  firn_repo_b64="$(b64 "$FIRN_REPO_URL")"
  trading_repo_b64="$(b64 "$TRADINGAGENTS_REPO_URL")"
  moomoo_repo_b64="$(b64 "$PY_MOOMOO_API_REPO_URL")"
  market_dir_b64="$(b64 "$MARKET_DATA_LAB_REMOTE_DIR")"
  firn_dir_b64="$(b64 "$FIRN_REMOTE_DIR")"
  trading_dir_b64="$(b64 "$TRADINGAGENTS_REMOTE_DIR")"
  moomoo_dir_b64="$(b64 "$PY_MOOMOO_API_REMOTE_DIR")"

  ssh_cmd \
    "REMOTE_DIR_B64='$remote_dir_b64' AUTH_USER_B64='$auth_user_b64' AUTH_HASH_B64='$auth_hash_b64' REPORTS_URL_B64='$reports_url_b64' REPORTS_HEALTH_B64='$reports_health_b64' MARKET_REPO_B64='$market_repo_b64' FIRN_REPO_B64='$firn_repo_b64' TRADING_REPO_B64='$trading_repo_b64' MOOMOO_REPO_B64='$moomoo_repo_b64' MARKET_DIR_B64='$market_dir_b64' FIRN_DIR_B64='$firn_dir_b64' TRADING_DIR_B64='$trading_dir_b64' MOOMOO_DIR_B64='$moomoo_dir_b64' bash -s" <<'REMOTE'
set -Eeuo pipefail

decode() {
  printf '%s' "$1" | base64 -d
}

REMOTE_DIR="$(decode "$REMOTE_DIR_B64")"
HUB_AUTH_USER_VALUE="$(decode "$AUTH_USER_B64")"
HUB_AUTH_HASH_VALUE="$(decode "$AUTH_HASH_B64")"
DAILYBRIEF_PUBLIC_REPORTS_URL_VALUE="$(decode "$REPORTS_URL_B64")"
DAILYBRIEF_REPORTS_HEALTH_CHECK_URL_VALUE="$(decode "$REPORTS_HEALTH_B64")"
MARKET_DATA_LAB_REPO_URL="$(decode "$MARKET_REPO_B64")"
FIRN_REPO_URL="$(decode "$FIRN_REPO_B64")"
TRADINGAGENTS_REPO_URL="$(decode "$TRADING_REPO_B64")"
PY_MOOMOO_API_REPO_URL="$(decode "$MOOMOO_REPO_B64")"
MARKET_DATA_LAB_DIR_VALUE="$(decode "$MARKET_DIR_B64")"
FIRN_DIR_VALUE="$(decode "$FIRN_DIR_B64")"
TRADINGAGENTS_DIR_VALUE="$(decode "$TRADING_DIR_B64")"
PY_MOOMOO_API_DIR_VALUE="$(decode "$MOOMOO_DIR_B64")"

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
docker compose version >/dev/null

require_source() {
  local target_dir="$1"
  local name="$2"
  local marker="$3"
  if [ ! -f "${target_dir}/${marker}" ]; then
    echo "missing uploaded ${name} source marker: ${target_dir}/${marker}" >&2
    exit 1
  fi
}

if [ -d "${REMOTE_DIR}/.git" ]; then
  git -C "$REMOTE_DIR" fetch origin
  git -C "$REMOTE_DIR" checkout main
  git -C "$REMOTE_DIR" pull --ff-only origin main
else
  rm -rf "$REMOTE_DIR"
  git clone https://github.com/YOHO-ENT/stock-research-stack.git "$REMOTE_DIR"
fi

require_source "$MARKET_DATA_LAB_DIR_VALUE" "market-data-lab" "pyproject.toml"
require_source "$FIRN_DIR_VALUE" "Firn" "global-market-agent/Dockerfile"
require_source "$TRADINGAGENTS_DIR_VALUE" "TradingAgents" "pyproject.toml"
require_source "$PY_MOOMOO_API_DIR_VALUE" "py-moomoo-api" "setup.py"

cd "$REMOTE_DIR"
previous_env="$(mktemp)"
if [ -f .env ]; then
  cp .env "$previous_env"
else
  : > "$previous_env"
fi
cp .env.production.example .env

export HUB_AUTH_USER_VALUE
export HUB_AUTH_HASH_VALUE
export DAILYBRIEF_PUBLIC_REPORTS_URL_VALUE
export DAILYBRIEF_REPORTS_HEALTH_CHECK_URL_VALUE
export MARKET_DATA_LAB_DIR_VALUE
export FIRN_DIR_VALUE
export TRADINGAGENTS_DIR_VALUE
export PY_MOOMOO_API_DIR_VALUE
export PREVIOUS_ENV_PATH="$previous_env"
python3 - <<'PY'
from pathlib import Path
import os
import secrets

def quote_env(value: str) -> str:
    if value == "":
        return ""
    if any(char in value for char in " \t#$'\"\\"):
        return "'" + value.replace("'", "\\'") + "'"
    return value

def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, raw_value = raw_line.split("=", 1)
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
            if raw_value.strip().startswith("'"):
                value = value.replace("\\'", "'")
        values[key.strip()] = value
    return values

path = Path(".env")
previous = parse_env(Path(os.environ["PREVIOUS_ENV_PATH"]))
preserve_keys = {
    "FIRN_JWT_SECRET",
    "FIRN_ADMIN_PASSWORD",
    "FIRN_DEEPSEEK_API_KEY",
    "FIRN_OPENAI_API_KEY",
    "FIRN_GEMINI_API_KEY",
    "FIRN_TAVILY_API_KEY",
    "TRADINGAGENTS_OPENAI_API_KEY",
    "TRADINGAGENTS_ANTHROPIC_API_KEY",
    "TRADINGAGENTS_GOOGLE_API_KEY",
    "TRADINGAGENTS_FINNHUB_API_KEY",
}
updates = {
    "HUB_AUTH_USER": os.environ["HUB_AUTH_USER_VALUE"],
    "HUB_AUTH_HASH": os.environ["HUB_AUTH_HASH_VALUE"],
    "DAILYBRIEF_PUBLIC_REPORTS_URL": os.environ["DAILYBRIEF_PUBLIC_REPORTS_URL_VALUE"],
    "DAILYBRIEF_REPORTS_HEALTH_CHECK_URL": os.environ["DAILYBRIEF_REPORTS_HEALTH_CHECK_URL_VALUE"],
    "MARKET_DATA_LAB_DIR": os.environ["MARKET_DATA_LAB_DIR_VALUE"],
    "FIRN_DIR": os.environ["FIRN_DIR_VALUE"],
    "TRADINGAGENTS_DIR": os.environ["TRADINGAGENTS_DIR_VALUE"],
    "PY_MOOMOO_API_DIR": os.environ["PY_MOOMOO_API_DIR_VALUE"],
}
for key in preserve_keys:
    if previous.get(key):
        updates[key] = previous[key]

if not updates.get("FIRN_JWT_SECRET"):
    updates["FIRN_JWT_SECRET"] = secrets.token_urlsafe(48)
if not updates.get("FIRN_ADMIN_PASSWORD"):
    updates["FIRN_ADMIN_PASSWORD"] = secrets.token_urlsafe(24)

lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
output = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else None
    if key in updates:
        output.append(f"{key}={quote_env(updates[key])}")
        seen.add(key)
    else:
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(f"{key}={quote_env(value)}")
path.write_text("\n".join(output) + "\n", encoding="utf-8")
PY
rm -f "$previous_env"

install -d -m 0755 runtime/dailybrief-reports
if [ ! -f runtime/dailybrief-reports/index.html ]; then
  cat > runtime/dailybrief-reports/index.html <<'HTML'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DailyBrief Reports</title>
  <style>
    body { background:#0b1120; color:#e2ebf5; font-family:system-ui,-apple-system,sans-serif; margin:0; padding:48px; }
    main { max-width:720px; }
    h1 { margin:0 0 12px; font-size:32px; }
    p { color:#9fb0c8; line-height:1.6; }
    code { color:#00d4aa; }
  </style>
</head>
<body>
  <main>
    <h1>DailyBrief Reports</h1>
    <p>The static report mount is ready. Publish generated DailyBrief files into <code>runtime/dailybrief-reports</code> on the server to replace this placeholder.</p>
  </main>
</body>
</html>
HTML
fi

docker compose up -d --build
docker compose ps
REMOTE
}

verify_remote() {
  log "verifying unauthenticated protection"
  local route code
  for route in / /brief/ /market/ /firn/ /agents/ /moomoo/; do
    code=""
    for _ in {1..20}; do
      code="$(curl --max-time 3 -s -o /dev/null -w '%{http_code}' "http://149.28.156.116${route}" || true)"
      [ "$code" = "401" ] && break
      sleep 1
    done
    [ "$code" = "401" ] || fail "expected unauthenticated ${route} to return 401, got ${code}"
  done

  log "verifying remote internal endpoints"
  ssh_cmd "cd '$REMOTE_DIR' && docker compose ps && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/ && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/api/services && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/api/health && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/api/control/status && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/brief/ && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/market/ && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/market/api/health && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/firn/ && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/firn/api/health && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/agents/ && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/agents/api/health && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/moomoo/ && \
    docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/moomoo/api/watchlists/status"
}

main() {
  cd "$ROOT_DIR"
  run_local_checks
  check_git_state
  resolve_auth
  upload_source_archives
  deploy_remote
  verify_remote
  log "done"
}

main "$@"
