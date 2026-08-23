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
CURL=/usr/bin/curl
LAUNCHCTL=/bin/launchctl
RUNTIME_ROOT="${ARVECTUM_P7_02_ROOT:-$HOME/Library/Application Support/ArvectumOS/persistent-internal}"
LABEL="com.arvectum.os.persistent-internal"
WORKSPACE_URL="http://127.0.0.1:8769"
HEALTH_TIMEOUT_SECONDS=30
HEALTH_POLL_INTERVAL=2

LOCK_DIR="$RUNTIME_ROOT/run/desktop-launcher.lock"
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

release_lock() {
  rm -rf "$LOCK_DIR" 2>/dev/null || true
}

is_workspace_running() {
  local target="gui/$(id -u)/$LABEL"
  if ! "$LAUNCHCTL" print "$target" >/dev/null 2>&1; then
    return 1
  fi
  local pid
  pid=$("$LAUNCHCTL" print "$target" 2>/dev/null | awk '/^[[:space:]]*pid = / {print $3; exit}')
  if [ -z "$pid" ]; then
    return 1
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    return 1
  fi
  local http_code
  http_code=$("$CURL" -s -o /dev/null -w "%{http_code}" --max-time 3 "$WORKSPACE_URL/" 2>/dev/null || echo "000")
  [ "$http_code" = "200" ]
}

wait_for_readiness() {
  local elapsed=0
  while [ "$elapsed" -lt "$HEALTH_TIMEOUT_SECONDS" ]; do
    local http_code
    http_code=$("$CURL" -s -o /dev/null -w "%{http_code}" --max-time 3 "$WORKSPACE_URL/" 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
      return 0
    fi
    sleep "$HEALTH_POLL_INTERVAL"
    elapsed=$((elapsed + HEALTH_POLL_INTERVAL))
  done
  return 1
}

start_workspace() {
  log "Workspace not running; starting via P7.02"

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

  log "Waiting for Workspace readiness (timeout=${HEALTH_TIMEOUT_SECONDS}s)"
  if ! wait_for_readiness; then
    fail_with_dialog "Workspace did not become ready within $HEALTH_TIMEOUT_SECONDS seconds. Check logs for details."
  fi
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
