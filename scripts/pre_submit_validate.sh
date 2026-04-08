#!/usr/bin/env bash
#
# pre_submit_validate.sh
#
# Extended pre-submission checks for OpenEnv hackathon submissions.
# This script complements scripts/validate-submission.sh by also checking
# inference contract requirements and baseline reproducibility.

set -euo pipefail

DOCKER_BUILD_TIMEOUT=600
INFERENCE_TIMEOUT=1200

PING_URL=""
REPO_DIR="."
SKIP_DOCKER=false
SKIP_INFERENCE=false
PYTHON_BIN=""
OPENENV_BIN=""
OPENENV_USE_MODULE=false
DOCKER_CONTAINER_ID=""
INFERENCE_OUT_FILE=".pre-submit-inference.out"

usage() {
  cat <<'EOF'
Usage: scripts/pre_submit_validate.sh [options]

Options:
  --ping-url <url>        HF Space URL (e.g., https://team-space.hf.space)
  --repo-dir <path>       Repo root directory (default: current directory)
  --skip-docker           Skip docker build check
  --skip-inference        Skip inference baseline check
  -h, --help              Show this help message

Required environment variables for inference checks:
  API_BASE_URL
  MODEL_NAME
  HF_TOKEN
EOF
}

run_with_timeout() {
  local secs="$1"; shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" "$@"
  else
    "$@" &
    local pid=$!
    ( sleep "$secs" && kill "$pid" 2>/dev/null ) &
    local watcher=$!
    wait "$pid" 2>/dev/null
    local rc=$?
    kill "$watcher" 2>/dev/null || true
    wait "$watcher" 2>/dev/null || true
    return $rc
  fi
}

log() {
  printf "[%s] %s\n" "$(date -u +%H:%M:%S)" "$*"
}

die() {
  log "FAILED -- $*"
  exit 1
}

pass() {
  log "PASSED -- $*"
}

cleanup() {
  if [ -n "$DOCKER_CONTAINER_ID" ]; then
    docker rm -f "$DOCKER_CONTAINER_ID" >/dev/null 2>&1 || true
  fi
  rm -f "$INFERENCE_OUT_FILE" >/dev/null 2>&1 || true
}

trap cleanup EXIT

resolve_python_bin() {
  local candidates=(
    "$REPO_DIR/.venv/bin/python"
    "$REPO_DIR/.venv/Scripts/python.exe"
    "$REPO_DIR/../.venv/bin/python"
    "$REPO_DIR/../.venv/Scripts/python.exe"
  )

  for c in "${candidates[@]}"; do
    if [ -x "$c" ]; then
      PYTHON_BIN="$c"
      return 0
    fi
  done

  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
    return 0
  fi

  return 1
}

resolve_openenv_cmd() {
  local candidates=(
    "$REPO_DIR/.venv/bin/openenv"
    "$REPO_DIR/.venv/Scripts/openenv.exe"
    "$REPO_DIR/../.venv/bin/openenv"
    "$REPO_DIR/../.venv/Scripts/openenv.exe"
  )

  for c in "${candidates[@]}"; do
    if [ -x "$c" ]; then
      OPENENV_BIN="$c"
      return 0
    fi
  done

  if command -v openenv >/dev/null 2>&1; then
    OPENENV_BIN="$(command -v openenv)"
    return 0
  fi

  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ping-url)
      shift
      [ "$#" -gt 0 ] || die "--ping-url requires a value"
      PING_URL="$1"
      ;;
    --repo-dir)
      shift
      [ "$#" -gt 0 ] || die "--repo-dir requires a value"
      REPO_DIR="$1"
      ;;
    --skip-docker)
      SKIP_DOCKER=true
      ;;
    --skip-inference)
      SKIP_INFERENCE=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
  shift
done

REPO_DIR="$(cd "$REPO_DIR" && pwd)"
cd "$REPO_DIR"

log "Repo: $REPO_DIR"

resolve_python_bin || die "No usable Python interpreter found"
log "Python: $PYTHON_BIN"

