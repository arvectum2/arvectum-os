#!/bin/sh
set -eu

RUNTIME_ROOT=${ARVECTUM_P7_02_ROOT:-"$HOME/Library/Application Support/ArvectumOS/persistent-internal"}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
P702="$SCRIPT_DIR/p7_02_macos_service.sh"
P705="$SCRIPT_DIR/p7_05_macos_observer.sh"
P706="$SCRIPT_DIR/p7_06_governed_deploy.py"
P911="$SCRIPT_DIR/p9_11_workspace_process.py"
RUNTIME_LABEL="com.arvectum.os.persistent-internal"
OBSERVER_LABEL="com.arvectum.os.p7-05-observer"
DOMAIN="gui/$(id -u)"
RUNTIME_TARGET="$DOMAIN/$RUNTIME_LABEL"
OBSERVER_TARGET="$DOMAIN/$OBSERVER_LABEL"
RUNTIME_PLIST="$HOME/Library/LaunchAgents/$RUNTIME_LABEL.plist"
OBSERVER_PLIST="$HOME/Library/LaunchAgents/$OBSERVER_LABEL.plist"
LOCK_DIR="$RUNTIME_ROOT/run/p7-06-deploy.lock"
R22_SHA="950a5a8e0258dd555db4a97e5622d64951bcf6fe"
P705_LEGACY_PROVEN_SHA="cf60e52c93bf0ef4158cf2c3e26792850a126c70"
CANONICAL_REPOSITORY="arvectum2/arvectum-os"
QUIESCE_WAIT_ATTEMPTS=${ARVECTUM_P7_06_QUIESCE_WAIT_ATTEMPTS:-30}
QUIESCE_WAIT_INTERVAL=${ARVECTUM_P7_06_QUIESCE_WAIT_INTERVAL:-0.5}

fail() { printf '%s\n' "P7.06 deploy FAIL: $*" >&2; exit 1; }
info() { printf '%s\n' "P7.06 deploy: $*"; }
assert_macos() { [ "$(uname -s)" = "Darwin" ] || fail "macOS is required for the selected-Mac adapter"; }

assert_canonical_checkout() {
  git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "source is not a Git checkout"
  [ "$(git -C "$REPO_ROOT" branch --show-current)" = "main" ] || fail "canonical checkout must be on main"
  origin=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)
  case "$origin" in
    "https://github.com/$CANONICAL_REPOSITORY"|"https://github.com/$CANONICAL_REPOSITORY.git"|https://*@github.com/"$CANONICAL_REPOSITORY"|https://*@github.com/"$CANONICAL_REPOSITORY".git|"git@github.com:$CANONICAL_REPOSITORY"|"git@github.com:$CANONICAL_REPOSITORY.git"|"ssh://git@github.com/$CANONICAL_REPOSITORY"|"ssh://git@github.com/$CANONICAL_REPOSITORY.git") ;;
    *) fail "origin is not canonical $CANONICAL_REPOSITORY: $origin" ;;
  esac
  [ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "canonical checkout must be clean"
  git -C "$REPO_ROOT" fetch --quiet origin main
  git -C "$REPO_ROOT" merge --ff-only --quiet origin/main
  head=$(git -C "$REPO_ROOT" rev-parse HEAD)
  [ "$head" = "$(git -C "$REPO_ROOT" rev-parse origin/main)" ] || fail "local main must equal origin/main"
  git -C "$REPO_ROOT" merge-base --is-ancestor "$R22_SHA" "$head" || fail "target release must include merged R22 hardening"
  printf '%s\n' "$head"
}

ensure_workspace_runtime_dependencies() {
  release=$1
  venv=$2
  lock="$release/source/reference/python/workspace_app/requirements.lock"

  # Pre-P9 releases legitimately have no Workspace lock.
  [ -f "$lock" ] || return 0

  stamp="$venv/.workspace-requirements.sha256"
  lock_sha=$(shasum -a 256 "$lock" | awk '{print $1}')
  installed_sha=""

  if [ -f "$stamp" ]; then
    installed_sha=$(cat "$stamp")
  fi

  if [ "$installed_sha" != "$lock_sha" ]; then
    "$venv/bin/python" -m pip install \
      --disable-pip-version-check \
      -r "$lock" >/dev/null \
      || fail "workspace runtime dependency install failed for exact target release"

    tmp_stamp="$stamp.tmp.$$"
    printf '%s\n' "$lock_sha" > "$tmp_stamp"
    chmod 600 "$tmp_stamp"
    mv "$tmp_stamp" "$stamp"
  fi

  "$venv/bin/python" - <<'PY' >/dev/null 2>&1 \
    || fail "workspace runtime dependency verification failed for exact target release"
import fastapi
import uvicorn
PY
}

