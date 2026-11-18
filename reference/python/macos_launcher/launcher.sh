#!/bin/sh
set -eu

# Arvectum OS — macOS Desktop Workspace Launcher
#
# Thin UX wrapper over the canonical P7.02/P7.06 runtime/service path.
# This script is compiled into ~/Desktop/Arvectum OS.app by the installer.
# It must NOT perform git operations, updates, dependency installs, or
# create alternative runtime controllers.
#
# Finder-launched processes have a minimal environment. All paths below
# are absolute or resolved from known canonical locations.

APPLESCRIPT=/usr/bin/osascript
OPEN=/usr/bin/open
LAUNCHCTL=/bin/launchctl
RUNTIME_ROOT="${ARVECTUM_P7_02_ROOT:-$HOME/Library/Application Support/ArvectumOS/persistent-internal}"
LABEL="com.arvectum.os.persistent-internal"
WORKSPACE_URL="http://127.0.0.1:8769"
HEALTH_TIMEOUT_SECONDS=30
HEALTH_POLL_INTERVAL=2

LOCK_DIR="$RUNTIME_ROOT/run/desktop-launcher.lock"
DEPLOY_LOCK="$RUNTIME_ROOT/run/p7-06-deploy.lock"
DEPLOY_LOCK_OWNED=false
LAUNCHER_LOG="$RUNTIME_ROOT/logs/desktop-launcher.log"

mkdir -p "$RUNTIME_ROOT/logs" 2>/dev/null || true

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$LAUNCHER_LOG" 2>/dev/null || true
}

fail_with_dialog() {
  local message="$1"
  local log_path="${2:-$LAUNCHER_LOG}"
  log "FAIL: $message"
  if [ -t 2 ]; then
    printf '%s\n' "Arvectum OS: $message" >&2
    printf '%s\n' "Log: $log_path" >&2
  else
    "$APPLESCRIPT" -e "
      display dialog \"Arvectum OS failed to start.\" & return & return & \"$message\" & return & return & \"Log: $log_path\" buttons {\"OK\" default button \"OK\" with icon stop with title \"Arvectum OS\"
    " 2>/dev/null || printf '%s\n' "Arvectum OS: $message" >&2
  fi
  exit 1
}

acquire_lock() {
  mkdir -p "$RUNTIME_ROOT/run" 2>/dev/null || true
  chmod 700 "$RUNTIME_ROOT/run" 2>/dev/null || true

  if [ -d "$LOCK_DIR" ]; then
    local lock_pid=""
    if [ -f "$LOCK_DIR/pid" ]; then
      lock_pid=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    fi
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
      log "Another launcher active (pid=$lock_pid); waiting for readiness"
      wait_for_readiness || fail_with_dialog "Another instance is starting the Workspace but it did not become ready within $HEALTH_TIMEOUT_SECONDS seconds."
      open_browser
      exit 0
    fi
    local lock_age=0
    if [ -f "$LOCK_DIR/created" ]; then
      local created
      created=$(cat "$LOCK_DIR/created" 2>/dev/null || echo 0)
      local now
      now=$(date +%s)
      lock_age=$((now - created))
    fi
    if [ "$lock_age" -gt 120 ]; then
      log "Removing stale lock (age=${lock_age}s)"
      rm -rf "$LOCK_DIR"
    else
      if is_workspace_running; then
        log "Workspace already running (another launcher active); opening browser"
        open_browser
        exit 0
      fi
      log "Another launcher active (stale but recent); waiting for readiness"
      wait_for_readiness || fail_with_dialog "Another instance is starting the Workspace but it did not become ready within $HEALTH_TIMEOUT_SECONDS seconds."
      open_browser
      exit 0
    fi
  fi

  mkdir "$LOCK_DIR" 2>/dev/null || {
    if is_workspace_running; then
      log "Workspace already running; opening browser"
      open_browser
      exit 0
    fi
    log "Lock held but workspace not yet responding; waiting for readiness"
    if wait_for_readiness; then
      open_browser
      exit 0
    fi
    fail_with_dialog "Could not acquire launcher lock and workspace did not become ready."
  }
  echo $$ > "$LOCK_DIR/pid"
  date +%s > "$LOCK_DIR/created"
  chmod 600 "$LOCK_DIR/pid" "$LOCK_DIR/created"
}