if resolve_openenv_cmd; then
  log "OpenEnv CLI: $OPENENV_BIN"
else
  OPENENV_USE_MODULE=true
  log "OpenEnv CLI via module: $PYTHON_BIN -m openenv"
fi

log "Step 1/8: Checking OpenEnv standard file layout"
required_files=(
  "openenv.yaml"
  "models.py"
  "env.py"
  "inference.py"
  "server/app.py"
  "server/cloud_devops_env_environment.py"
)
for f in "${required_files[@]}"; do
  [ -f "$f" ] || die "Missing required file: $f"
done
pass "Core OpenEnv file layout looks valid"

log "Step 2/8: Checking inference contract requirements"
[ -f "inference.py" ] || die "inference.py must exist in repo root"
grep -q "from openai import OpenAI" inference.py || die "inference.py must import OpenAI client"
grep -q "OpenAI(" inference.py || die "inference.py must instantiate OpenAI client"
grep -q "\[START\]" inference.py || die "inference.py must emit [START] logs"
grep -q "\[STEP\]" inference.py || die "inference.py must emit [STEP] logs"
grep -q "\[END\]" inference.py || die "inference.py must emit [END] logs"
pass "Inference script contract checks passed"

log "Step 3/8: Validating OpenEnv manifest and typed models"
if [ "$OPENENV_USE_MODULE" = true ]; then
  "$PYTHON_BIN" -m openenv validate >/tmp/openenv-validate.out 2>&1 || {
    cat /tmp/openenv-validate.out
    die "openenv validate failed"
  }
else
  "$OPENENV_BIN" validate >/tmp/openenv-validate.out 2>&1 || {
    cat /tmp/openenv-validate.out
    die "openenv validate failed"
  }
fi
pass "openenv validate passed"

