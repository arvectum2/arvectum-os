import pathlib
import subprocess
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = HERE / "p7_06_macos_deploy.sh"
PROOF = HERE / "p7_06_selected_mac_proof.sh"

class ShellTests(unittest.TestCase):
    def test_deploy_shell_syntax(self):
        subprocess.run(["sh", "-n", str(DEPLOY)], check=True)

    def test_current_canonical_repository_guard_and_target_manifest(self):
        text = DEPLOY.read_text()
        self.assertIn('CANONICAL_REPOSITORY="arvectum2/arvectum-os"', text)
        self.assertIn('"https://github.com/$CANONICAL_REPOSITORY"', text)
        self.assertIn('https://*@github.com/"$CANONICAL_REPOSITORY"', text)
        self.assertNotIn('*github.com/', text)
        self.assertNotIn('github.com/arvectum/arvectum-os', text)
        self.assertIn('"canonical_repository":"$CANONICAL_REPOSITORY"', text)

    def test_p702_activation_uses_the_same_current_repository_identity(self):
        text = (HERE / "p7_02_macos_service.sh").read_text()
        self.assertIn('CANONICAL_REPOSITORY="arvectum2/arvectum-os"', text)
        self.assertIn('https://*@github.com/"$CANONICAL_REPOSITORY"', text)
        self.assertNotIn('*github.com/', text)
        self.assertNotIn('github.com/arvectum/arvectum-os', text)
        self.assertIn('"canonical_repository":"$CANONICAL_REPOSITORY"', text)

    def test_proof_shell_syntax(self):
        subprocess.run(["sh", "-n", str(PROOF)], check=True)

    def test_no_network_client_or_remote_transport(self):
        text = DEPLOY.read_text()
        for token in ("curl ", "wget ", "ssh ", "scp ", "nc "):
            self.assertNotIn(token, text)

    def test_r22_and_governed_sequence_guards_present(self):
        text = DEPLOY.read_text()
        self.assertIn("R22_SHA=", text)
        update_start = text.index("update_runtime()")
        update_end = text.index("rollback_last()", update_start)
        update = text[update_start:update_end]
        self.assertLess(
            update.index('backup_preupdate "$source"'),
            update.index('sh "$P705" uninstall'),
        )
        self.assertIn("compatibility/migration preflight rejected target", text)
        self.assertIn("rollback_and_record_failure", text)
        self.assertIn("restore_plist_and_start", text)

    def test_sibling_shell_adapters_do_not_require_executable_git_mode(self):
        text = DEPLOY.read_text()
        self.assertNotIn('\n  "$P702" ', text)
        self.assertNotIn('\n  "$P705" ', text)
        self.assertNotIn('if ! "$P702" ', text)
        self.assertNotIn('if ! "$P705" ', text)
        self.assertIn('sh "$P702" status', text)
        self.assertIn('sh "$P702" stop', text)
        self.assertIn('sh "$P702" install', text)
        self.assertIn('sh "$P705" status', text)
        self.assertIn('sh "$P705" uninstall', text)
        self.assertIn('sh "$P705" install', text)

    def test_release_python_command_substitution_is_space_safe(self):
        text = DEPLOY.read_text()
        self.assertNotIn('output=$($py ', text)
        self.assertIn(
            'output=$("$py" "$durable" backup --runtime-root "$RUNTIME_ROOT" --release-sha "$rel")',
            text,
        )
        self.assertIn(
            'RUNTIME_ROOT=${ARVECTUM_P7_02_ROOT:-"$HOME/Library/Application Support/ArvectumOS/persistent-internal"}',
            text,
        )

    def test_first_r22_upgrade_admits_only_exact_proven_legacy_observer_shape(self):
        text = DEPLOY.read_text()
        self.assertIn(
            'P705_LEGACY_PROVEN_SHA="cf60e52c93bf0ef4158cf2c3e26792850a126c70"',
            text,
        )
        self.assertIn('verify_source_observer_preupdate "$source"', text)
        self.assertIn('rel" = "$P705_LEGACY_PROVEN_SHA', text)
        self.assertIn('payload.get("ProgramArguments") != expected', text)
        self.assertIn(
            "pre-R22 observer plist does not match the exact historically proven P7.05 shape",
            text,
        )
        self.assertIn("source observer legacy R22 carry-forward status PASS", text)

    def test_update_requires_runtime_lock_quiescence_before_target_install(self):
        text = DEPLOY.read_text()
        stop = text.index('if ! sh "$P702" stop; then rollback_and_record_failure "source runtime did not stop"; fi')
        quiescent = text.index('wait_runtime_quiescent || rollback_and_record_failure')
        install = text.index('if ! sh "$P702" install')
        self.assertLess(stop, quiescent)
        self.assertLess(quiescent, install)
        self.assertIn("fcntl.LOCK_EX | fcntl.LOCK_NB", text)
        self.assertIn("source runtime process did not quiesce after stop", text)

    def test_failure_rollback_reuses_bounded_lifecycle_adapters(self):
        text = DEPLOY.read_text()
        restore_start = text.index("restore_plist_and_start()")
        restore_end = text.index("backup_preupdate()", restore_start)
        restore = text[restore_start:restore_end]
        self.assertNotIn('launchctl bootout "$RUNTIME_TARGET"', restore)
        self.assertNotIn('launchctl bootout "$OBSERVER_TARGET"', restore)
        self.assertIn('sh "$P705" uninstall', restore)
        self.assertIn('sh "$P702" stop', restore)
        self.assertIn('wait_runtime_quiescent', restore)
        self.assertIn("rollback runtime process did not release the single-instance lock", restore)

    def test_pre_activation_workspace_stop_failure_records_fail_without_rollback(self):
        text = DEPLOY.read_text()
        failure_start = text.index("record_pre_activation_stop_failure()")
        failure_end = text.index("preflight()", failure_start)
        failure = text[failure_start:failure_end]
        update_start = text.index("update_runtime()")
        update_end = text.index("rollback_last()", update_start)
        update = text[update_start:update_end]
        self.assertIn('write_payload "$payload" "$plan_id" "$source" "$target" FAIL', failure)
        self.assertIn("target activation never began", failure)
        self.assertIn("current pointer unchanged", failure)
        self.assertIn("post_stop_state=not_queried_after_stop_failure", failure)
        self.assertIn("signal_disposition=unknown_to_adapter", failure)
        self.assertNotIn("not_queried_after_signal", failure)
        self.assertNotIn("workspace_status", failure)
        self.assertNotIn("rollback_and_record_failure", failure)
        self.assertIn('workspace_stop_for_update >/dev/null || record_pre_activation_stop_failure', update)
        self.assertLess(update.index("workspace_stop_for_update"), update.index('sh "$P705" uninstall'))

    def test_interrupted_recovery_is_exact_source_and_effect_free(self):
        text = DEPLOY.read_text()
        self.assertIn("recover_interrupted_latest()", text)
        self.assertIn('root.glob("work-*")', text)
        self.assertIn('payload.get("Label") != expected_label', text)
        self.assertIn('args.index("--release-sha")', text)
        self.assertIn('restore_plist_and_start "$txdir" "$source"', text)
        self.assertIn('"durable_backup_restored": False', text)
        self.assertIn('"canonical_mutation_performed_by_recovery": False', text)
        self.assertIn('"product_external_effect_invoked": False', text)
        self.assertIn('"historical_effect_replay_invoked": False', text)
        self.assertIn('recover-interrupted-latest) recover_interrupted_latest', text)

    def test_rollback_reinstalls_safe_exact_observer_instead_of_unsafe_legacy_plist(self):
        text = DEPLOY.read_text()
        self.assertNotIn('cp "$old_observer" "$OBSERVER_PLIST"', text)
        self.assertIn(
            'if ! sh "$P705" install >/dev/null; then fail "rollback observer exact-release re-pin failed"; fi',
            text,
        )
        self.assertIn(
            'if ! sh "$P705" status >/dev/null; then fail "rollback observer exact-release verification failed"; fi',
            text,
        )

    def test_selected_mac_proof_orders_update_rollback_reupdate(self):
        text = PROOF.read_text()
        self.assertLess(text.index('update "$DECISION_REF:update"'), text.index("rollback-last"))
        self.assertLess(text.index("rollback-last"), text.index('update "$DECISION_REF:final-update"'))
        self.assertIn("historical_effect_replay_invoked", text)
        self.assertIn("product_external_effect_invoked", text)

    def test_selected_mac_proof_does_not_require_executable_git_mode(self):
        text = PROOF.read_text()
        self.assertIn('sh "$DEPLOY" update "$DECISION_REF:update"', text)
        self.assertIn('sh "$DEPLOY" rollback-last', text)
        self.assertIn('sh "$DEPLOY" update "$DECISION_REF:final-update"', text)
        self.assertIn('sh "$DEPLOY" status', text)

    def test_selected_mac_proof_retains_digest_sidecar(self):
        text = PROOF.read_text()
        self.assertIn('> "$summary.sha256"', text)
        self.assertIn('chmod 600 "$summary.sha256"', text)