prepare_target() {
  target=$1
  release="$RUNTIME_ROOT/releases/$target"
  tmp="$RUNTIME_ROOT/releases/.p7-06-verify-$target-$$"
  mkdir -p "$RUNTIME_ROOT/releases" "$RUNTIME_ROOT/venvs"
  rm -rf "$tmp"; mkdir -p "$tmp"
  git -C "$REPO_ROOT" archive --format=tar --prefix=source/ "$target" reference/python > "$tmp/reference-python.tar"
  archive_sha=$(shasum -a 256 "$tmp/reference-python.tar" | awk '{print $1}')
  tar -xf "$tmp/reference-python.tar" -C "$tmp"
  cat > "$tmp/release-manifest.json" <<EOF
{"canonical_repository":"$CANONICAL_REPOSITORY","release_sha":"$target","reference_python_archive_sha256":"$archive_sha","runtime_classification":"Persistent Internal / owner-operated","network_listener_mode":"none"}
EOF
  if [ -e "$release" ]; then
    [ -d "$release/source/reference/python" ] || fail "existing target release is incomplete"
    stored=$(shasum -a 256 "$release/reference-python.tar" | awk '{print $1}')
    [ "$stored" = "$archive_sha" ] || fail "existing target release archive differs from canonical Git archive"
    cmp -s "$tmp/release-manifest.json" "$release/release-manifest.json" || fail "existing target release manifest mismatch"
    diff -qr "$tmp/source" "$release/source" >/dev/null || fail "existing target release source mismatch"
    rm -rf "$tmp"
  else
    chmod -R a-w "$tmp/source" "$tmp/reference-python.tar" "$tmp/release-manifest.json"
    mv "$tmp" "$release"
  fi
  venv="$RUNTIME_ROOT/venvs/$target"
  if [ ! -x "$venv/bin/python" ]; then python3 -m venv "$venv"; fi
  ensure_workspace_runtime_dependencies "$release" "$venv"
}

current_release() {
  [ -L "$RUNTIME_ROOT/current" ] || fail "current release symlink is missing"
  basename "$(readlink "$RUNTIME_ROOT/current")"
}

release_python() { printf '%s/venvs/%s/bin/python\n' "$RUNTIME_ROOT" "$1"; }
release_source() { printf '%s/releases/%s/source/reference/python\n' "$RUNTIME_ROOT" "$1"; }

