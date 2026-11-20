#!/usr/bin/env python3
"""Exact-release Productive Workspace process lifecycle helper.

This owner-local helper is not a daemon or a service manager. It proves that the
loopback Workspace listener belongs to an installed exact release before it is
reported ready or, during a P7.06 transition, gracefully stopped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import p7_06_governed_deploy as p706

# Public publication pin, not a policy digest or credential. The operator must
# independently provision the exact release-bound private launch record.
OWNER_QUEUE_CONTRACT = "0af2c545f0e68c4f0b8d684a11e3d9051a6d30a5"
OWNER_QUEUE_SUFFIX = re.compile(r" --owner-queue-policy-sha256 ([0-9a-f]{64}) --owner-queue-contract-blob ([0-9a-f]{40})$")

PORT = 8769
HOST = "127.0.0.1"
PROCESS_SCHEMA = "arvectum.p9_11.workspace-process/2"
STOP_SCHEMA = "arvectum.p9_11.workspace-stop/1"
MAX_WAIT_SECONDS = 30.0
POLL_SECONDS = 0.25
ASSET_HREF = re.compile(rb'(?:src|href)="/(assets/[A-Za-z0-9_-]+\.(?:js|css))"')

NOT_RUNNING = "NOT_RUNNING"
CURRENT_EXACT = "CURRENT_EXACT"
STALE_KNOWN_EXACT = "STALE_KNOWN_EXACT"
UNKNOWN = "UNKNOWN"


class WorkspaceProcessError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    if path.is_symlink():
        raise WorkspaceProcessError("operational metadata target must not be a symlink")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _current_release(root: Path) -> str:
    return p706.current_release(root)


def _release_paths(root: Path, release: str) -> tuple[Path, Path, Path, Path]:
    release_root = root / "releases" / release
    source = release_root / "source/reference/python"
    return (
        root / "venvs" / release / "bin/python",
        source / "p9_03_workspace.py",
        source,
        source / "workspace_frontend/dist/index.html",
    )


def _command(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceProcessError(f"process inspection command failed: {args[0]}") from exc
    if result.returncode not in {0, 1}:
        raise WorkspaceProcessError(f"process inspection command failed: {args[0]}")
    return result.stdout


def _listener() -> tuple[int, str] | None:
    output = _command(["lsof", "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-Fpcn"])
    pid: int | None = None
    command = ""
    address = ""
    listeners: list[tuple[int, str, str]] = []
    for line in output.splitlines():
        if not line:
            continue
        field, value = line[0], line[1:]
        if field == "p":
            if pid is not None and address:
                listeners.append((pid, command, address))
            pid = int(value) if value.isdigit() else None
            command = ""
            address = ""
        elif field == "c":
            command = value
        elif field == "n":
            address = value
    if pid is not None and address:
        listeners.append((pid, command, address))
    if not listeners:
        return None
    if len(listeners) != 1 or listeners[0][2] != f"{HOST}:{PORT}":
        raise WorkspaceProcessError("listener is not exactly one IPv4 loopback Workspace socket")
    return listeners[0][0], listeners[0][1]


def _process_cwd(pid: int) -> Path | None:
    output = _command(["lsof", "-n", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    for line in output.splitlines():
        if line.startswith("n"):
            return Path(line[1:]).resolve()
    return None


def _process_command(pid: int) -> str:
    return _command(["ps", "-ww", "-p", str(pid), "-o", "command="]).strip()


def _process_start_identity(pid: int) -> str | None:
    value = _command(["ps", "-ww", "-p", str(pid), "-o", "lstart="]).strip()
    return value or None


def _owner_queue_launch_args(root: Path, release: str) -> list[str]:
    """Read an independently provisioned launch pin, never derive it from policy."""
    path = root / "config/owner-project-queue-launch.json"
    if not path.exists() and not path.is_symlink():
        return []
    if path.resolve() != path:
        raise WorkspaceProcessError("owner queue launch record unsafe")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise WorkspaceProcessError("owner queue launch record unsafe")
        raw = handle.read(4097)
    if len(raw) > 4096:
        raise WorkspaceProcessError("owner queue launch record too large")
    record = json.loads(raw)
    if not isinstance(record, dict) or set(record) != {"schema", "release_commit", "contract_blob", "policy_sha256"}:
        raise WorkspaceProcessError("owner queue launch record invalid")
    pin = record["policy_sha256"]
    if (record["schema"] != "arvectum.workspace.owner-project-queue-launch/1"
            or record["contract_blob"] != OWNER_QUEUE_CONTRACT
            or not isinstance(pin, str) or not re.fullmatch("[0-9a-f]{64}", pin)
            or not isinstance(record["release_commit"], str)
            or not re.fullmatch("[0-9a-f]{40}", record["release_commit"])):
        raise WorkspaceProcessError("owner queue launch record invalid")
    # An older or later release must not inherit this activation automatically.
    if record["release_commit"] != release:
        return []
    return ["--owner-queue-policy-sha256", pin, "--owner-queue-contract-blob", OWNER_QUEUE_CONTRACT]


def _process_identity(command: str, cwd: Path | None, python: Path, entrypoint: Path) -> tuple[bool, str | None]:
    if cwd is None:
        return False, "wrong cwd"
    # Only the exact ordered two-pin suffix is recognised; arbitrary flags
    # remain forbidden. This proves process identity, not permission to read.
    suffix = OWNER_QUEUE_SUFFIX.search(command)
    if suffix:
        if suffix.group(2) != OWNER_QUEUE_CONTRACT:
            return False, "wrong owner queue contract"
        command = command[:suffix.start()]
    if not command.endswith(" serve"):
        return False, "not Workspace command"
    absolute_suffix = f" {entrypoint} serve"
    relative_name = entrypoint.name
    if command.endswith(absolute_suffix):
        executable_display = command[: -len(absolute_suffix)]
        resolved_entrypoint = entrypoint.resolve()
    elif command.endswith(f" {relative_name} serve"):
        idx = len(command) - len(f" {relative_name} serve")
        if idx <= 0:
            return False, "not Workspace command"
        executable_display = command[:idx]
        resolved_entrypoint = (cwd / relative_name).resolve()
    else:
        return False, "wrong entrypoint"
    if not executable_display or executable_display != executable_display.strip():
        return False, "not Workspace command"
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in executable_display):
        return False, "not Workspace command"
    if resolved_entrypoint != entrypoint.resolve():
        return False, "wrong entrypoint"
    candidate = Path(executable_display)
    if not candidate.is_file():
        return False, "not Workspace command"
    if not os.access(candidate, os.X_OK):
        return False, "not Workspace command"
    try:
        direct_proof = os.path.samefile(executable_display, python)
    except OSError:
        direct_proof = False
    return direct_proof, None


def _managed_proof(root: Path, pid: int, release: str, python: Path, entrypoint: Path, source: Path) -> bool:
    path = root / "run/workspace-process.json"
    try:
        details = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    if path.is_symlink() or not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid() or details.st_mode & 0o077:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    identity = _process_start_identity(pid)
    return (
        payload.get("schema") == PROCESS_SCHEMA
        and payload.get("classification") == "non-canonical operational telemetry"
        and payload.get("managed_by") == "p9_11_workspace_process"
        and payload.get("pid") == pid
        and payload.get("release_sha") == release
        and payload.get("requested_python") == str(python)
        and payload.get("requested_entrypoint") == str(entrypoint)
        and payload.get("requested_cwd") == str(source)
        and payload.get("bind") == f"{HOST}:{PORT}"
        and payload.get("observed_process_start_identity") == identity
    )


def _invalidate_matching_metadata(root: Path, pid: int, release: str, start_identity: str) -> None:
    path = root / "run/workspace-process.json"
    try:
        details = path.stat(follow_symlinks=False)
        if path.is_symlink() or not stat.S_ISREG(details.st_mode):
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return
    if (
        payload.get("schema") == PROCESS_SCHEMA
        and payload.get("managed_by") == "p9_11_workspace_process"
        and payload.get("pid") == pid
        and payload.get("release_sha") == release
        and payload.get("observed_process_start_identity") == start_identity
    ):
        path.unlink()


def _cleanup_own_spawn(process: subprocess.Popen[Any], start_identity: str | None, root: Path, release: str) -> None:
    if process.poll() is not None:
        if start_identity is not None:
            _invalidate_matching_metadata(root, process.pid, release, start_identity)
        return
    if start_identity is None:
        process.terminate()
    elif _process_start_identity(process.pid) == start_identity:
        os.kill(process.pid, signal.SIGTERM)
    else:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:
        raise WorkspaceProcessError("new Workspace process did not stop gracefully") from exc
    if start_identity is not None:
        _invalidate_matching_metadata(root, process.pid, release, start_identity)


def _fetch(path: str) -> bytes:
    try:
        with urlopen(f"http://{HOST}:{PORT}{path}", timeout=3) as response:
            if response.status != 200:
                raise WorkspaceProcessError(f"Workspace HTTP returned {response.status}")
            return response.read(4 * 1024 * 1024)
    except (URLError, OSError) as exc:
        raise WorkspaceProcessError("Workspace HTTP is unavailable") from exc


def _live_assets_match(index: Path) -> bool:
    try:
        expected = index.read_bytes()
        live = _fetch("/")
    except (OSError, WorkspaceProcessError):
        return False
    if live != expected:
        return False
    for asset in ASSET_HREF.findall(expected):
        path = index.parent / asset.decode("ascii")
        try:
            matches = path.is_file() and _fetch("/" + asset.decode("ascii")) == path.read_bytes()
        except (OSError, WorkspaceProcessError):
            return False
        if not matches:
            return False
    return True


def status(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    current = _current_release(root)
    try:
        listener = _listener()
    except WorkspaceProcessError as exc:
        return {"state": UNKNOWN, "current_release": current, "reason": str(exc)}
    if listener is None:
        return {"state": NOT_RUNNING, "current_release": current}
    pid, listener_command = listener
    command = _process_command(pid)
    cwd = _process_cwd(pid)
    if cwd is None:
        return {"state": UNKNOWN, "current_release": current, "pid": pid, "reason": "wrong cwd"}
    releases = root / "releases"
    try:
        release = cwd.relative_to(releases).parts[0]
        python, entrypoint, source, index = _release_paths(root, release)
        p706.verify_release(root, release, allow_legacy_repository=True)
    except (ValueError, IndexError, OSError, p706.P706Error):
        return {"state": UNKNOWN, "current_release": current, "pid": pid, "reason": "invalid release provenance"}
    if cwd != source.resolve():
        return {"state": UNKNOWN, "current_release": current, "pid": pid, "reason": "wrong cwd"}
    if not python.is_file() or not entrypoint.is_file():
        return {"state": UNKNOWN, "current_release": current, "pid": pid, "reason": "invalid release provenance"}
    direct_proof, identity_error = _process_identity(command, cwd, python, entrypoint)
    if identity_error:
        return {"state": UNKNOWN, "current_release": current, "pid": pid, "reason": identity_error}
    if not _live_assets_match(index):
        return {"state": UNKNOWN, "current_release": current, "pid": pid, "reason": "asset mismatch"}
    proof_mode = "DIRECT_OS_PROOF" if direct_proof else "MANAGED_SPAWN_PROOF" if _managed_proof(root, pid, release, python, entrypoint, source) else "NONE"
    if proof_mode == "NONE":
        return {"state": UNKNOWN, "current_release": current, "pid": pid, "release_sha": release, "proof_mode": proof_mode, "reason": "exact invocation provenance is unavailable"}
    state = CURRENT_EXACT if release == current else STALE_KNOWN_EXACT
    return {"state": state, "current_release": current, "release_sha": release, "pid": pid, "listener_command": listener_command, "proof_mode": proof_mode, "process_start_identity": _process_start_identity(pid)}


def _require_p702_health(root: Path, release: str) -> None:
    python, _, source, _ = _release_paths(root, release)
    runtime = source / "p7_02_persistent_runtime.py"
    result = subprocess.run(
        [str(python), str(runtime), "check", "--runtime-root", str(root), "--expected-release", release, "--max-age-seconds", "20"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise WorkspaceProcessError("P7.02 exact-current runtime health verification failed")


def _write_process_metadata(root: Path, release: str, pid: int, start_identity: str) -> None:
    python, entrypoint, source, index = _release_paths(root, release)
    release_payload = json.loads((index.parent.parent.parent / "workspace_app/release.json").read_text(encoding="utf-8"))
    _atomic_json(root / "run/workspace-process.json", {
        "schema": PROCESS_SCHEMA,
        "classification": "non-canonical operational telemetry",
        "managed_by": "p9_11_workspace_process",
        "pid": pid,
        "release_sha": release,
        "workspace_release": release_payload["release_id"],
        "app_api_contract": release_payload["app_api_contract"],
        "requested_python": str(python),
        "requested_entrypoint": str(entrypoint),
        "requested_cwd": str(source),
        "spawned_at": _utc_now(),
        "observed_process_start_identity": start_identity,
        "bind": f"{HOST}:{PORT}",
    })


def start(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    before = status(root)
    if before["state"] == CURRENT_EXACT:
        return before
    if before["state"] != NOT_RUNNING:
        raise WorkspaceProcessError(f"Workspace start refused: {before['state']}")
    release = _current_release(root)
    python, entrypoint, source, _ = _release_paths(root, release)
    if not python.is_file() or not entrypoint.is_file():
        raise WorkspaceProcessError("current exact release lacks Workspace process files")
    _require_p702_health(root, release)
    checked = subprocess.run([str(python), str(entrypoint), "check"], cwd=source, check=False, capture_output=True, text=True, timeout=30)
    if checked.returncode != 0:
        raise WorkspaceProcessError("current exact Workspace check failed")
    launch_args = _owner_queue_launch_args(root, release)
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    os.chmod(logs, 0o700)
    stdout = (logs / "workspace.stdout.log").open("w", encoding="utf-8")
    stderr = (logs / "workspace.stderr.log").open("w", encoding="utf-8")
    os.chmod(stdout.name, 0o600)
    os.chmod(stderr.name, 0o600)
    process = subprocess.Popen([str(python), str(entrypoint), "serve", *launch_args], cwd=source, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
    stdout.close()
    stderr.close()
    start_identity = _process_start_identity(process.pid)
    if start_identity is None:
        _cleanup_own_spawn(process, None, root, release)
        raise WorkspaceProcessError("new Workspace process has no observable start identity")
    try:
        _write_process_metadata(root, release, process.pid, start_identity)
    except Exception:
        _cleanup_own_spawn(process, start_identity, root, release)
        raise
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    last_observed: dict[str, Any] = before
    while time.monotonic() < deadline:
        last_observed = status(root)
        if last_observed["state"] == CURRENT_EXACT and last_observed.get("pid") == process.pid:
            return last_observed
        if process.poll() is not None:
            break
        time.sleep(POLL_SECONDS)
    _cleanup_own_spawn(process, start_identity, root, release)
    last_state = last_observed.get("state", "UNKNOWN")
    reason = last_observed.get("reason", "unknown")
    proof_mode = last_observed.get("proof_mode", "NONE")
    raise WorkspaceProcessError(
        f"exact Workspace process did not become ready: "
        f"state={last_state} reason={reason} proof_mode={proof_mode}"
    )


def _wait_for_exact_process_stop(root: Path, pid: int, release: str, start_identity: str) -> dict[str, Any]:
    """Wait for the already-proven process without consulting shutdown-volatile HTTP."""
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        observed_identity = _process_start_identity(pid)
        if observed_identity is not None and observed_identity != start_identity:
            raise WorkspaceProcessError("Workspace stop refused: process identity changed after signal")
        listener = _listener()
        if listener is not None and listener[0] != pid:
            raise WorkspaceProcessError("Workspace stop refused: foreign listener appeared after signal")
        if observed_identity is None and listener is None:
            _invalidate_matching_metadata(root, pid, release, start_identity)
            _atomic_json(root / "run/workspace-last-stop.json", {
                "schema": STOP_SCHEMA,
                "classification": "non-canonical operational telemetry",
                "pid": pid,
                "release_sha": release,
                "stopped_at": _utc_now(),
                "bind": f"{HOST}:{PORT}",
            })
            return {"state": NOT_RUNNING, "stopped_pid": pid, "stopped_release": release}
        time.sleep(POLL_SECONDS)
    raise WorkspaceProcessError("known Workspace process did not stop gracefully")


def stop_for_update(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    before = status(root)
    if before["state"] == NOT_RUNNING:
        return before
    if before["state"] not in {CURRENT_EXACT, STALE_KNOWN_EXACT} or before.get("proof_mode") not in {"DIRECT_OS_PROOF", "MANAGED_SPAWN_PROOF"}:
        raise WorkspaceProcessError("Workspace stop refused: listener is UNKNOWN")
    pid = int(before["pid"])
    start_identity = before.get("process_start_identity")
    if not isinstance(start_identity, str) or not start_identity:
        raise WorkspaceProcessError("Workspace stop refused: process start identity is unavailable")
    revalidated = status(root)
    if revalidated.get("state") != before["state"] or revalidated.get("pid") != pid or revalidated.get("release_sha") != before.get("release_sha") or revalidated.get("proof_mode") != before.get("proof_mode") or revalidated.get("process_start_identity") != start_identity:
        raise WorkspaceProcessError("Workspace stop refused: process identity changed")
    os.kill(pid, signal.SIGTERM)
    return _wait_for_exact_process_stop(root, pid, before["release_sha"], start_identity)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Arvectum OS exact-release Workspace process helper")
    parser.add_argument("command", choices=("status", "start", "stop-for-update"))
    parser.add_argument("--runtime-root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = Path(args.runtime_root)
        value = status(root) if args.command == "status" else start(root) if args.command == "start" else stop_for_update(root)
    except (WorkspaceProcessError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"P9.11 Workspace process FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
