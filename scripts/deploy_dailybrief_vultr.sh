#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DAILYBRIEF_DIR="${DAILYBRIEF_DIR:-/Users/yongnahwa/Desktop/DailyBrief}"
DAILYBRIEF_REPO_URL="${DAILYBRIEF_REPO_URL:-https://github.com/YOHO-ENT/daily-brief-update.git}"
SSH_TARGET="${SSH_TARGET:-root@149.28.156.116}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/research_stack_vultr}"
REMOTE_DAILYBRIEF_DIR="${REMOTE_DAILYBRIEF_DIR:-/home/deploy/DailyBrief}"
REMOTE_REPORT_DIR="${REMOTE_REPORT_DIR:-/opt/research-stack/runtime/dailybrief-reports}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-/etc/dailybrief/dailybrief.env}"
DAILYBRIEF_REPORT_BASE_URL="${DAILYBRIEF_REPORT_BASE_URL:-http://149.28.156.116/brief/}"
DAILYBRIEF_SCHEDULE_TZ="${DAILYBRIEF_SCHEDULE_TZ:-Asia/Shanghai}"
RUN_DAILYBRIEF_NOW="${RUN_DAILYBRIEF_NOW:-1}"

log() {
  printf '[dailybrief-deploy] %s\n' "$*"
}