workspace_status() { python3 "$P911" status --runtime-root "$RUNTIME_ROOT"; }
workspace_start() { python3 "$P911" start --runtime-root "$RUNTIME_ROOT"; }
workspace_stop_for_update() { python3 "$P911" stop-for-update --runtime-root "$RUNTIME_ROOT"; }
workspace_state() { printf '%s' "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])'; }

acquire_lock() {
  mkdir -p "$RUNTIME_ROOT/run"
  chmod 700 "$RUNTIME_ROOT/run"
  mkdir "$LOCK_DIR" 2>/dev/null || fail "another P7.06 deployment transaction is active"
  printf '%s\n' "$$" > "$LOCK_DIR/pid"
  chmod 600 "$LOCK_DIR/pid"
}
release_lock() { rm -rf "$LOCK_DIR"; }

wait_loaded() {
  wait_target=$1
  i=0
  while [ "$i" -lt 30 ]; do
    launchctl print "$wait_target" >/dev/null 2>&1 && return 0
    i=$((i + 1)); sleep 0.5
  done
  return 1
}

runtime_lock_available() {
  lock="$RUNTIME_ROOT/run/runtime.lock"
  [ -e "$lock" ] || return 0
  python3 - "$lock" <<'PY'
import fcntl
import sys

path = sys.argv[1]
try:
    handle = open(path, "r+", encoding="utf-8")
except FileNotFoundError:
    raise SystemExit(0)
except OSError:
    raise SystemExit(2)
try:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(1)
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
finally:
    handle.close()
PY
}

wait_runtime_quiescent() {
  i=0
  while [ "$i" -lt "$QUIESCE_WAIT_ATTEMPTS" ]; do
    if runtime_lock_available; then
      return 0
    fi
    i=$((i + 1))
    sleep "$QUIESCE_WAIT_INTERVAL"
  done
  runtime_lock_available
}

verify_source_observer_preupdate() {
  rel=$1
  if sh "$P705" status >/dev/null 2>&1; then
    info "source observer exact-release status PASS release=$rel"
    return 0
  fi

  [ "$rel" = "$P705_LEGACY_PROVEN_SHA" ] || fail "source observer exact-release verification failed outside the one admitted pre-R22 release"
  launchctl print "$OBSERVER_TARGET" >/dev/null 2>&1 || fail "admitted pre-R22 observer is not loaded"
  [ -f "$OBSERVER_PLIST" ] || fail "admitted pre-R22 observer plist is missing"
  py=$(release_python "$rel")
  legacy_script="$RUNTIME_ROOT/current/source/reference/python/p7_05_operational_visibility.py"
  [ -x "$py" ] || fail "admitted pre-R22 observer Python is missing"
  [ -f "$legacy_script" ] || fail "admitted pre-R22 observer script is missing"

  python3 - "$OBSERVER_PLIST" "$py" "$legacy_script" "$RUNTIME_ROOT" <<'PY'
import plistlib
import sys

path, expected_python, expected_script, root = sys.argv[1:]
with open(path, "rb") as handle:
    payload = plistlib.load(handle)
expected = [
    expected_python,
    expected_script,
    "observe",
    "--runtime-root",
    root,
    "--max-age-seconds",
    "20",
]
if payload.get("ProgramArguments") != expected:
    raise SystemExit("pre-R22 observer plist does not match the exact historically proven P7.05 shape")
PY

  "$py" "$legacy_script" status --runtime-root "$RUNTIME_ROOT" --max-age-seconds 20 >/dev/null
  info "source observer legacy R22 carry-forward status PASS release=$rel"
}

restore_plist_and_start() {
  txdir=$1
  rel=$2
  old_runtime="$txdir/pre-runtime.plist"
  old_observer="$txdir/pre-observer.plist"
  [ -f "$old_runtime" ] || fail "rollback runtime plist evidence missing"
  [ -f "$old_observer" ] || fail "rollback observer plist evidence missing"
  [ -d "$RUNTIME_ROOT/releases/$rel" ] || fail "rollback release is no longer installed: $rel"
  [ -x "$(release_python "$rel")" ] || fail "rollback release Python missing"

  workspace=$(workspace_status) || fail "rollback Workspace listener classification failed"
  case "$(workspace_state "$workspace")" in
    NOT_RUNNING) ;;
    CURRENT_EXACT|STALE_KNOWN_EXACT) workspace_stop_for_update >/dev/null || fail "rollback known Workspace listener did not stop" ;;
    UNKNOWN) fail "rollback refused: Workspace listener is UNKNOWN" ;;
  esac

  sh "$P705" uninstall >/dev/null || fail "rollback observer did not unload within bounded wait"
  sh "$P702" stop >/dev/null || fail "rollback runtime launchd target did not unload within bounded wait"
  wait_runtime_quiescent || fail "rollback runtime process did not release the single-instance lock"

  rm -f "$RUNTIME_ROOT/current"
  ln -s "$RUNTIME_ROOT/releases/$rel" "$RUNTIME_ROOT/current"

  mkdir -p "$HOME/Library/LaunchAgents" "$RUNTIME_ROOT/service"
  cp "$old_runtime" "$RUNTIME_PLIST"
  cp "$old_runtime" "$RUNTIME_ROOT/service/$RUNTIME_LABEL.plist"
  chmod 600 "$RUNTIME_PLIST" "$RUNTIME_ROOT/service/$RUNTIME_LABEL.plist"
  launchctl bootstrap "$DOMAIN" "$RUNTIME_PLIST"
  launchctl kickstart "$RUNTIME_TARGET" >/dev/null 2>&1
  wait_loaded "$RUNTIME_TARGET" || fail "rollback runtime did not load"
  py=$(release_python "$rel")
  runtime="$(release_source "$rel")/p7_02_persistent_runtime.py"
  i=0
  until "$py" "$runtime" check --runtime-root "$RUNTIME_ROOT" --expected-release "$rel" --max-age-seconds 20 >/dev/null 2>&1; do
    [ "$i" -lt 30 ] || fail "rollback runtime did not become healthy"
    i=$((i + 1)); sleep 0.5
  done

  rm -f "$OBSERVER_PLIST"
  if ! sh "$P705" install >/dev/null; then fail "rollback observer exact-release re-pin failed"; fi
  if ! sh "$P705" status >/dev/null; then fail "rollback observer exact-release verification failed"; fi
  if [ "${workspace_was_running:-false}" = "true" ]; then
    workspace_start >/dev/null || fail "rollback Workspace exact-source restart failed"
  fi
}

