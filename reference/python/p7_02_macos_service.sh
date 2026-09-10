#!/bin/sh
set -eu

LABEL="com.arvectum.os.persistent-internal"
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd "$SCRIPT_DIR/../.." && pwd -P)
PYTHON_BIN=${PYTHON_BIN:-python3}
RUNTIME_ROOT=${ARVECTUM_P7_02_ROOT:-"$HOME/Library/Application Support/ArvectumOS/persistent-internal"}
LAUNCH_AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
SERVICE_TARGET="$DOMAIN/$LABEL"
SERVICE_WAIT_ATTEMPTS=${ARVECTUM_P7_02_SERVICE_WAIT_ATTEMPTS:-20}
SERVICE_WAIT_INTERVAL=${ARVECTUM_P7_02_SERVICE_WAIT_INTERVAL:-0.5}
CANONICAL_REPOSITORY="arvectum2/arvectum-os"

fail() { printf '%s\n' "P7.02 FAIL: $*" >&2; exit 1; }
info() { printf '%s\n' "P7.02: $*"; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "$1 is not available"; }

assert_macos() {
  [ "$(uname -s)" = "Darwin" ] || fail "macOS is required for the launchd adapter"
}

assert_outside_repo() {
  case "$RUNTIME_ROOT/" in
    "$REPO_ROOT"/*) fail "runtime root must remain outside the source checkout" ;;
  esac
}

assert_runtime_root_real_outside_repo() {
  runtime_real=$(CDPATH= cd "$RUNTIME_ROOT" && pwd -P)
  [ "$runtime_real" != "$REPO_ROOT" ] || fail "runtime root resolves to the source checkout"
  case "$runtime_real/" in
    "$REPO_ROOT"/*) fail "runtime root resolves inside the source checkout" ;;
  esac
}

assert_canonical_checkout() {
  require_cmd git
  git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not a Git worktree"
  origin=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)
  case "$origin" in
    "https://github.com/$CANONICAL_REPOSITORY"|"https://github.com/$CANONICAL_REPOSITORY.git"|https://*@github.com/"$CANONICAL_REPOSITORY"|https://*@github.com/"$CANONICAL_REPOSITORY".git|"git@github.com:$CANONICAL_REPOSITORY"|"git@github.com:$CANONICAL_REPOSITORY.git"|"ssh://git@github.com/$CANONICAL_REPOSITORY"|"ssh://git@github.com/$CANONICAL_REPOSITORY.git") ;;
    *) fail "origin is not canonical $CANONICAL_REPOSITORY: ${origin:-missing}" ;;
  esac
  branch=$(git -C "$REPO_ROOT" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
  [ "$branch" = "main" ] || fail "checkout must be canonical main (found ${branch:-detached})"
  [ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "working tree must be clean"
  git -C "$REPO_ROOT" fetch --prune origin main
  git -C "$REPO_ROOT" merge --ff-only origin/main >/dev/null
  HEAD_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD)
  ORIGIN_SHA=$(git -C "$REPO_ROOT" rev-parse origin/main)
  [ "$HEAD_SHA" = "$ORIGIN_SHA" ] || fail "local main does not equal origin/main"
}

current_release() {
  [ -L "$RUNTIME_ROOT/current" ] || fail "current release is not installed"
  basename "$(readlink "$RUNTIME_ROOT/current")"
}

current_runtime_script() {
  printf '%s/current/source/reference/python/p7_02_persistent_runtime.py\n' "$RUNTIME_ROOT"
}

current_python() {
  rel=$(current_release)
  printf '%s/venvs/%s/bin/python\n' "$RUNTIME_ROOT" "$rel"
}

replace_current_release() {
  prepared="$RUNTIME_ROOT/current.new"
  current="$RUNTIME_ROOT/current"
  "$PYTHON_BIN" - "$prepared" "$current" <<'PY'
import os
import stat
import sys

source, destination = sys.argv[1:]
if not os.path.islink(source):
    raise SystemExit("prepared current release pointer is not a symbolic link")
try:
    mode = os.lstat(destination).st_mode
except FileNotFoundError:
    pass
else:
    if not stat.S_ISLNK(mode):
        raise SystemExit("current release pointer exists and is not a symbolic link")
os.replace(source, destination)
PY
}

is_loaded() { launchctl print "$SERVICE_TARGET" >/dev/null 2>&1; }

service_pid() {
  launchctl print "$SERVICE_TARGET" 2>/dev/null | awk '/^[[:space:]]*pid = / {print $3; exit}'
}

wait_healthy() {
  rel=$(current_release)
  py=$(current_python)
  runtime=$(current_runtime_script)
  i=0
  while [ "$i" -lt 40 ]; do
    if "$py" "$runtime" check --runtime-root "$RUNTIME_ROOT" --expected-release "$rel" --max-age-seconds 20 >/dev/null 2>&1; then
      return 0
    fi
    i=$((i + 1))
    sleep 0.5
  done
  return 1
}

wait_unloaded() {
  i=0
  while is_loaded; do
    if [ "$i" -ge "$SERVICE_WAIT_ATTEMPTS" ]; then
      return 1
    fi
    i=$((i + 1))
    sleep "$SERVICE_WAIT_INTERVAL"
  done
  return 0
}

unload_service() {
  if ! is_loaded; then
    return 0
  fi
  if ! launchctl bootout "$SERVICE_TARGET" >/dev/null 2>&1; then
    if ! is_loaded; then
      return 0
    fi
    return 1
  fi
  wait_unloaded
}

prepare_release() {
  release="$RUNTIME_ROOT/releases/$HEAD_SHA"
  tmp="$RUNTIME_ROOT/releases/.verify-$HEAD_SHA-$$"
  rm -rf "$tmp"
  mkdir -p "$tmp"
  git -C "$REPO_ROOT" archive --format=tar --prefix=source/ "$HEAD_SHA" reference/python > "$tmp/reference-python.tar"
  archive_sha=$(shasum -a 256 "$tmp/reference-python.tar" | awk '{print $1}')
  tar -xf "$tmp/reference-python.tar" -C "$tmp"
  cat > "$tmp/release-manifest.json" <<EOF
{"canonical_repository":"$CANONICAL_REPOSITORY","release_sha":"$HEAD_SHA","reference_python_archive_sha256":"$archive_sha","runtime_classification":"Persistent Internal / owner-operated","network_listener_mode":"none"}
EOF

  if [ -e "$release" ]; then
    [ -d "$release/source/reference/python" ] || fail "existing release is incomplete: $release"
    [ -f "$release/reference-python.tar" ] || fail "existing release archive is missing: $release"
    [ -f "$release/release-manifest.json" ] || fail "existing release manifest is missing: $release"
    stored_archive_sha=$(shasum -a 256 "$release/reference-python.tar" | awk '{print $1}')
    [ "$stored_archive_sha" = "$archive_sha" ] || fail "existing release archive differs from canonical Git archive"
    cmp -s "$tmp/release-manifest.json" "$release/release-manifest.json" || fail "existing release manifest differs from canonical release pin"
    diff -qr "$tmp/source" "$release/source" >/dev/null || fail "existing runtime source differs from canonical release snapshot"
    rm -rf "$tmp"
    chmod -R a-w "$release/source" "$release/reference-python.tar" "$release/release-manifest.json"
    info "verified existing exact release $HEAD_SHA"
    return 0
  fi

  chmod -R a-w "$tmp/source" "$tmp/reference-python.tar" "$tmp/release-manifest.json"
  mv "$tmp" "$release"
  info "created exact release $HEAD_SHA"
}

write_plist() {
  rel=$1
  venv_python="$RUNTIME_ROOT/venvs/$rel/bin/python"
  runtime_script="$RUNTIME_ROOT/releases/$rel/source/reference/python/p7_02_persistent_runtime.py"
  generated="$RUNTIME_ROOT/service/$LABEL.plist"
  mkdir -p "$RUNTIME_ROOT/service" "$HOME/Library/LaunchAgents" "$RUNTIME_ROOT/logs"
  "$PYTHON_BIN" - "$generated" "$LABEL" "$venv_python" "$runtime_script" "$RUNTIME_ROOT" "$rel" "$RUNTIME_ROOT/logs/stdout.log" "$RUNTIME_ROOT/logs/stderr.log" <<'PY'
import plistlib, sys
path, label, py, runtime, root, release, out, err = sys.argv[1:]
payload = {
    "Label": label,
    "ProgramArguments": [py, runtime, "run", "--runtime-root", root, "--release-sha", release, "--heartbeat-seconds", "5"],
    "RunAtLoad": True,
    "KeepAlive": {"SuccessfulExit": False},
    "ThrottleInterval": 5,
    "ProcessType": "Background",
    "StandardOutPath": out,
    "StandardErrorPath": err,
    "EnvironmentVariables": {"PYTHONDONTWRITEBYTECODE": "1"},
}
with open(path, "wb") as handle:
    plistlib.dump(payload, handle, sort_keys=True)
PY
  chmod 600 "$generated"
  plutil -lint "$generated" >/dev/null
  cp "$generated" "$LAUNCH_AGENT"
  chmod 600 "$LAUNCH_AGENT"
}

install_runtime() {
  assert_macos
  assert_outside_repo
  require_cmd "$PYTHON_BIN"
  require_cmd launchctl
  require_cmd plutil
  require_cmd tar
  require_cmd shasum
  require_cmd cmp
  require_cmd diff
  assert_canonical_checkout

  mkdir -p "$RUNTIME_ROOT"
  assert_runtime_root_real_outside_repo
  mkdir -p "$RUNTIME_ROOT/releases" "$RUNTIME_ROOT/venvs" "$RUNTIME_ROOT/run" "$RUNTIME_ROOT/logs" "$RUNTIME_ROOT/evidence" "$RUNTIME_ROOT/config" "$RUNTIME_ROOT/secrets" "$RUNTIME_ROOT/service"
  chmod 700 "$RUNTIME_ROOT" "$RUNTIME_ROOT/run" "$RUNTIME_ROOT/config" "$RUNTIME_ROOT/secrets" "$RUNTIME_ROOT/evidence"

  prepare_release

  venv="$RUNTIME_ROOT/venvs/$HEAD_SHA"
  if [ ! -x "$venv/bin/python" ]; then
    "$PYTHON_BIN" -m venv "$venv"
  fi

  config="$RUNTIME_ROOT/config/p7-02.json"
  if [ ! -f "$config" ]; then
    cat > "$config" <<'EOF'
{
  "classification": "owner-local runtime configuration; non-secret",
  "operating_mode": "Persistent Internal / owner-operated",
  "organization_scope": "ООО «Арвектум»",
  "operating_role": "Arvectum OS Owner-Operator",
  "reusable_secrets_required_for_p7_02": false,
  "network_listener_mode": "none"
}
EOF
    chmod 600 "$config"
  fi

  rm -f "$RUNTIME_ROOT/current.new"
  ln -s "$release" "$RUNTIME_ROOT/current.new"
  replace_current_release
  [ "$(current_release)" = "$HEAD_SHA" ] || fail "current release pointer did not switch to exact target"
  write_plist "$HEAD_SHA"

  if is_loaded; then
    unload_service || fail "existing service did not unload before install"
  fi
  launchctl enable "$SERVICE_TARGET" >/dev/null 2>&1 || true
  launchctl bootstrap "$DOMAIN" "$LAUNCH_AGENT"
  wait_healthy || fail "runtime did not become healthy after install"
  info "install PASS release=$HEAD_SHA"
  status_runtime
}

start_runtime() {
  assert_macos
  [ -f "$LAUNCH_AGENT" ] || fail "LaunchAgent not installed; run install"
  launchctl enable "$SERVICE_TARGET" >/dev/null 2>&1 || true
  if ! is_loaded; then
    launchctl bootstrap "$DOMAIN" "$LAUNCH_AGENT"
  fi
  launchctl kickstart "$SERVICE_TARGET" >/dev/null
  wait_healthy || fail "runtime did not become healthy"
  info "start PASS"
}

stop_runtime() {
  assert_macos
  unload_service || fail "service remains loaded after bounded stop wait"
  info "stop PASS"
}

restart_runtime() {
  assert_macos
  launchctl enable "$SERVICE_TARGET" >/dev/null 2>&1 || true
  if is_loaded; then
    launchctl kickstart -k "$SERVICE_TARGET"
  else
    launchctl bootstrap "$DOMAIN" "$LAUNCH_AGENT"
    launchctl kickstart "$SERVICE_TARGET"
  fi
  wait_healthy || fail "runtime did not become healthy after restart"
  info "restart PASS"
}

status_runtime() {
  assert_macos
  rel=$(current_release)
  if ! is_loaded; then
    fail "service is not loaded"
  fi
  py=$(current_python)
  runtime=$(current_runtime_script)
  "$py" "$runtime" check --runtime-root "$RUNTIME_ROOT" --expected-release "$rel" --max-age-seconds 20
  pid=$(service_pid)
  [ -n "$pid" ] || fail "launchd did not report a pid"
  info "service loaded target=$SERVICE_TARGET pid=$pid release=$rel"
}

assert_no_network_listener() {
  pid=$1
  require_cmd lsof
  sockets=$(lsof -a -p "$pid" -i -n -P 2>/dev/null | sed '1d' || true)
  [ -z "$sockets" ] || fail "runtime process owns network sockets: $sockets"
}

crash_proof() {
  assert_macos
  status_runtime >/dev/null
  rel=$(current_release)
  py=$(current_python)
  runtime=$(current_runtime_script)
  before_json=$($py "$runtime" check --runtime-root "$RUNTIME_ROOT" --expected-release "$rel" --max-age-seconds 20 --json)
  before_pid=$(printf '%s' "$before_json" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["pid"])')
  before_gen=$(printf '%s' "$before_json" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["generation"])')
  kill -9 "$before_pid"

  i=0
  new_pid=""
  while [ "$i" -lt 40 ]; do
    sleep 0.5
    new_pid=$(service_pid || true)
    if [ -n "$new_pid" ] && [ "$new_pid" != "$before_pid" ] && wait_healthy; then
      break
    fi
    i=$((i + 1))
  done
  [ -n "$new_pid" ] && [ "$new_pid" != "$before_pid" ] || fail "launchd did not replace crashed process"
  after_json=$($py "$runtime" check --runtime-root "$RUNTIME_ROOT" --expected-release "$rel" --max-age-seconds 20 --json)
  after_gen=$(printf '%s' "$after_json" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["generation"])')
  [ "$after_gen" -gt "$before_gen" ] || fail "health generation did not advance after crash"
  assert_no_network_listener "$new_pid"

  stamp=$(date -u '+%Y%m%dT%H%M%SZ')
  evidence="$RUNTIME_ROOT/evidence/p7-02-crash-$stamp.json"
  "$PYTHON_BIN" - "$evidence" "$rel" "$before_pid" "$new_pid" "$before_gen" "$after_gen" <<'PY'
import json, sys
from datetime import datetime, timezone
path, release, before_pid, after_pid, before_gen, after_gen = sys.argv[1:]
payload = {
    "schema": "arvectum.p7_02.crash-restart-proof/1",
    "classification": "local operational evidence; non-canonical telemetry",
    "release_sha": release,
    "crashed_pid": int(before_pid),
    "replacement_pid": int(after_pid),
    "generation_before": int(before_gen),
    "generation_after": int(after_gen),
    "launchd_restart_observed": True,
    "network_listener_exposure": "none observed",
    "product_effect_replay": False,
    "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
    handle.write("\n")
PY
  chmod 600 "$evidence"
  info "crash/restart PASS evidence=$evidence"
}

prove_runtime() {
  assert_macos
  assert_outside_repo
  assert_runtime_root_real_outside_repo
  rel=$(current_release)
  info "proving predictable stop/start"
  stop_runtime
  start_runtime
  first_pid=$(service_pid)
  info "proving explicit restart"
  restart_runtime
  second_pid=$(service_pid)
  [ -n "$first_pid" ] && [ -n "$second_pid" ] && [ "$first_pid" != "$second_pid" ] || fail "restart did not replace process"
  assert_no_network_listener "$second_pid"
  info "proving launchd crash recovery"
  crash_proof
  plutil -extract RunAtLoad raw -o - "$LAUNCH_AGENT" | grep -qx true || fail "RunAtLoad is not true"
  plutil -extract KeepAlive.SuccessfulExit raw -o - "$LAUNCH_AGENT" | grep -qx false || fail "KeepAlive.SuccessfulExit is not false"
  [ "$(stat -f '%Lp' "$LAUNCH_AGENT")" = "600" ] || fail "LaunchAgent permissions are not 600"
  [ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "source checkout became dirty"
  status_runtime
  stamp=$(date -u '+%Y%m%dT%H%M%SZ')
  summary="$RUNTIME_ROOT/evidence/p7-02-summary-$stamp.txt"
  cat > "$summary" <<EOF
p7_02_local_proof=PASS
operating_mode=Persistent Internal / owner-operated
canonical_repository=$CANONICAL_REPOSITORY
release_sha=$rel
service_manager=launchd LaunchAgent; reversible environment-specific adapter
service_label=$LABEL
boot_login_lifecycle=RunAtLoad at owner login
supervision=KeepAlive on unsuccessful exit; ThrottleInterval=5
network_listener_exposure=none observed
runtime_root=$RUNTIME_ROOT
source_checkout=$REPO_ROOT
source_checkout_dirty=false
reusable_secrets_required_for_p7_02=false
product_effects_enabled=false
canonical_state_written_by_runtime_envelope=false
EOF
  chmod 600 "$summary"
  info "full local proof PASS evidence=$summary"
}

remove_service() {
  assert_macos
  unload_service || fail "service remains loaded during remove"
  rm -f "$LAUNCH_AGENT" "$RUNTIME_ROOT/service/$LABEL.plist"
  info "service removed; releases/config/secrets/evidence retained at $RUNTIME_ROOT"
}

usage() {
  cat <<EOF
Usage: $0 install|start|stop|restart|status|crash-proof|prove|remove

install      pin canonical main into an exact verified runtime release and install owner LaunchAgent
start        load/start the LaunchAgent
stop         unload/stop the LaunchAgent with bounded asynchronous-unload wait
restart      replace the supervised process
status       check launchd state and fresh local health telemetry
crash-proof  SIGKILL the runtime and prove launchd replacement + no network sockets
prove        prove stop/start/restart/crash recovery/listener/source-separation requirements
remove       remove the service adapter while retaining local releases/config/secrets/evidence
EOF
}

case "${1:-}" in
  install) install_runtime ;;
  start) start_runtime ;;
  stop) stop_runtime ;;
  restart) restart_runtime ;;
  status) status_runtime ;;
  crash-proof) crash_proof ;;
  prove) prove_runtime ;;
  remove) remove_service ;;
  *) usage; exit 2 ;;
esac
