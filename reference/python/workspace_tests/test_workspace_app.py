from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from arvectum_os_ref.identity import Identity
import p7_04_persistent_access as p704
from workspace_app.access import AccessContext, P704AccessResolver, WORKSPACE_OPERATION, WORKSPACE_RESOURCE, WorkspaceAccessError
from workspace_app.config import WorkspaceSettings
from workspace_app.main import CSRF_HEADER, RELEASE_HEADER, create_app
from workspace_app.release import load_release


class FakeResolver:
    def __init__(self) -> None:
        self.denied = False
        self.organization = Identity("organization", "org-a", "platform")
        self.actor = Identity("principal", "actor-a", "org-a")

    def authorize(self) -> AccessContext:
        if self.denied:
            raise WorkspaceAccessError("revoked for test")
        return AccessContext(
            organization=self.organization,
            actor=self.actor,
            principal_kind="human",
            credential_id="credential-test",
            grant_id="grant-test",
        )


def settings(root: Path) -> WorkspaceSettings:
    return WorkspaceSettings(
        runtime_root=root,
        public_origin="http://127.0.0.1:8769",
        bind_host="127.0.0.1",
        bind_port=8769,
        allowed_hosts=("127.0.0.1:8769",),
        organization_label="ООО «Арвектум»",
        actor_label="Owner operator",
        session_idle_seconds=60,
        session_absolute_seconds=300,
        allow_loopback_http=True,
    )


class WorkspaceBffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.resolver = FakeResolver()
        self.static = self.root / "dist"
        self.static.mkdir()
        (self.static / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
        assets = self.static / "assets"
        assets.mkdir()
        (assets / "app-abcdef.js").write_text("console.log('test')", encoding="utf-8")
        self.app = create_app(settings(self.root), access_resolver=self.resolver, static_dir=self.static)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8769", client=("127.0.0.1", 50000))
        self.release = load_release().release_id
        self.headers = {RELEASE_HEADER: self.release}

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def bootstrap(self):
        return self.client.post(
            "/api/app/v1/session/bootstrap",
            headers={**self.headers, "Origin": "http://127.0.0.1:8769"},
        )

    def test_positive_shell_context_is_server_resolved_and_minimized(self) -> None:
        response = self.bootstrap()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["organization"]["label"], "ООО «Арвектум»")
        self.assertTrue(payload["organization"]["scope_resolved_server_side"])
        self.assertEqual(payload["actor"]["label"], "Owner operator")
        self.assertTrue(payload["actor"]["attributable"])
        self.assertFalse(payload["session"]["authority_provided"])
        self.assertEqual(payload["data_governance"]["response_minimized"], "shell-context-only")
        serialized = json.dumps(payload)
        self.assertNotIn("org-a", serialized)
        self.assertNotIn("actor-a", serialized)
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertNotIn("Domain=", cookie)
        self.assertNotIn("Secure", cookie)

    def test_shell_navigation_is_owner_oriented_and_release_scoped(self) -> None:
        payload = self.bootstrap().json()
        self.assertEqual(payload["release"]["id"], "p10.09.3")
        self.assertEqual(payload["release"]["app_api_contract"], "15")
        self.assertEqual(
            [(item["id"], item["href"]) for item in payload["navigation"]],
            [
                ("today", "/"),
                ("work", "/work"),
                ("information", "/information"),
                ("copilot", "/copilot"),
                ("system", "/system"),
            ],
        )

    def test_browser_cannot_override_organization_or_actor(self) -> None:
        self.bootstrap()
        response = self.client.get(
            "/api/app/v1/context?organization=evil-org&actor=evil-actor",
            headers={**self.headers, "X-Organization": "evil-org", "X-Actor": "evil-actor"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["organization"]["label"], "ООО «Арвектум»")
        self.assertEqual(payload["actor"]["label"], "Owner operator")
        self.assertNotIn("evil-org", json.dumps(payload))

    def test_protected_read_revalidates_current_access_and_revokes_session(self) -> None:
        self.assertEqual(self.bootstrap().status_code, 200)
        self.resolver.denied = True
        self.assertEqual(self.client.get("/api/app/v1/context", headers=self.headers).status_code, 403)
        self.resolver.denied = False
        self.assertEqual(self.client.get("/api/app/v1/context", headers=self.headers).status_code, 401)

    def test_context_binding_change_fails_closed(self) -> None:
        self.assertEqual(self.bootstrap().status_code, 200)
        self.resolver.actor = Identity("principal", "actor-b", "org-a")
        denied = self.client.get("/api/app/v1/context", headers=self.headers)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["detail"], "CONTEXT_CHANGED")

    def test_host_origin_release_and_csrf_fail_closed(self) -> None:
        bad_host = self.client.get("/api/app/v1/context", headers={**self.headers, "Host": "attacker.invalid"})
        self.assertEqual(bad_host.status_code, 400)
        bad_origin = self.client.post(
            "/api/app/v1/session/bootstrap",
            headers={**self.headers, "Origin": "https://attacker.invalid"},
        )
        self.assertEqual(bad_origin.status_code, 403)
        stale = self.client.get("/api/app/v1/context", headers={RELEASE_HEADER: "stale-client"})
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(stale.json()["reload_required"])

        context = self.bootstrap().json()
        missing_csrf = self.client.post(
            "/api/app/v1/session/logout",
            headers={**self.headers, "Origin": "http://127.0.0.1:8769"},
        )
        self.assertEqual(missing_csrf.status_code, 403)
        valid = self.client.post(
            "/api/app/v1/session/logout",
            headers={**self.headers, "Origin": "http://127.0.0.1:8769", CSRF_HEADER: context["session"]["csrf_token"]},
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(self.client.get("/api/app/v1/context", headers=self.headers).status_code, 401)

    def test_cache_and_browser_security_headers(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertIn("default-src 'self'", page.headers["content-security-policy"])
        asset = self.client.get("/assets/app-abcdef.js")
        self.assertEqual(asset.status_code, 200)
        self.assertIn("immutable", asset.headers["cache-control"])


class P704ResolverIntegrationTests(unittest.TestCase):
    def test_real_p704_access_is_exact_and_server_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            organization = Identity("organization", "org-real", "platform")
            actor = Identity("principal", "owner-human", "org-real")
            p704.initialize_access_store(root, organization)
            p704.register_principal(root, actor, kind="human")
            credential = p704.issue_credential(root, actor)
            with self.assertRaises(WorkspaceAccessError):
                P704AccessResolver(root).authorize()
            p704.grant_access(
                root,
                actor,
                operation=WORKSPACE_OPERATION,
                resource=WORKSPACE_RESOURCE,
                access_paths=("local",),
            )
            resolved = P704AccessResolver(root).authorize()
            self.assertEqual(resolved.organization, organization)
            self.assertEqual(resolved.actor, actor)
            self.assertEqual(resolved.credential_id, credential["credential_id"])
            self.assertEqual(resolved.principal_kind, "human")


if __name__ == "__main__":
    unittest.main()