backup_preupdate() {
  rel=$1
  py=$(release_python "$rel")
  durable="$(release_source "$rel")/p7_03_durable_state.py"
  "$py" "$durable" verify --runtime-root "$RUNTIME_ROOT" >/dev/null
  output=$("$py" "$durable" backup --runtime-root "$RUNTIME_ROOT" --release-sha "$rel")
  backup=$(printf '%s\n' "$output" | sed -n 's/^P7.03 backup PASS archive=\(.*\) sha256=[0-9a-f][0-9a-f]*$/\1/p')
  sha=$(printf '%s\n' "$output" | sed -n 's/^P7.03 backup PASS archive=.* sha256=\([0-9a-f][0-9a-f]*\)$/\1/p')
  [ -n "$backup" ] && [ -n "$sha" ] || fail "could not parse exact pre-update backup identity"
  "$py" "$durable" verify-backup --archive "$backup" >/dev/null
  [ "$(awk '{print $1}' "$backup.sha256")" = "$sha" ] || fail "backup checksum sidecar does not match backup result"
  printf '%s|%s\n' "$backup" "$sha"
}

write_payload() {
  path=$1; plan_id=$2; source=$3; target=$4; result=$5; backup=$6; backup_sha=$7; runtime_ok=$8; observer_ok=$9; rollback=${10}; workspace=${11}
  python3 - "$path" "$plan_id" "$source" "$target" "$result" "$backup" "$backup_sha" "$runtime_ok" "$observer_ok" "$rollback" "$workspace" <<'PY'
import json, sys
path, plan_id, source, target, result, backup, backup_sha, runtime_ok, observer_ok, rollback, workspace = sys.argv[1:]
payload = {
    "plan_id": plan_id,
    "source_release": source,
    "target_release": target,
    "result": result,
    "backup_path": backup,
    "backup_sha256": backup_sha,
    "runtime_release_verified": runtime_ok == "true",
    "observer_release_verified": observer_ok == "true",
    "workspace_listener_disposition": workspace,
    "rollback_disposition": rollback,
    "canonical_mutation_performed_by_deploy": False,
    "product_external_effect_invoked": False,
    "historical_effect_replay_invoked": False,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2); handle.write("\n")
PY
  chmod 600 "$path"
}

rollback_and_record_failure() {
  reason=$1
  restore_plist_and_start "$txdir" "$source"
  payload="$txdir/failure-rollback-$(date -u '+%Y%m%dT%H%M%SZ').json"
  write_payload "$payload" "$plan_id" "$source" "$target" ROLLED_BACK "$backup" "$backup_sha" true true "executed after failed update: $reason; exact source release restored; backup retained and not replayed" "$workspace_disposition"
  tx=$(python3 "$P706" record --runtime-root "$RUNTIME_ROOT" --payload "$payload" --json || true)
  if [ -n "$tx" ]; then
    txid=$(printf '%s' "$tx" | python3 -c 'import json,sys; print(json.load(sys.stdin)["transaction_id"])' 2>/dev/null || true)
    info "failed update rolled back transaction=${txid:-record-unreadable}"
  else
    info "failed update rolled back; transaction evidence recording also failed (operator investigation required)"
  fi
  fail "$reason; source release restored"
}