release_deploy_lock() {
  if [ "$DEPLOY_LOCK_OWNED" = true ] && [ "$(cat "$DEPLOY_LOCK/pid" 2>/dev/null || true)" = "$$" ]; then
    rm -f "$DEPLOY_LOCK/pid"
    rmdir "$DEPLOY_LOCK"
    DEPLOY_LOCK_OWNED=false
  fi
}
release_lock() {
  release_deploy_lock
  rm -rf "$LOCK_DIR" 2>/dev/null || true
}

is_workspace_running() {
  [ "$(workspace_state 2>/dev/null || true)" = "CURRENT_EXACT" ]
}

workspace_state() {
  local release helper python
  [ -L "$RUNTIME_ROOT/current" ] || return 1
  release=$(basename "$(readlink "$RUNTIME_ROOT/current")")
  helper="$RUNTIME_ROOT/current/source/reference/python/p9_11_workspace_process.py"
  python="$RUNTIME_ROOT/venvs/$release/bin/python"
  [ -x "$python" ] && [ -f "$helper" ] || return 1
  "$python" "$helper" status --runtime-root "$RUNTIME_ROOT" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])'
}

wait_for_readiness() {
  local elapsed=0
  while [ "$elapsed" -lt "$HEALTH_TIMEOUT_SECONDS" ]; do
    if is_workspace_running; then
      return 0
    fi
    sleep "$HEALTH_POLL_INTERVAL"
    elapsed=$((elapsed + HEALTH_POLL_INTERVAL))
  done
  return 1
}

start_workspace() {
  log "Workspace not running; starting exact current release"
  (umask 077; mkdir "$DEPLOY_LOCK") || fail_with_dialog "Workspace update or another lifecycle operation is active."
  DEPLOY_LOCK_OWNED=true
  (umask 077; printf '%s\n' "$$" > "$DEPLOY_LOCK/pid")

  local target="gui/$(id -u)/$LABEL"
  local plist="$HOME/Library/LaunchAgents/$LABEL.plist"

  if [ ! -f "$plist" ]; then
    fail_with_dialog "Arvectum OS runtime is not installed." "Run the one-time install: sh reference/python/p7_02_macos_service.sh install"
  fi

  "$LAUNCHCTL" enable "$target" 2>/dev/null || true

  if ! "$LAUNCHCTL" print "$target" >/dev/null 2>&1; then
    "$LAUNCHCTL" bootstrap "$target" "$plist" 2>/dev/null || true
  fi

  "$LAUNCHCTL" kickstart "$target" >/dev/null 2>&1 || true

  local state
  state=$(workspace_state 2>/dev/null || true)
  if [ -n "$state" ] && [ "$state" != "NOT_RUNNING" ]; then
    fail_with_dialog "Workspace listener is $state and was not modified. Use P7.06 update or investigate the listener."
  fi
  local release helper python
  release=$(basename "$(readlink "$RUNTIME_ROOT/current")")
  helper="$RUNTIME_ROOT/current/source/reference/python/p9_11_workspace_process.py"
  python="$RUNTIME_ROOT/venvs/$release/bin/python"
  "$python" "$helper" start --runtime-root "$RUNTIME_ROOT" >> "$LAUNCHER_LOG" 2>&1 || fail_with_dialog "Current exact Workspace process could not be started. Check logs for details."

  log "Waiting for Workspace readiness (timeout=${HEALTH_TIMEOUT_SECONDS}s)"
  if ! wait_for_readiness; then
    fail_with_dialog "Workspace did not become ready within $HEALTH_TIMEOUT_SECONDS seconds. Check logs for details."
  fi
  release_deploy_lock
  log "Workspace is ready"
}

open_browser() {
  log "Opening $WORKSPACE_URL"
  "$OPEN" "$WORKSPACE_URL"
}

main() {
  log "Launcher invoked"
  acquire_lock

  trap 'release_lock' EXIT HUP INT TERM

  if is_workspace_running; then
    log "Workspace already running"
    open_browser
  else
    start_workspace
    open_browser
  fi

  log "Launcher complete"
  release_lock
  trap - EXIT HUP INT TERM
}

main "$@"