fail() {
  printf '[dailybrief-deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

ssh_cmd() {
  ssh -i "$SSH_KEY" -o BatchMode=yes "$SSH_TARGET" "$@"
}

check_git_state() {
  local repo_dir="$1"
  local label="$2"
  log "checking git state: ${label}"
  git -C "$repo_dir" fetch origin
  local branch
  branch="$(git -C "$repo_dir" branch --show-current)"
  [ "$branch" = "main" ] || fail "${label}: expected branch main, got ${branch}"
  if ! git -C "$repo_dir" diff --quiet || ! git -C "$repo_dir" diff --cached --quiet; then
    fail "${label}: working tree has uncommitted changes"
  fi
  local counts
  counts="$(git -C "$repo_dir" rev-list --left-right --count main...origin/main)"
  [ "$counts" = "0	0" ] || fail "${label}: main and origin/main are not in sync: ${counts}"
}

run_local_checks() {
  log "running research-stack validation"
  (
    cd "$ROOT_DIR"
    python3 scripts/check.py
    git diff --check
  )

  log "running DailyBrief validation"
  (
    cd "$DAILYBRIEF_DIR"
    python3 -m compileall dailybrief scripts tests
    python3 -m pytest -q
    python3 -m dailybrief run --dry-run --output-json >/tmp/dailybrief-dry-run.json
  )
}

build_env_file() {
  local output="$1"
  local env_file="${DAILYBRIEF_DIR}/.env.local"
  [ -f "$env_file" ] || fail "missing DailyBrief env file: ${env_file}"
  python3 - "$env_file" "$output" "$DAILYBRIEF_REPORT_BASE_URL" "$REMOTE_REPORT_DIR" <<'PY'
from __future__ import annotations

import shlex
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
report_base_url = sys.argv[3]
report_target = sys.argv[4]

provider_key_by_backend = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
}
optional_keys = [
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "MINIMAX_API_KEY",
    "MINIMAX_BASE_URL",
    "ZHIPU_API_KEY",
    "ZHIPU_BASE_URL",
]


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value:
            try:
                parts = shlex.split(value, comments=False, posix=True)
                value = parts[0] if parts else ""
            except ValueError:
                value = value.strip("\"'")
        values[key] = value
    return values


def quote(value: str) -> str:
    if value == "":
        return ""
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./:@%-+")
    if all(ch in safe for ch in value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


env = parse_env(env_path)
backend = env.get("LLM_BACKEND", "").strip()
if not backend:
    raise SystemExit("LLM_BACKEND is required in DailyBrief .env.local")
provider_key = provider_key_by_backend.get(backend)
if provider_key is None:
    raise SystemExit(f"unsupported LLM_BACKEND for production deploy: {backend}")
if not env.get(provider_key) and not env.get("LLM_API_KEY"):
    raise SystemExit(f"{provider_key} or LLM_API_KEY is required in DailyBrief .env.local")

output: dict[str, str] = {
    "DAILYBRIEF_LIVE_ALLOWED": "true",
    "REPORT_LOCALE": env.get("REPORT_LOCALE", "zh") or "zh",
    "REPORT_TZ": "Asia/Shanghai",
    "LLM_BACKEND": backend,
    "DAILYBRIEF_REPORT_BASE_URL": report_base_url,
    "DAILYBRIEF_REPORTS_TARGET": report_target,
    "SLACK_ENABLED": "false",
    "TELEGRAM_ENABLED": "false",
    "EMAIL_ENABLED": "false",
}
for key in optional_keys:
    if env.get(key):
        output[key] = env[key]

output_path.write_text(
    "\n".join(f"{key}={quote(value)}" for key, value in output.items()) + "\n",
    encoding="utf-8",
)
PY
  chmod 0600 "$output"
}

prepare_remote() {
  log "preparing remote DailyBrief runtime"
  local repo_url_q remote_dir_q report_dir_q env_file_q schedule_tz_q
  printf -v repo_url_q '%q' "$DAILYBRIEF_REPO_URL"
  printf -v remote_dir_q '%q' "$REMOTE_DAILYBRIEF_DIR"
  printf -v report_dir_q '%q' "$REMOTE_REPORT_DIR"
  printf -v env_file_q '%q' "$REMOTE_ENV_FILE"
  printf -v schedule_tz_q '%q' "$DAILYBRIEF_SCHEDULE_TZ"

  ssh_cmd "DAILYBRIEF_REPO_URL=${repo_url_q} REMOTE_DAILYBRIEF_DIR=${remote_dir_q} REMOTE_REPORT_DIR=${report_dir_q} REMOTE_ENV_FILE=${env_file_q} DAILYBRIEF_SCHEDULE_TZ=${schedule_tz_q} bash -s" <<'REMOTE'
set -Eeuo pipefail

export DEBIAN_FRONTEND=noninteractive
if ! command -v git >/dev/null || ! python3 -m venv --help >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git ca-certificates python3-venv python3-pip
fi

if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash deploy
fi

install -d -m 0755 -o deploy -g deploy /home/deploy
install -d -m 0755 -o deploy -g deploy "$REMOTE_REPORT_DIR"
chown -R deploy:deploy "$REMOTE_REPORT_DIR"
install -d -m 0750 -o root -g root "$(dirname "$REMOTE_ENV_FILE")"

if [ -d /opt/research-stack ]; then
  cd /opt/research-stack
  docker compose ps >/dev/null
else
  echo "/opt/research-stack is missing; deploy Research Hub first" >&2
  exit 1
fi

if [ -d "${REMOTE_DAILYBRIEF_DIR}/.git" ]; then
  runuser -u deploy -- git -C "$REMOTE_DAILYBRIEF_DIR" fetch origin
  runuser -u deploy -- git -C "$REMOTE_DAILYBRIEF_DIR" checkout main
  runuser -u deploy -- git -C "$REMOTE_DAILYBRIEF_DIR" pull --ff-only origin main
else
  rm -rf "$REMOTE_DAILYBRIEF_DIR"
  runuser -u deploy -- git clone "$DAILYBRIEF_REPO_URL" "$REMOTE_DAILYBRIEF_DIR"
fi

runuser -u deploy -- bash -lc "cd '$REMOTE_DAILYBRIEF_DIR' && python3 -m venv .venv && .venv/bin/pip install --upgrade pip setuptools wheel && .venv/bin/pip install -e '.[test]'"

install -d -m 0755 -o deploy -g deploy "$REMOTE_DAILYBRIEF_DIR/daily_reports" "$REMOTE_DAILYBRIEF_DIR/logs"
chmod 0755 "$REMOTE_DAILYBRIEF_DIR/deploy/vultr/run_dailybrief_once.sh"
install -m 0644 "$REMOTE_DAILYBRIEF_DIR/deploy/vultr/dailybrief.service" /etc/systemd/system/dailybrief.service
install -m 0644 "$REMOTE_DAILYBRIEF_DIR/deploy/vultr/dailybrief.timer" /etc/systemd/system/dailybrief.timer
systemctl daemon-reload
systemd-analyze calendar "*-*-* 08:00:00 ${DAILYBRIEF_SCHEDULE_TZ}" >/dev/null
REMOTE
}

install_remote_env() {
  local env_tmp="$1"
  local remote_tmp="/tmp/dailybrief.env.$$"
  log "installing private DailyBrief env on remote"
  scp -q -i "$SSH_KEY" "$env_tmp" "${SSH_TARGET}:${remote_tmp}"
  local remote_tmp_q env_file_q
  printf -v remote_tmp_q '%q' "$remote_tmp"
  printf -v env_file_q '%q' "$REMOTE_ENV_FILE"
  ssh_cmd "install -m 0600 -o root -g root ${remote_tmp_q} ${env_file_q}; rm -f ${remote_tmp_q}"
}

seed_reports() {
  [ -d "${DAILYBRIEF_DIR}/daily_reports" ] || fail "DailyBrief daily_reports directory is missing"
  log "seeding DailyBrief reports to remote"
  local remote_dir_q report_dir_q base_url_q
  printf -v remote_dir_q '%q' "$REMOTE_DAILYBRIEF_DIR"
  printf -v report_dir_q '%q' "$REMOTE_REPORT_DIR"
  printf -v base_url_q '%q' "$DAILYBRIEF_REPORT_BASE_URL"

  COPYFILE_DISABLE=1 tar -C "${DAILYBRIEF_DIR}/daily_reports" --exclude ".DS_Store" -cf - . \
    | ssh_cmd "install -d -m 0755 -o deploy -g deploy ${remote_dir_q}/daily_reports && tar -C ${remote_dir_q}/daily_reports -xf - && chown -R deploy:deploy ${remote_dir_q}/daily_reports"

  ssh_cmd "runuser -u deploy -- bash -lc 'cd ${remote_dir_q} && .venv/bin/python scripts/publish_reports.py --source ${remote_dir_q}/daily_reports --target ${report_dir_q} --public-url ${base_url_q}'"
}

start_and_verify() {
  log "verifying remote timer and static report health"
  ssh_cmd "systemctl enable --now dailybrief.timer"
  ssh_cmd "systemctl status dailybrief.timer --no-pager"
  if [ "$RUN_DAILYBRIEF_NOW" = "1" ]; then
    log "starting DailyBrief service once"
    ssh_cmd "systemctl start dailybrief.service"
  fi
  ssh_cmd "systemctl status dailybrief.service --no-pager || true"
  ssh_cmd "journalctl -u dailybrief.service -n 200 --no-pager"
  ssh_cmd "cd '$REMOTE_DAILYBRIEF_DIR' && .venv/bin/python scripts/check_vps_production.py --output-json"
  ssh_cmd "cd '$REMOTE_DAILYBRIEF_DIR' && .venv/bin/python scripts/check_dailybrief_acceptance.py --days 1 --output-dir '$REMOTE_REPORT_DIR' --output-json"
  ssh_cmd "cd /opt/research-stack && docker compose exec -T caddy wget -q -O /dev/null http://127.0.0.1:8080/brief/health.json"
}

main() {
  cd "$ROOT_DIR"
  [ -d "$DAILYBRIEF_DIR" ] || fail "DailyBrief repo not found: ${DAILYBRIEF_DIR}"
  local env_tmp
  env_tmp="$(mktemp)"
  DAILYBRIEF_DEPLOY_ENV_TMP="$env_tmp"
  trap 'rm -f "${DAILYBRIEF_DEPLOY_ENV_TMP:-}"' EXIT

  build_env_file "$env_tmp"
  run_local_checks
  check_git_state "$DAILYBRIEF_DIR" "DailyBrief"
  check_git_state "$ROOT_DIR" "research-stack"
  ssh_cmd "whoami >/dev/null"
  prepare_remote
  install_remote_env "$env_tmp"
  seed_reports
  start_and_verify
  log "done"
}

main "$@"