record_pre_activation_stop_failure() {
  reason=$1
  runtime_ok=false
  observer_ok=false
  if sh "$P702" status >/dev/null 2>&1; then runtime_ok=true; fi
  if sh "$P705" status >/dev/null 2>&1; then observer_ok=true; fi
  workspace_disposition="$workspace_disposition; stop_for_update=failed; post_stop_state=not_queried_after_stop_failure; signal_disposition=unknown_to_adapter"
  payload="$txdir/pre-activation-stop-failure-$(date -u '+%Y%m%dT%H%M%SZ').json"
  write_payload "$payload" "$plan_id" "$source" "$target" FAIL "$backup" "$backup_sha" "$runtime_ok" "$observer_ok" "not executed: target activation never began; current pointer unchanged; backup retained; operator investigation/retry required" "$workspace_disposition"
  tx=$(python3 "$P706" record --runtime-root "$RUNTIME_ROOT" --payload "$payload" --json || true)
  if [ -n "$tx" ]; then
    txid=$(printf '%s' "$tx" | python3 -c 'import json,sys; print(json.load(sys.stdin)["transaction_id"])' 2>/dev/null || true)
    info "pre-activation Workspace stop failure recorded transaction=${txid:-record-unreadable}"
  else
    info "pre-activation Workspace stop failure; transaction evidence recording also failed (operator investigation required)"
  fi
  fail "$reason; target activation never began"
}

preflight() {
  decision_ref=${1:-}
  [ -n "$decision_ref" ] || fail "decision-ref is required"
  assert_macos
  target=$(assert_canonical_checkout)
  source=$(current_release)
  workspace=$(workspace_status) || fail "Workspace listener classification failed"
  [ "$(workspace_state "$workspace")" != "UNKNOWN" ] || fail "Workspace listener is UNKNOWN; operator investigation required"
  [ "$source" != "$target" ] || fail "canonical target is already the active release"
  prepare_target "$target"
  python3 "$P706" preflight --runtime-root "$RUNTIME_ROOT" --target-release "$target" --decision-ref "$decision_ref"
}

