from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.actionable_work import (
    ActionableWorkError,
    ActionableWorkRequest,
    RuntimeActionableWorkProvider,
)
from workspace_app.config import WorkspaceSettings
from workspace_app.main import RELEASE_HEADER, create_app
from workspace_app.release import load_release


ORG = Identity("organization", "org-a", "platform")
ACTOR = Identity("principal", "owner", "org-a")


def access() -> AccessContext:
    return AccessContext(
        organization=ORG,
        actor=ACTOR,
        principal_kind="human",
        credential_id="credential-a",
        grant_id="grant-a",
    )


def key(identity: Identity) -> tuple[str, str, str]:
    return (identity.namespace, identity.value, identity.scope)


def request(**overrides: object) -> ActionableWorkRequest:
    values: dict[str, object] = {
        "organization_key": key(ORG),
        "actor_key": key(ACTOR),
        "source_kind": "product",
        "source_id": "tender-agent",
        "source_label": "Tender Agent",
        "request_ref": "tender-owner-disposition:0344100006426000005",
        "title": "Review a real Tender Agent result",
        "context": "The owning product reports a current result that requires an owner disposition.",
        "attention_reason": "The source explicitly reports that owner attention is required.",
        "source_state": "waiting-owner-disposition",
        "freshness": "fresh",
        "observed_at": datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc),
        "next_steps": ("Open the product-owned request context.", "Review source evidence before any governed effect."),
        "entry_href": "/products/tender-operator?request=opaque-ref",
        "source_authority": "Tender Agent product-owned request state; EIS remains externally authoritative for procurement facts",
        "product_contract_id": "TA-PC",
        "product_contract_version": "0.1.0",
        "product_contract_lifecycle": "Provisional",
        "preflight_state": "not-yet-evaluated-for-effect",
        "provenance_refs": ("product-request:opaque-ref", "product-release:0123456789abcdef0123456789abcdef01234567"),
    }
    values.update(overrides)
    return ActionableWorkRequest(**values)  # type: ignore[arg-type]


class StaticSource:
    def __init__(self, items: tuple[ActionableWorkRequest, ...]) -> None:
        self.items = items
        self.calls = 0

    def collect(self, current: AccessContext) -> tuple[ActionableWorkRequest, ...]:
        self.calls += 1
        self.last_access = current
        return self.items


class FailingSource:
    def collect(self, current: AccessContext) -> tuple[ActionableWorkRequest, ...]:
        del current
        raise RuntimeError("source unavailable")


class FakeResolver:
    def authorize(self) -> AccessContext:
        return access()


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


def client_for(root: Path, provider: RuntimeActionableWorkProvider) -> TestClient:
    static = root / "dist"
    static.mkdir(exist_ok=True)
    (static / "index.html").write_text("ok", encoding="utf-8")
    app = create_app(
        settings(root),
        access_resolver=FakeResolver(),
        actionable_work_provider=provider,
        static_dir=static,
    )
    return TestClient(app, base_url="http://127.0.0.1:8769", client=("127.0.0.1", 50000))