log "Step 4/8: Optional HF Space ping check"
if [ -n "$PING_URL" ]; then
  PING_URL="${PING_URL%/}"
  code=$(curl -s -o /tmp/pre-submit-ping.out -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" -d '{}' \
    "$PING_URL/reset" --max-time 30 || printf "000")
  [ "$code" = "200" ] || die "HF Space /reset returned HTTP $code"
  pass "HF Space responds to /reset (HTTP 200)"
else
  log "SKIPPED -- no --ping-url provided"
fi

log "Step 5/8: Docker build + run check"
if [ "$SKIP_DOCKER" = true ]; then
  log "SKIPPED -- --skip-docker enabled"
else
  command -v docker >/dev/null 2>&1 || die "docker not found"
  if [ -f "Dockerfile" ]; then
    context="."
  elif [ -f "server/Dockerfile" ]; then
    context="server"
  else
    die "No Dockerfile found at root or server/"
  fi
  run_with_timeout "$DOCKER_BUILD_TIMEOUT" docker build "$context" >/tmp/pre-submit-docker.out 2>&1 || {
    tail -n 40 /tmp/pre-submit-docker.out
    die "docker build failed"
  }
  pass "Docker build succeeded"

  IMAGE_TAG="openenv-pre-submit-local"
  run_with_timeout "$DOCKER_BUILD_TIMEOUT" docker build -t "$IMAGE_TAG" "$context" >/tmp/pre-submit-docker-tagged.out 2>&1 || {
    tail -n 40 /tmp/pre-submit-docker-tagged.out
    die "docker build (tagged) failed"
  }

  DOCKER_CONTAINER_ID="$(docker run -d -p 127.0.0.1::8000 "$IMAGE_TAG" 2>/tmp/pre-submit-docker-run.err || true)"
  [ -n "$DOCKER_CONTAINER_ID" ] || {
    cat /tmp/pre-submit-docker-run.err
    die "docker run failed"
  }

  HOST_PORT="$(docker port "$DOCKER_CONTAINER_ID" 8000/tcp | tail -n 1 | awk -F: '{print $NF}')"
  [ -n "$HOST_PORT" ] || die "could not resolve mapped host port for container"

  HEALTH_OK=false
  for _ in $(seq 1 30); do
    health_code=$(curl -s -o /tmp/pre-submit-health.out -w "%{http_code}" \
      "http://127.0.0.1:${HOST_PORT}/health" --max-time 3 || printf "000")
    if [ "$health_code" = "200" ]; then
      HEALTH_OK=true
      break
    fi
    sleep 1
  done
  [ "$HEALTH_OK" = true ] || {
    docker logs "$DOCKER_CONTAINER_ID" | tail -n 50
    die "container did not become healthy on /health"
  }

  reset_code=$(curl -s -o /tmp/pre-submit-reset.out -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" -d '{}' \
    "http://127.0.0.1:${HOST_PORT}/reset" --max-time 10 || printf "000")
  [ "$reset_code" = "200" ] || {
    docker logs "$DOCKER_CONTAINER_ID" | tail -n 50
    die "container /reset returned HTTP $reset_code"
  }

  pass "Containerized execution check passed (/health and /reset)"

  docker rm -f "$DOCKER_CONTAINER_ID" >/dev/null 2>&1 || true
  DOCKER_CONTAINER_ID=""
fi

log "Step 6/8: Environment variable checks"
if [ "$SKIP_INFERENCE" = true ]; then
  log "SKIPPED -- --skip-inference enabled"
else
  [ -n "${API_BASE_URL:-}" ] || die "API_BASE_URL is not set"
  [ -n "${MODEL_NAME:-}" ] || die "MODEL_NAME is not set"
  [ -n "${HF_TOKEN:-}" ] || die "HF_TOKEN is not set"
  pass "Required API_BASE_URL / MODEL_NAME / HF_TOKEN are set"
fi

log "Step 7/8: Baseline reproducibility (inference.py)"
if [ "$SKIP_INFERENCE" = true ]; then
  log "SKIPPED -- --skip-inference enabled"
else
  run_with_timeout "$INFERENCE_TIMEOUT" "$PYTHON_BIN" inference.py >"$INFERENCE_OUT_FILE" 2>&1 || {
    tail -n 80 "$INFERENCE_OUT_FILE"
    die "inference.py failed or timed out"
  }
  pass "inference.py completed within timeout"
fi

log "Step 8/8: Structured logs + task/grader checks"
if [ "$SKIP_INFERENCE" = true ]; then
  log "SKIPPED -- --skip-inference enabled"
else
  "$PYTHON_BIN" - "$INFERENCE_OUT_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8', errors='replace').splitlines()

starts = []
ends = []
step_count = 0

for line in text:
    line = line.strip()
    if line.startswith('[START] '):
        payload = json.loads(line[len('[START] '):])
        starts.append(payload)
    elif line.startswith('[STEP] '):
        json.loads(line[len('[STEP] '):])
        step_count += 1
    elif line.startswith('[END] '):
        payload = json.loads(line[len('[END] '):])
        ends.append(payload)

if len(starts) < 3:
    raise SystemExit('Expected at least 3 [START] task logs')

unique_tasks = {str(s.get('task', '')) for s in starts if s.get('task')}
if len(unique_tasks) < 3:
    raise SystemExit('Expected at least 3 unique tasks in [START] logs')

if len(ends) != len(starts):
    raise SystemExit('Mismatch between [START] and [END] log counts')

if step_count == 0:
    raise SystemExit('No [STEP] logs found')

for i, end in enumerate(ends, start=1):
    score = float(end.get('score', -1.0))
    rewards = end.get('rewards', [])
    if not (0.0 <= score <= 1.0):
        raise SystemExit(f'END #{i} score out of range [0,1]: {score}')
    if not isinstance(rewards, list):
        raise SystemExit(f'END #{i} rewards must be a list')
    for r in rewards:
        rv = float(r)
        if not (-1.0 <= rv <= 1.0):
            raise SystemExit(f'END #{i} step reward out of sanity range [-1,1]: {rv}')

print('Structured logs and task/grader checks passed')
PY
  pass "Structured [START]/[STEP]/[END] logs and score-range checks passed"
fi

log "All checks passed. Submission is ready."