update_runtime() {
  decision_ref=${1:-}
  [ -n "$decision_ref" ] || fail "decision-ref is required"
  assert_macos
  command -v launchctl >/dev/null 2>&1 || fail "launchctl unavailable"
  source=$(current_release)
  target=$(assert_canonical_checkout)
  [ "$source" != "$target" ] || fail "canonical target is already the active release"
  sh "$P702" status >/dev/null
  verify_source_observer_preupdate "$source"
  workspace=$(workspace_status) || fail "Workspace listener classification failed"
  workspace_state_value=$(workspace_state "$workspace")
  [ "$workspace_state_value" != "UNKNOWN" ] || fail "Workspace listener is UNKNOWN; operator investigation required"
  workspace_was_running=false
  if [ "$workspace_state_value" = "CURRENT_EXACT" ] || [ "$workspace_state_value" = "STALE_KNOWN_EXACT" ]; then
    workspace_was_running=true
  fi
  workspace_disposition="preflight=$workspace_state_value; previously_running=$workspace_was_running"
  prepare_target "$target"
  plan=$(python3 "$P706" preflight --runtime-root "$RUNTIME_ROOT" --target-release "$target" --decision-ref "$decision_ref" --json) || fail "compatibility/migration preflight rejected target"
  plan_id=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_id"])')

  acquire_lock
  trap 'release_lock' EXIT HUP INT TERM
  stamp=$(date -u '+%Y%m%dT%H%M%SZ')
  txdir="$RUNTIME_ROOT/evidence/p7-06/work-$stamp-$$"
  mkdir -p "$txdir"; chmod 700 "$txdir"
  cp "$RUNTIME_PLIST" "$txdir/pre-runtime.plist"
  cp "$OBSERVER_PLIST" "$txdir/pre-observer.plist"
  chmod 600 "$txdir/pre-runtime.plist" "$txdir/pre-observer.plist"

  backup_info=$(backup_preupdate "$source")
  backup=${backup_info%%|*}; backup_sha=${backup_info#*|}
  info "pre-update backup PASS sha256=$backup_sha"
  printf '%s\n' "$workspace_was_running" > "$txdir/workspace-was-running"
  chmod 600 "$txdir/workspace-was-running"

  if [ "$workspace_was_running" = "true" ]; then
    workspace_stop_for_update >/dev/null || record_pre_activation_stop_failure "known Workspace listener did not stop for update"
    workspace_disposition="$workspace_disposition; stopped_for_update=true"
  fi

  if ! sh "$P705" uninstall; then rollback_and_record_failure "source observer did not unload"; fi
  if ! sh "$P702" stop; then rollback_and_record_failure "source runtime did not stop"; fi
  wait_runtime_quiescent || rollback_and_record_failure "source runtime process did not quiesce after stop"
  if ! sh "$P702" install >/dev/null; then rollback_and_record_failure "target activation failed"; fi
  [ "$(current_release)" = "$target" ] || rollback_and_record_failure "target release did not become current"
  if ! sh "$P702" status >/dev/null; then rollback_and_record_failure "target runtime exact-release health verification failed"; fi
  if ! sh "$P705" install >/dev/null; then rollback_and_record_failure "observer re-pin failed"; fi
  if ! sh "$P705" status >/dev/null; then rollback_and_record_failure "observer exact-release verification failed"; fi
  if [ "$workspace_was_running" = "true" ]; then
    if ! workspace_start >/dev/null; then rollback_and_record_failure "target Workspace exact-release restart failed"; fi
    workspace_disposition="$workspace_disposition; restarted_target=true"
  fi

  payload="$txdir/transaction-payload.json"
  write_payload "$payload" "$plan_id" "$source" "$target" PASS "$backup" "$backup_sha" true true "safe: unchanged P7.03 store schema; exact release re-pin available" "$workspace_disposition"
  tx=$(python3 "$P706" record --runtime-root "$RUNTIME_ROOT" --payload "$payload" --json)
  txid=$(printf '%s' "$tx" | python3 -c 'import json,sys; print(json.load(sys.stdin)["transaction_id"])')
  python3 - "$RUNTIME_ROOT/run/p7-06-last-success.json" "$txdir" "$txid" "$source" "$target" "$plan_id" "$backup" "$backup_sha" "$workspace_was_running" <<'PY'
import json, os, sys
path, txdir, txid, source, target, plan, backup, backup_sha, workspace_was_running = sys.argv[1:]
with open(path, "w", encoding="utf-8") as h:
    json.dump({"transaction_id":txid,"work_dir":txdir,"source_release":source,"target_release":target,"plan_id":plan,"backup_path":backup,"backup_sha256":backup_sha,"workspace_was_running":workspace_was_running == "true"}, h, sort_keys=True, indent=2); h.write("\n")
os.chmod(path, 0o600)
PY
  info "update PASS source=$source target=$target transaction=$txid"
  release_lock; trap - EXIT HUP INT TERM
}

rollback_last() {
  assert_macos
  pointer="$RUNTIME_ROOT/run/p7-06-last-success.json"
  [ -f "$pointer" ] || fail "no successful P7.06 transaction is available for rollback"
  source=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_release"])' "$pointer")
  target=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["target_release"])' "$pointer")
  txdir=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["work_dir"])' "$pointer")
  plan_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["plan_id"])' "$pointer")
  backup=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["backup_path"])' "$pointer")
  backup_sha=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["backup_sha256"])' "$pointer")
  workspace_was_running=$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1])).get("workspace_was_running", False)).lower())' "$pointer")
  [ "$(current_release)" = "$target" ] || fail "rollback source mismatch: active release is not transaction target"
  acquire_lock; trap 'release_lock' EXIT HUP INT TERM
  restore_plist_and_start "$txdir" "$source"
  payload="$txdir/rollback-payload-$(date -u '+%Y%m%dT%H%M%SZ').json"
  workspace_disposition="manual rollback; prior Workspace running=$workspace_was_running"
  write_payload "$payload" "$plan_id" "$source" "$target" ROLLED_BACK "$backup" "$backup_sha" true true "executed: exact source release re-pin; durable schema unchanged; backup retained and not restored" "$workspace_disposition"
  tx=$(python3 "$P706" record --runtime-root "$RUNTIME_ROOT" --payload "$payload" --json)
  txid=$(printf '%s' "$tx" | python3 -c 'import json,sys; print(json.load(sys.stdin)["transaction_id"])')
  info "rollback PASS active=$source from_target=$target transaction=$txid"
  release_lock; trap - EXIT HUP INT TERM
}