class ActionableWorkProjectionTests(unittest.TestCase):
    def test_default_runtime_has_no_sources_and_does_not_manufacture_work(self) -> None:
        payload = RuntimeActionableWorkProvider().project(access()).to_payload()
        self.assertEqual(payload["schema"], "arvectum.workspace.actionable-work/1")
        self.assertEqual(payload["items"], [])
        self.assertFalse(payload["projection"]["creates_requests"])
        self.assertFalse(payload["projection"]["universal_task_primitive"])
        self.assertFalse(payload["projection"]["canonical_authority"])
        self.assertFalse(payload["projection"]["urgency_inferred"])
        self.assertFalse(payload["projection"]["approval_requirement_inferred"])
        self.assertFalse(payload["projection"]["action_availability_inferred"])

    def test_real_source_request_is_projected_without_authority_or_effect(self) -> None:
        source = StaticSource((request(),))
        payload = RuntimeActionableWorkProvider((source,)).project(access()).to_payload()
        self.assertEqual(source.calls, 1)
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["title"], "Review a real Tender Agent result")
        self.assertEqual(item["source"]["request_ref"], "tender-owner-disposition:0344100006426000005")
        self.assertEqual(item["source"]["product_contract"]["lifecycle"], "Provisional")
        self.assertTrue(item["governed_execution"]["current_gate_revalidation_required_for_effect"])
        self.assertFalse(item["governed_execution"]["consequential_action_available"])
        self.assertFalse(item["governed_execution"]["organizational_authority_provided"])
        self.assertEqual(item["entry"]["kind"], "no-side-effect-context-entry")
        self.assertTrue(item["entry"]["available"])
        self.assertEqual(item["entry"]["href"], "/products/tender-operator?request=opaque-ref")
        self.assertFalse(item["entry"]["executes_product_operation"])
        self.assertFalse(item["entry"]["canonical_mutation_requested"])
        self.assertFalse(item["entry"]["external_effect_requested"])
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn('"urgency"', serialized)
        self.assertNotIn('"approved"', serialized.lower())

    def test_projection_identity_is_opaque_and_deterministic(self) -> None:
        first = request()
        second = request(title="Changed human-readable title")
        self.assertEqual(first.projection_id, second.projection_id)
        self.assertEqual(len(first.projection_id), 24)
        self.assertNotIn("0344100006426000005", first.projection_id)

    def test_stale_request_withholds_entry_but_preserves_truthful_context(self) -> None:
        item = request(freshness="stale")
        payload = RuntimeActionableWorkProvider((StaticSource((item,)),)).project(access()).to_payload()["items"][0]
        self.assertEqual(payload["source"]["freshness"], "stale")
        self.assertFalse(payload["entry"]["available"])
        self.assertIsNone(payload["entry"]["href"])
        self.assertEqual(payload["next_steps"], list(item.next_steps))

    def test_scope_mismatch_fails_closed(self) -> None:
        other = request(organization_key=("organization", "other", "platform"))
        with self.assertRaisesRegex(ActionableWorkError, "scope"):
            RuntimeActionableWorkProvider((StaticSource((other,)),)).project(access())

    def test_duplicate_source_identity_fails_closed(self) -> None:
        first = request(title="First")
        second = request(title="Second")
        with self.assertRaisesRegex(ActionableWorkError, "duplicate"):
            RuntimeActionableWorkProvider((StaticSource((first, second)),)).project(access())

    def test_missing_provenance_and_unsafe_entries_fail_closed(self) -> None:
        for item in (
            request(provenance_refs=()),
            request(entry_href="https://example.com/execute"),
            request(entry_href="/api/app/v1/unsafe"),
            request(entry_href="/governed?focus=fake"),
        ):
            with self.subTest(item=item.entry_href):
                with self.assertRaises(ActionableWorkError):
                    RuntimeActionableWorkProvider((StaticSource((item,)),)).project(access())

    def test_non_effective_contract_lifecycle_fails_closed(self) -> None:
        with self.assertRaisesRegex(ActionableWorkError, "effective Product Contract"):
            RuntimeActionableWorkProvider(
                (StaticSource((request(product_contract_lifecycle="Draft"),)),)
            ).project(access())

    def test_source_exception_fails_closed(self) -> None:
        with self.assertRaisesRegex(ActionableWorkError, "failed closed"):
            RuntimeActionableWorkProvider((FailingSource(),)).project(access())


class ActionableWorkBffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.provider = RuntimeActionableWorkProvider((StaticSource((request(),)),))
        self.client = client_for(self.root, self.provider)
        self.headers = {RELEASE_HEADER: load_release().release_id}
        boot = self.client.post(
            "/api/app/v1/session/bootstrap",
            headers={**self.headers, "Origin": "http://127.0.0.1:8769"},
        )
        self.assertEqual(boot.status_code, 200)

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def test_endpoint_requires_current_session(self) -> None:
        other_root = self.root / "other"
        other_root.mkdir()
        other = client_for(other_root, self.provider)
        try:
            response = other.get("/api/app/v1/actionable-work", headers=self.headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"], "SESSION_REQUIRED")
        finally:
            other.close()

    def test_endpoint_returns_read_only_projection(self) -> None:
        response = self.client.get("/api/app/v1/actionable-work", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        self.assertFalse(payload["projection"]["creates_requests"])
        self.assertFalse(payload["items"][0]["entry"]["executes_product_operation"])

    def test_source_failure_is_503_and_does_not_fall_back_to_synthetic_work(self) -> None:
        failing_root = self.root / "failing"
        failing_root.mkdir()
        failing = client_for(failing_root, RuntimeActionableWorkProvider((FailingSource(),)))
        try:
            boot = failing.post(
                "/api/app/v1/session/bootstrap",
                headers={**self.headers, "Origin": "http://127.0.0.1:8769"},
            )
            self.assertEqual(boot.status_code, 200)
            response = failing.get("/api/app/v1/actionable-work", headers=self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"], "ACTIONABLE_WORK_UNAVAILABLE")
        finally:
            failing.close()


if __name__ == "__main__":
    unittest.main()
