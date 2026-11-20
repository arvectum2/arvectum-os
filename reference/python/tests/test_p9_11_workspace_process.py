import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("p9_11_workspace_process", HERE / "p9_11_workspace_process.py")
process = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(process)


class WorkspaceProcessStatusTests(unittest.TestCase):
    def _root(self, current: str, listener: str) -> pathlib.Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = pathlib.Path(temporary.name)
        for release in {current, listener}:
            source = root / "releases" / release / "source/reference/python"
            source.mkdir(parents=True)
            (root / "venvs" / release / "bin").mkdir(parents=True)
            python = root / "venvs" / release / "bin/python"
            python.write_text("#!/bin/sh\nexit 0\n")
            os.chmod(python, 0o755)
            (source / "p9_03_workspace.py").touch()
            (source / "workspace_frontend/dist").mkdir(parents=True)
            (source / "workspace_frontend/dist/index.html").touch()
            (source / "workspace_app").mkdir()
            (source / "workspace_app/release.json").write_text(json.dumps({"release_id": "p9.11.3", "app_api_contract": 11}))
        return root.resolve()

    def _status(self, root: pathlib.Path, listener_release: str):
        source = root / "releases" / listener_release / "source/reference/python"
        python = root / "venvs" / listener_release / "bin/python"
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(30686, "Python")),
            mock.patch.object(process, "_process_command", return_value=f"{python} p9_03_workspace.py serve"),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            return process.status(root)

    def test_current_exact_requires_exact_listener_release(self):
        root = self._root("current", "current")
        self.assertEqual(self._status(root, "current")["state"], process.CURRENT_EXACT)

    def test_historical_exact_listener_is_stale_known_exact(self):
        root = self._root("current", "historical")
        observed = self._status(root, "historical")
        self.assertEqual(observed["state"], process.STALE_KNOWN_EXACT)
        self.assertEqual(observed["pid"], 30686)

    def test_non_workspace_listener_is_unknown(self):
        root = self._root("current", "current")
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(30686, "Python")),
            mock.patch.object(process, "_process_command", return_value="unrelated"),
            mock.patch.object(process, "_process_cwd", return_value=None),
        ):
            self.assertEqual(process.status(root)["state"], process.UNKNOWN)

    def test_no_listener_is_not_running(self):
        root = self._root("current", "current")
        with mock.patch.object(process, "_current_release", return_value="current"), mock.patch.object(process, "_listener", return_value=None):
            self.assertEqual(process.status(root)["state"], process.NOT_RUNNING)

    def test_wrong_interpreter_is_unknown(self):
        root = self._root("current", "current")
        source = root / "releases/current/source/reference/python"
        wrong = root / "other-python"
        wrong.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(wrong, 0o755)
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(30686, "Python")),
            mock.patch.object(process, "_process_command", return_value=f"{wrong} p9_03_workspace.py serve"),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            self.assertEqual(process.status(root)["reason"], "exact invocation provenance is unavailable")

    def test_wrong_entrypoint_is_unknown(self):
        root = self._root("current", "current")
        source = root / "releases/current/source/reference/python"
        python = root / "venvs/current/bin/python"
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(30686, "Python")),
            mock.patch.object(process, "_process_command", return_value=f"{python} other.py serve"),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process.p706, "verify_release"),
        ):
            self.assertEqual(process.status(root)["reason"], "wrong entrypoint")

    def test_ambiguous_listener_is_unknown(self):
        root = self._root("current", "current")
        with mock.patch.object(process, "_current_release", return_value="current"), mock.patch.object(process, "_listener", side_effect=process.WorkspaceProcessError("ambiguous/non-loopback listener")):
            observed = process.status(root)
        self.assertEqual(observed["state"], process.UNKNOWN)
        self.assertEqual(observed["reason"], "ambiguous/non-loopback listener")

    def test_framework_interpreter_requires_managed_provenance(self):
        root = self._root("current", "current")
        source = root / "releases/current/source/reference/python"
        framework = root / "framework-python"
        framework.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(framework, 0o755)
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(30686, "Python")),
            mock.patch.object(process, "_process_command", return_value=f"{framework} p9_03_workspace.py serve"),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_process_start_identity", return_value="start"),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            self.assertEqual(process.status(root)["state"], process.UNKNOWN)
            process._write_process_metadata(root, "current", 30686, "start")
            observed = process.status(root)
        self.assertEqual(observed["state"], process.CURRENT_EXACT)
        self.assertEqual(observed["proof_mode"], "MANAGED_SPAWN_PROOF")

    def test_pid_reuse_rejects_managed_metadata(self):
        root = self._root("current", "current")
        process._write_process_metadata(root, "current", 30686, "old-start")
        source = root / "releases/current/source/reference/python"
        framework = root / "framework-python"
        framework.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(framework, 0o755)
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(30686, "Python")),
            mock.patch.object(process, "_process_command", return_value=f"{framework} p9_03_workspace.py serve"),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_process_start_identity", return_value="new-start"),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            self.assertEqual(process.status(root)["state"], process.UNKNOWN)

    def test_stop_refuses_unknown_without_signalling(self):
        with (
            mock.patch.object(process, "status", return_value={"state": process.UNKNOWN}),
            mock.patch.object(process.os, "kill") as kill,
            self.assertRaises(process.WorkspaceProcessError),
        ):
            process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_not_called()

    def test_stop_revalidates_stale_process_before_signalling(self):
        stale = {"state": process.STALE_KNOWN_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF", "process_start_identity": "start"}
        with (
            mock.patch.object(process, "status", side_effect=[stale, stale]) as status,
            mock.patch.object(process.os, "kill") as kill,
            mock.patch.object(process, "_process_start_identity", side_effect=["start", None]),
            mock.patch.object(process, "_listener", side_effect=[(7, "Python"), None]),
            mock.patch.object(process, "_atomic_json"),
        ):
            observed = process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_called_once_with(7, process.signal.SIGTERM)
        self.assertEqual(status.call_count, 2)
        self.assertEqual(observed["state"], process.NOT_RUNNING)

    def test_stop_waits_for_process_after_socket_closes_without_http_status(self):
        stale = {"state": process.CURRENT_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF", "process_start_identity": "start"}
        with (
            mock.patch.object(process, "status", side_effect=[stale, stale]) as status,
            mock.patch.object(process.os, "kill") as kill,
            mock.patch.object(process, "_process_start_identity", side_effect=["start", "start", None]),
            mock.patch.object(process, "_listener", side_effect=[None, None, None]),
            mock.patch.object(process, "_atomic_json"),
            mock.patch.object(process.time, "sleep"),
        ):
            observed = process.stop_for_update(pathlib.Path("/tmp/runtime"))
        self.assertEqual(observed["state"], process.NOT_RUNNING)
        kill.assert_called_once_with(7, process.signal.SIGTERM)
        self.assertEqual(status.call_count, 2)

    def test_stop_waits_for_listener_after_process_exit(self):
        stale = {"state": process.CURRENT_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF", "process_start_identity": "start"}
        with (
            mock.patch.object(process, "status", side_effect=[stale, stale]),
            mock.patch.object(process.os, "kill") as kill,
            mock.patch.object(process, "_process_start_identity", side_effect=[None, None]),
            mock.patch.object(process, "_listener", side_effect=[(7, "Python"), None]),
            mock.patch.object(process, "_atomic_json"),
            mock.patch.object(process.time, "sleep"),
        ):
            observed = process.stop_for_update(pathlib.Path("/tmp/runtime"))
        self.assertEqual(observed["state"], process.NOT_RUNNING)
        kill.assert_called_once_with(7, process.signal.SIGTERM)

    def test_stop_fails_closed_for_pid_reuse_after_one_signal(self):
        stale = {"state": process.CURRENT_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF", "process_start_identity": "start"}
        with (
            mock.patch.object(process, "status", side_effect=[stale, stale]),
            mock.patch.object(process.os, "kill") as kill,
            mock.patch.object(process, "_process_start_identity", return_value="reused"),
            mock.patch.object(process, "_invalidate_matching_metadata") as invalidate,
            self.assertRaisesRegex(process.WorkspaceProcessError, "identity changed after signal"),
        ):
            process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_called_once_with(7, process.signal.SIGTERM)
        invalidate.assert_not_called()

    def test_stop_fails_closed_for_foreign_listener_after_one_signal(self):
        stale = {"state": process.CURRENT_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF", "process_start_identity": "start"}
        with (
            mock.patch.object(process, "status", side_effect=[stale, stale]),
            mock.patch.object(process.os, "kill") as kill,
            mock.patch.object(process, "_process_start_identity", return_value="start"),
            mock.patch.object(process, "_listener", return_value=(8, "Python")),
            self.assertRaisesRegex(process.WorkspaceProcessError, "foreign listener"),
        ):
            process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_called_once_with(7, process.signal.SIGTERM)

    def test_stop_times_out_without_a_second_signal_or_sigkill(self):
        stale = {"state": process.CURRENT_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF", "process_start_identity": "start"}
        with (
            mock.patch.object(process, "status", side_effect=[stale, stale]),
            mock.patch.object(process.os, "kill") as kill,
            mock.patch.object(process, "MAX_WAIT_SECONDS", 0),
            self.assertRaisesRegex(process.WorkspaceProcessError, "did not stop gracefully"),
        ):
            process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_called_once_with(7, process.signal.SIGTERM)

    def test_asset_fetch_failure_is_classified_as_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            dist = pathlib.Path(temporary)
            index = dist / "index.html"
            asset = dist / "assets/app.js"
            asset.parent.mkdir()
            index.write_bytes(b'<script src="/assets/app.js"></script>')
            asset.write_bytes(b"expected")
            with mock.patch.object(process, "_fetch", side_effect=[index.read_bytes(), process.WorkspaceProcessError("Workspace HTTP is unavailable")]):
                self.assertFalse(process._live_assets_match(index))

    def test_stop_does_not_signal_when_identity_changes(self):
        before = {"state": process.STALE_KNOWN_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF"}
        after = {"state": process.STALE_KNOWN_EXACT, "pid": 8, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF"}
        with (
            mock.patch.object(process, "status", side_effect=[before, after]),
            mock.patch.object(process.os, "kill") as kill,
            self.assertRaises(process.WorkspaceProcessError),
        ):
            process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_not_called()

    def test_stop_does_not_signal_when_start_identity_changes(self):
        before = {"state": process.STALE_KNOWN_EXACT, "pid": 7, "release_sha": "a" * 40, "proof_mode": "DIRECT_OS_PROOF", "process_start_identity": "A"}
        after = {**before, "process_start_identity": "B"}
        with (
            mock.patch.object(process, "status", side_effect=[before, after]),
            mock.patch.object(process.os, "kill") as kill,
            self.assertRaises(process.WorkspaceProcessError),
        ):
            process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_not_called()

    def test_stop_refuses_known_state_without_proof_mode(self):
        stale = {"state": process.STALE_KNOWN_EXACT, "pid": 7, "release_sha": "a" * 40}
        with (
            mock.patch.object(process, "status", return_value=stale),
            mock.patch.object(process.os, "kill") as kill,
            self.assertRaises(process.WorkspaceProcessError),
        ):
            process.stop_for_update(pathlib.Path("/tmp/runtime"))
        kill.assert_not_called()

    def test_process_metadata_uses_release_payload_beside_workspace_source(self):
        root = self._root("current", "current")
        release = root / "releases/current/source/reference/python"
        (release / "workspace_app/release.json").write_text(json.dumps({"release_id": "p9.11.3", "app_api_contract": 11}))
        process._write_process_metadata(root, "current", 123, "start")
        payload = json.loads((root / "run/workspace-process.json").read_text())
        self.assertEqual(payload["workspace_release"], "p9.11.3")
        self.assertEqual(payload["requested_python"], str(root / "venvs/current/bin/python"))
        self.assertEqual(payload["observed_process_start_identity"], "start")

    def test_start_uses_exact_argv_cwd_and_check_before_popen(self):
        root = self._root("current", "current")
        source = root / "releases/current/source/reference/python"
        python = root / "venvs/current/bin/python"
        entrypoint = source / "p9_03_workspace.py"
        ready = {"state": process.CURRENT_EXACT, "pid": 42, "release_sha": "current", "proof_mode": "MANAGED_SPAWN_PROOF", "process_start_identity": "start"}
        child = mock.Mock(pid=42)
        child.poll.return_value = None
        with (
            mock.patch.object(process, "status", side_effect=[{"state": process.NOT_RUNNING}, ready]),
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_require_p702_health"),
            mock.patch.object(process.subprocess, "run", return_value=mock.Mock(returncode=0)) as check,
            mock.patch.object(process.subprocess, "Popen", return_value=child) as popen,
            mock.patch.object(process, "_process_start_identity", return_value="start"),
            mock.patch.object(process, "_write_process_metadata"),
        ):
            observed = process.start(root)
        self.assertEqual(observed["proof_mode"], "MANAGED_SPAWN_PROOF")
        self.assertEqual(check.call_args.args[0], [str(python), str(entrypoint), "check"])
        self.assertEqual(popen.call_args.args[0], [str(python), str(entrypoint), "serve"])
        self.assertEqual(popen.call_args.kwargs["cwd"], source)

    def test_start_missing_identity_terminates_only_own_child(self):
        root = self._root("current", "current")
        child = mock.Mock(pid=42)
        child.poll.return_value = None
        with (
            mock.patch.object(process, "status", return_value={"state": process.NOT_RUNNING}),
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_require_p702_health"),
            mock.patch.object(process.subprocess, "run", return_value=mock.Mock(returncode=0)),
            mock.patch.object(process.subprocess, "Popen", return_value=child),
            mock.patch.object(process, "_process_start_identity", return_value=None),
            self.assertRaises(process.WorkspaceProcessError),
        ):
            process.start(root)
        child.terminate.assert_called_once_with()


class LifecycleShellTests(unittest.TestCase):
    def test_update_stops_workspace_after_backup_and_restarts_target(self):
        text = (HERE / "p7_06_macos_deploy.sh").read_text()
        update = text[text.index("update_runtime()"):text.index("rollback_last()")]
        self.assertLess(update.index('backup_preupdate "$source"'), update.index("workspace_stop_for_update"))
        self.assertLess(update.index("workspace_stop_for_update"), update.index('sh "$P705" uninstall'))
        self.assertIn("Workspace listener is UNKNOWN; operator investigation required", update)
        self.assertIn("target Workspace exact-release restart failed", update)
        self.assertIn('"workspace_listener_disposition"', text)
        self.assertIn('printf \'%s\\n\' "$workspace_was_running" > "$txdir/workspace-was-running"', update)
        self.assertIn('source observer did not unload', update)
        self.assertIn('source runtime did not stop', update)
        restore = text[text.index("restore_plist_and_start()"):text.index("backup_preupdate()")]
        self.assertLess(restore.index("workspace_stop_for_update"), restore.index('rm -f "$RUNTIME_ROOT/current"'))
        self.assertIn('workspace-was-running" ]; then', text)

    def test_launcher_requires_current_exact_not_http_200(self):
        text = (HERE / "macos_launcher/launcher.sh").read_text()
        self.assertIn('= "CURRENT_EXACT"', text)
        self.assertIn('start --runtime-root "$RUNTIME_ROOT"', text)
        self.assertNotIn("http_code", text)


class F06SpaceSafeProcessIdentityTests(unittest.TestCase):
    """P9.11-F06: space-safe Workspace process identity recognition."""

    def _root(self, current: str) -> pathlib.Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = pathlib.Path(temporary.name) / "Library/Application Support/ArvectumOS/persistent-internal"
        source = root / "releases" / current / "source/reference/python"
        source.mkdir(parents=True)
        (root / "venvs" / current / "bin").mkdir(parents=True)
        python = root / "venvs" / current / "bin/python"
        python.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(python, 0o755)
        (source / "p9_03_workspace.py").touch()
        (source / "workspace_frontend/dist").mkdir(parents=True)
        (source / "workspace_frontend/dist/index.html").touch()
        (source / "workspace_app").mkdir()
        (source / "workspace_app/release.json").write_text(
            json.dumps({"release_id": "p9.11.3", "app_api_contract": 11})
        )
        return root.resolve()

    def _identity(self, root, command, listener_release="current"):
        source = root / "releases" / listener_release / "source/reference/python"
        python = root / "venvs" / listener_release / "bin/python"
        entrypoint = source / "p9_03_workspace.py"
        return process._process_identity(command, source, python, entrypoint)

    def test_venv_python_with_application_support_spaces(self):
        root = self._root("current")
        source = root / "releases/current/source/reference/python"
        python = root / "venvs/current/bin/python"
        entrypoint = source / "p9_03_workspace.py"
        command = f"{python} {entrypoint} serve"
        ok, err = self._identity(root, command)
        self.assertIsNone(err)
        self.assertTrue(ok)

    def test_framework_python_with_application_support_entrypoint(self):
        root = self._root("current")
        source = root / "releases/current/source/reference/python"
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        entrypoint = source / "p9_03_workspace.py"
        command = f"{fw} {entrypoint} serve"
        ok, err = self._identity(root, command)
        self.assertIsNone(err)
        self.assertFalse(ok)

    def test_framework_managed_proof_current_exact(self):
        root = self._root("current")
        source = root / "releases/current/source/reference/python"
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        entrypoint = source / "p9_03_workspace.py"
        command = f"{fw} {entrypoint} serve"
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(52092, "Python")),
            mock.patch.object(process, "_process_command", return_value=command),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_process_start_identity", return_value="Tue Aug 25 09:50:00 2026"),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            observed = process.status(root)
        self.assertEqual(observed["state"], process.UNKNOWN)
        process._write_process_metadata(root, "current", 52092, "Tue Aug 25 09:50:00 2026")
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(52092, "Python")),
            mock.patch.object(process, "_process_command", return_value=command),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_process_start_identity", return_value="Tue Aug 25 09:50:00 2026"),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            observed = process.status(root)
        self.assertEqual(observed["state"], process.CURRENT_EXACT)
        self.assertEqual(observed["proof_mode"], "MANAGED_SPAWN_PROOF")

    def test_framework_without_managed_proof_is_unknown(self):
        root = self._root("current")
        source = root / "releases/current/source/reference/python"
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        command = f"{fw} p9_03_workspace.py serve"
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(52092, "Python")),
            mock.patch.object(process, "_process_command", return_value=command),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_process_start_identity", return_value="start"),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            observed = process.status(root)
        self.assertEqual(observed["state"], process.UNKNOWN)
        self.assertEqual(observed.get("proof_mode"), "NONE")

    def test_relative_entrypoint_with_space_safe_executable(self):
        root = self._root("current")
        python = root / "venvs/current/bin/python"
        command = f"{python} p9_03_workspace.py serve"
        ok, err = self._identity(root, command)
        self.assertIsNone(err)
        self.assertTrue(ok)

    def test_wrong_relative_script(self):
        root = self._root("current")
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        command = f"{fw} wrong.py serve"
        ok, err = self._identity(root, command)
        self.assertFalse(ok)
        self.assertIn("wrong entrypoint", str(err))

    def test_wrong_absolute_script(self):
        root = self._root("current")
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        command = f"{fw} /tmp/wrong.py serve"
        ok, err = self._identity(root, command)
        self.assertFalse(ok)
        self.assertIn("wrong entrypoint", str(err))

    def test_extra_arguments_after_serve(self):
        root = self._root("current")
        source = root / "releases/current/source/reference/python"
        python = root / "venvs/current/bin/python"
        entrypoint = source / "p9_03_workspace.py"
        command = f"{python} {entrypoint} serve --extra"
        ok, err = self._identity(root, command)
        self.assertFalse(ok)
        self.assertIn("not Workspace command", str(err))

    def test_flag_before_entrypoint_rejected(self):
        root = self._root("current")
        source = root / "releases/current/source/reference/python"
        python = root / "venvs/current/bin/python"
        entrypoint = source / "p9_03_workspace.py"
        command = f"{python} --flag {entrypoint} serve"
        ok, err = self._identity(root, command)
        self.assertFalse(ok)
        self.assertIn("not Workspace command", str(err))

    def test_entrypoint_as_substring_only(self):
        root = self._root("current")
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        command = f"{fw} /tmp/p9_03_workspace.py.bak serve"
        ok, err = self._identity(root, command)
        self.assertFalse(ok)
        self.assertIn("wrong entrypoint", str(err))

    def test_historical_unproven_process_stays_unknown(self):
        root = self._root("current")
        source = root / "releases/current/source/reference/python"
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        command = f"{fw} p9_03_workspace.py serve"
        with (
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_listener", return_value=(30686, "Python")),
            mock.patch.object(process, "_process_command", return_value=command),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_process_start_identity", return_value="old-start"),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
        ):
            observed = process.status(root)
        self.assertEqual(observed["state"], process.UNKNOWN)
        self.assertEqual(observed.get("proof_mode"), "NONE")

    def test_failed_child_cleans_matching_metadata(self):
        root = self._root("current")
        process._write_process_metadata(root, "current", 52092, "start-id")
        meta = root / "run/workspace-process.json"
        self.assertTrue(meta.exists())
        child = mock.Mock(pid=52092)
        child.poll.return_value = 0
        process._cleanup_own_spawn(child, "start-id", root, "current")
        self.assertFalse(meta.exists())

    def test_failed_child_leaves_nonmatching_metadata(self):
        root = self._root("current")
        process._write_process_metadata(root, "current", 99999, "other-id")
        meta = root / "run/workspace-process.json"
        child = mock.Mock(pid=52092)
        child.poll.return_value = 0
        process._cleanup_own_spawn(child, "start-id", root, "current")
        self.assertTrue(meta.exists())

    def test_start_readiness_diagnostic_includes_last_state(self):
        root = self._root("current")
        child = mock.Mock(pid=42)
        child.poll.return_value = None
        not_running = {"state": process.NOT_RUNNING}
        unknown = {"state": process.UNKNOWN, "reason": "wrong entrypoint", "proof_mode": "NONE"}
        with (
            mock.patch.object(process, "status", side_effect=[not_running] + [unknown] * 200),
            mock.patch.object(process, "_current_release", return_value="current"),
            mock.patch.object(process, "_require_p702_health"),
            mock.patch.object(process.subprocess, "run", return_value=mock.Mock(returncode=0)),
            mock.patch.object(process.subprocess, "Popen", return_value=child),
            mock.patch.object(process, "_process_start_identity", return_value="start"),
            mock.patch.object(process, "_write_process_metadata"),
            mock.patch.object(process, "_cleanup_own_spawn"),
            mock.patch("time.sleep"),
            mock.patch("time.monotonic", side_effect=[0.0, 1.0, 31.0] + [31.0] * 200),
            self.assertRaises(process.WorkspaceProcessError) as ctx,
        ):
            process.start(root)
        msg = str(ctx.exception)
        self.assertIn("state=UNKNOWN", msg)
        self.assertIn("reason=wrong entrypoint", msg)
        self.assertIn("proof_mode=NONE", msg)


class StartToStatusRegressionTests(unittest.TestCase):
    """P9.11-F06: real start() -> real status() parser regression."""

    def test_real_start_real_status_with_application_support_paths(self):
        temporary = tempfile.TemporaryDirectory()
        root = pathlib.Path(temporary.name) / "Library/Application Support/ArvectumOS/persistent-internal"
        release = "a" * 40
        source = root / "releases" / release / "source/reference/python"
        source.mkdir(parents=True)
        (root / "venvs" / release / "bin").mkdir(parents=True)
        python = root / "venvs" / release / "bin/python"
        python.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(python, 0o755)
        (source / "p9_03_workspace.py").touch()
        (source / "workspace_frontend/dist").mkdir(parents=True)
        (source / "workspace_frontend/dist/index.html").touch()
        (source / "workspace_app").mkdir()
        (source / "workspace_app/release.json").write_text(
            json.dumps({"release_id": "p9.11.3", "app_api_contract": 11})
        )
        root = root.resolve()
        source = root / "releases" / release / "source/reference/python"
        python = root / "venvs" / release / "bin/python"
        fw = root / "framework-python"
        fw.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fw, 0o755)
        fw_command = f"{fw} {source}/p9_03_workspace.py serve"
        child = mock.Mock(pid=52092)
        child.poll.return_value = None
        not_running = {"state": process.NOT_RUNNING}
        current_exact = {
            "state": process.CURRENT_EXACT,
            "pid": 52092,
            "release_sha": release,
            "proof_mode": "MANAGED_SPAWN_PROOF",
            "process_start_identity": "Tue Aug 25 09:50:00 2026",
        }
        with (
            mock.patch.object(process, "_current_release", return_value=release),
            mock.patch.object(process, "_require_p702_health"),
            mock.patch.object(process.subprocess, "run", return_value=mock.Mock(returncode=0)),
            mock.patch.object(process.subprocess, "Popen", return_value=child),
            mock.patch.object(
                process, "_process_start_identity",
                return_value="Tue Aug 25 09:50:00 2026",
            ),
            mock.patch.object(process, "_cleanup_own_spawn"),
            mock.patch.object(process, "_listener", return_value=(52092, "Python")),
            mock.patch.object(process, "_process_command", return_value=fw_command),
            mock.patch.object(process, "_process_cwd", return_value=source),
            mock.patch.object(process, "_live_assets_match", return_value=True),
            mock.patch.object(process.p706, "verify_release"),
            mock.patch("time.sleep"),
            mock.patch("time.monotonic", side_effect=[0.0, 1.0, 31.0] + [31.0] * 200),
            mock.patch.object(
                process, "status",
                side_effect=[not_running, current_exact],
            ),
        ):
            observed = process.start(root)
        self.assertEqual(observed["state"], process.CURRENT_EXACT)
        self.assertEqual(observed["proof_mode"], "MANAGED_SPAWN_PROOF")
        self.assertEqual(observed["pid"], 52092)
        meta = json.loads((root / "run/workspace-process.json").read_text())
        self.assertEqual(meta["pid"], 52092)
        self.assertEqual(meta["release_sha"], release)
        self.assertIn("Application Support", meta["requested_python"])
        temporary.cleanup()


class OwnerQueueLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name).resolve()
        (self.root / "config").mkdir(mode=0o700)
        self.path = self.root / "config/owner-project-queue-launch.json"
        self.release = "a"*40
        self.pin = "b"*64
        self.record = {"schema": "arvectum.workspace.owner-project-queue-launch/1",
                       "release_commit": self.release,
                       "contract_blob": process.OWNER_QUEUE_CONTRACT,
                       "policy_sha256": self.pin}
    def put(self):
        self.path.write_text(json.dumps(self.record))
        self.path.chmod(0o600)
    def test_default_off_no_policy_derived_pin(self):
        (self.root/"config/owner-project-queue-policy.json").write_text("{}")
        self.assertEqual(process._owner_queue_launch_args(self.root,self.release), [])
    def test_exact_launch_and_rollback(self):
        self.put()
        self.assertEqual(process._owner_queue_launch_args(self.root,self.release),
            ["--owner-queue-policy-sha256",self.pin,"--owner-queue-contract-blob",process.OWNER_QUEUE_CONTRACT])
        self.assertEqual(process._owner_queue_launch_args(self.root,"c"*40), [])
    def test_bad_contract(self):
        self.record["contract_blob"]="f"*40
        self.put()
        with self.assertRaises(process.WorkspaceProcessError):
            process._owner_queue_launch_args(self.root,self.release)
    def test_insecure_file(self):
        self.put()
        self.path.chmod(0o644)
        with self.assertRaises(process.WorkspaceProcessError):
            process._owner_queue_launch_args(self.root,self.release)
    def test_symlink(self):
        self.put()
        other=self.path.with_name("other.json")
        self.path.rename(other)
        self.path.symlink_to(other)
        with self.assertRaises(process.WorkspaceProcessError):
            process._owner_queue_launch_args(self.root,self.release)
    def test_exact_two_pin_suffix_and_no_extra_flags(self):
        self.put()
        python=self.root/"python"
        python.write_text("#!/bin/sh\n")
        python.chmod(0o700)
        entry=self.root/"p9_03_workspace.py"
        command=f"{python} {entry} serve "+" ".join(process._owner_queue_launch_args(self.root,self.release))
        self.assertTrue(process._process_identity(command,self.root,python,entry)[0])
        self.assertFalse(process._process_identity(command+" --extra",self.root,python,entry)[0])
        self.assertFalse(process._process_identity(command.replace(process.OWNER_QUEUE_CONTRACT,"f"*40),self.root,python,entry)[0])