recover_interrupted_latest() {
  assert_macos
  command -v launchctl >/dev/null 2>&1 || fail "launchctl unavailable"
  acquire_lock; trap 'release_lock' EXIT HUP INT TERM

  txdir=$(python3 - "$RUNTIME_ROOT/evidence/p7-06" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
candidates = [
    path for path in root.glob("work-*")
    if path.is_dir()
    and (path / "pre-runtime.plist").is_file()
    and (path / "pre-observer.plist").is_file()
]
if not candidates:
    raise SystemExit(1)
latest = max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))
print(latest)
PY
  ) || fail "no interrupted P7.06 work evidence is available for recovery"

  source=$(python3 - "$txdir/pre-runtime.plist" "$RUNTIME_ROOT" "$RUNTIME_LABEL" <<'PY'
import plistlib
import sys
from pathlib import Path

plist_path, root, expected_label = sys.argv[1:]
with open(plist_path, "rb") as handle:
    payload = plistlib.load(handle)
if payload.get("Label") != expected_label:
    raise SystemExit(1)
args = payload.get("ProgramArguments")
if not isinstance(args, list):
    raise SystemExit(1)
try:
    root_index = args.index("--runtime-root")
    release_index = args.index("--release-sha")
    runtime_root = args[root_index + 1]
    release = args[release_index + 1]
except (ValueError, IndexError):
    raise SystemExit(1)
if runtime_root != root:
    raise SystemExit(1)
if len(release) != 40 or any(ch not in "0123456789abcdef" for ch in release):
    raise SystemExit(1)
expected_python = str(Path(root) / "venvs" / release / "bin" / "python")
expected_runtime = str(Path(root) / "releases" / release / "source/reference/python/p7_02_persistent_runtime.py")
if len(args) < 2 or args[0] != expected_python or args[1] != expected_runtime:
    raise SystemExit(1)
print(release)
PY
  ) || fail "latest interrupted work evidence does not identify an exact valid source release"
  workspace_was_running=false
  if [ -f "$txdir/workspace-was-running" ]; then
    workspace_was_running=$(cat "$txdir/workspace-was-running")
    [ "$workspace_was_running" = "true" ] || [ "$workspace_was_running" = "false" ] || fail "interrupted work Workspace state is invalid"
  fi

  before=$(current_release)
  restore_plist_and_start "$txdir" "$source"
  stamp=$(date -u '+%Y%m%dT%H%M%SZ')
  evidence="$txdir/interrupted-recovery-$stamp.json"
  python3 - "$evidence" "$source" "$before" "$(basename "$txdir")" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path, source, before, work_dir = sys.argv[1:]
value = {
    "schema": "arvectum.p7_06.interrupted-recovery/1",
    "classification": "owner-local operational recovery evidence; non-canonical",
    "operating_mode": "Persistent Internal / owner-operated",
    "source_release_restored": source,
    "observed_current_before_recovery": before,
    "work_evidence_directory": work_dir,
    "runtime_exact_release_health_verified": True,
    "observer_exact_release_pin_verified": True,
    "deployment_transaction_recorded_by_recovery": False,
    "durable_backup_restored": False,
    "canonical_mutation_performed_by_recovery": False,
    "product_external_effect_invoked": False,
    "historical_effect_replay_invoked": False,
    "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
    handle.write("\n")
os.chmod(path, 0o600)
PY
  info "interrupted recovery PASS source=$source evidence=$evidence"
  release_lock; trap - EXIT HUP INT TERM
}

status_runtime() {
  assert_macos
  sh "$P702" status
  sh "$P705" status
  python3 "$P706" status --runtime-root "$RUNTIME_ROOT" --json
}

usage() {
  cat <<EOF
Usage: $0 preflight <decision-ref>|update <decision-ref>|rollback-last|recover-interrupted-latest|status

P7.06 is a private owner-operated deployment adapter. It pins exact Git releases,
requires a verified pre-update P7.03 backup, rejects state-format migration until a
bounded governed executor + rollback proof exists, stops/re-pins runtime+observer
as one release unit, and never authorizes/replays product or external effects.

recover-interrupted-latest restores the exact source release from the newest bounded
work evidence after an interrupted failed-update rollback. It does not restore the
durable backup, replay effects or create a successful deployment transaction.
EOF
}

case "${1:-}" in
  preflight) preflight "${2:-}" ;;
  update) update_runtime "${2:-}" ;;
  rollback-last) rollback_last ;;
  recover-interrupted-latest) recover_interrupted_latest ;;
  status) status_runtime ;;
  *) usage; exit 2 ;;
esac