class WorkspaceDependencyTests(unittest.TestCase):
    def _deploy_text(self):
        return DEPLOY.read_text()

    def test_ensure_workspace_runtime_dependencies_exists(self):
        self.assertIn("ensure_workspace_runtime_dependencies()", self._deploy_text())

    def test_uses_workspace_app_requirements_lock(self):
        self.assertIn("workspace_app/requirements.lock", self._deploy_text())

    def test_hashes_lock_with_sha256(self):
        text = self._deploy_text()
        self.assertIn("shasum -a 256", text)
        self.assertIn("lock_sha", text)
        self.assertIn('$(shasum -a 256 "$lock" | awk', text)

    def test_stamp_semantics(self):
        text = self._deploy_text()
        self.assertIn('.workspace-requirements.sha256', text)
        self.assertIn('stamp="$venv/.workspace-requirements.sha256"', text)
        self.assertIn('installed_sha=$(cat "$stamp")', text)

    def test_install_uses_venv_python(self):
        text = self._deploy_text()
        self.assertIn('"$venv/bin/python" -m pip install', text)

    def test_install_uses_requirements_lock_file(self):
        text = self._deploy_text()
        self.assertIn('-r "$lock"', text)

    def test_install_failure_is_fail_closed(self):
        text = self._deploy_text()
        self.assertIn("workspace runtime dependency install failed for exact target release", text)

    def test_fastapi_and_uvicorn_are_verified(self):
        text = self._deploy_text()
        self.assertIn("import fastapi", text)
        self.assertIn("import uvicorn", text)
        self.assertIn("workspace runtime dependency verification failed for exact target release", text)

    def test_prepare_target_calls_helper_after_venv_creation(self):
        text = self._deploy_text()
        prepare_start = text.index("prepare_target()")
        prepare_end = text.index("\ncurrent_release()", prepare_start)
        prepare_body = text[prepare_start:prepare_end]
        self.assertIn("if [ ! -x \"$venv/bin/python\" ]; then python3 -m venv \"$venv\"; fi", prepare_body)
        self.assertIn('ensure_workspace_runtime_dependencies "$release" "$venv"', prepare_body)
        venv_line = prepare_body.index('if [ ! -x "$venv/bin/python" ]')
        helper_line = prepare_body.index('ensure_workspace_runtime_dependencies "$release" "$venv"')
        self.assertLess(venv_line, helper_line)

    def test_missing_lock_is_noop(self):
        text = self._deploy_text()
        self.assertIn('[ -f "$lock" ] || return 0', text)

    def test_stamp_written_only_after_successful_install(self):
        text = self._deploy_text()
        install_pos = text.index('pip install \\\n')
        stamp_pos = text.index('mv "$tmp_stamp" "$stamp"')
        self.assertLess(install_pos, stamp_pos)

    def test_atomic_stamp_update(self):
        text = self._deploy_text()
        self.assertIn('tmp_stamp="$stamp.tmp.$$"', text)
        self.assertIn('mv "$tmp_stamp" "$stamp"', text)
        self.assertIn('chmod 600 "$tmp_stamp"', text)

    def test_no_credentials_in_source(self):
        text = self._deploy_text()
        for token in ("password=", "token=", "api_key=", "secret="):
            self.assertNotIn(token, text)

    def test_no_new_network_transports(self):
        text = self._deploy_text()
        for token in ("curl ", "wget ", "ssh ", "scp ", "nc "):
            self.assertNotIn(token, text)

    def test_venv_isolation_per_release(self):
        text = self._deploy_text()
        self.assertIn('venv="$RUNTIME_ROOT/venvs/$target"', text)

    def test_preserves_preexisting_deploy_invariants(self):
        text = self._deploy_text()
        self.assertIn("restore_plist_and_start", text)
        self.assertIn("rollback_and_record_failure", text)
        self.assertIn("backup_preupdate", text)
        self.assertIn("acquire_lock", text)

if __name__ == "__main__":
    unittest.main()
