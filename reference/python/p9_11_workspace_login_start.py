"""One-shot owner-local login start; no service installation or grant changes."""
import argparse
import json
import os
import plistlib
import re
import stat
import time
from contextlib import contextmanager, ExitStack
from pathlib import Path

import p7_06_governed_deploy as p706
import p9_11_workspace_process as p911

LABEL = "com.arvectum.os.p9-11-login-start"
LOCKS = ("desktop-launcher.lock", "p7-06-deploy.lock")


class LoginStartError(RuntimeError):
    pass


def private_dir(p):
    s = p.lstat()
    if p.resolve() != p or not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise LoginStartError("unsafe runtime directory")


@contextmanager
def own_lock(path):
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise LoginStartError("existing lifecycle lock; no start") from exc
    marker = path / "pid"
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()) + "\n")
        yield
    finally:
        if marker.is_file() and not marker.is_symlink() and marker.read_text().strip() == str(os.getpid()):
            marker.unlink()
            path.rmdir()


def start_once(root, expected_release, *, attempts=15, sleep=time.sleep):
    root = Path(root)
    private_dir(root)
    private_dir(root / "run")
    if not isinstance(expected_release,str) or not re.fullmatch("[0-9a-f]{40}", expected_release):
        raise LoginStartError("invalid release")
    with ExitStack() as stack:
        for name in LOCKS:
            stack.enter_context(own_lock(root / "run" / name))
        if p706.current_release(root) != expected_release:
            raise LoginStartError("release changed")
        p706.verify_release(root, expected_release, allow_legacy_repository=True)
        before = p911.status(root)
        if before["state"] == p911.CURRENT_EXACT:
            return before
        if before["state"] != p911.NOT_RUNNING:
            raise LoginStartError("unrecognized or stale listener; no signal")
        for i in range(attempts):
            try:
                p911._require_p702_health(root, expected_release)
                break
            except p911.WorkspaceProcessError:
                if i == attempts - 1:
                    raise LoginStartError("core did not become healthy; no spawn") from None
                sleep(2)
        if p706.current_release(root) != expected_release:
            raise LoginStartError("release changed")
        after = p911.start(root)
        if after["state"] != p911.CURRENT_EXACT or after["release_sha"] != expected_release:
            raise LoginStartError("exact listener not proven")
        return after


def agent_spec(root):
    root = Path(root)
    private_dir(root)
    script = r'''
set -eu
root=$1
[ -L "$root/current" ] || exit 1
release=$(/usr/bin/basename "$(/usr/bin/readlink "$root/current")")
case "$release" in ''|*[!0123456789abcdef]*) exit 1;; esac
[ "${#release}" = 40 ] || exit 1
exec "$root/venvs/$release/bin/python" -B "$root/releases/$release/source/reference/python/p9_11_workspace_login_start.py" start --runtime-root "$root" --expected-release "$release"
'''
    return {"Label": LABEL, "ProgramArguments": ["/bin/sh", "-c", script, "arvectum-login", str(root)],
            "RunAtLoad": True, "AbandonProcessGroup": True, "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            "StandardOutPath": str(root / "logs/p9-11-login-start.stdout.log"),
            "StandardErrorPath": str(root / "logs/p9-11-login-start.stderr.log")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("start", "render-plist"))
    p.add_argument("--runtime-root", required=True)
    p.add_argument("--expected-release")
    args = p.parse_args()
    root = Path(args.runtime_root)
    if args.command == "render-plist":
        print(plistlib.dumps(agent_spec(root)).decode(), end="")
    else:
        print(json.dumps(start_once(root, args.expected_release), sort_keys=True))


if __name__ == "__main__":
    main()
