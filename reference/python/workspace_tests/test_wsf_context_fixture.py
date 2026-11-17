from dataclasses import replace
from datetime import datetime, timezone, timedelta
import unittest

from arvectum_os_ref.identity import Identity
from workspace_app.access import AccessContext
from workspace_app.wsf_context_fixture import ContextError, FixtureContext, SourceBinding, SourceRef


def access(org="fixture-company", actor="fixture-owner", kind="human"):
    return AccessContext(Identity("org", org, "local"), Identity("actor", actor, org), kind, "fixture", "fixture")


NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


class ContextFixtureTests(unittest.TestCase):
    def setUp(self):
        self.access = access()
        scope = (("org", "fixture-company", "local"), ("actor", "fixture-owner", "fixture-company"))
        self.binding = SourceBinding("fixture-a", "fixture-roadmap", scope, "fixture", "fixture", "memory-only", "synthetic")
        self.context = FixtureContext(self.access, (self.binding, replace(self.binding, binding_id="fixture-b")), frozenset({"PORT-001"}))
        self.project = self.context.create_workstream(self.access, "Synthetic customer project", "customer", parent_port="PORT-001")
        self.ref = SourceRef("fixture-a", "source-1", "r1", "a"*64, NOW)

    def receive(self):
        return self.context.receive(self.access, self.ref, "Synthetic observation")

    def test_stable_independent_workstream_identity(self):
        other = self.context.create_workstream(self.access, self.project.label, "customer")
        self.assertTrue(self.project.id.startswith("PRJ-"))
        self.assertNotEqual(self.project.id, other.id)
        with self.assertRaises(ContextError):
            self.context.create_workstream(self.access, "Other", "internal", parent_port="PORT-099")

    def test_replay_no_duplicate_and_no_change_of_observed_time(self):
        first = self.receive()
        second = self.context.receive(self.access, replace(self.ref, observed_at=NOW+timedelta(hours=1)), first.title)
        self.assertEqual(first, second)
        self.assertEqual(self.context.inbox(self.access), (first,))

    def test_same_revision_conflict(self):
        first = self.receive()
        for ref, title in [(replace(self.ref, digest="b"*64), first.title), (self.ref, "Different title")]:
            with self.assertRaises(ContextError):
                self.context.receive(self.access, ref, title)
        self.assertEqual(self.context.inbox(self.access), (first,))

    def test_revision_requires_exact_predecessor(self):
        first = self.receive()
        with self.assertRaises(ContextError):
            self.context.receive(self.access, replace(self.ref, revision="r2"), "Changed")
        second = self.context.receive(self.access, replace(self.ref, revision="r2", digest="b"*64, predecessor_revision="r1"), "Changed")
        self.assertEqual(self.context.inbox(self.access), (second,))
        self.assertEqual(self.receive(), first)
        with self.assertRaises(ContextError):
            self.context.receive(self.access, replace(self.ref, revision="r3", predecessor_revision="r1"), "Stale")
        self.assertEqual(self.context.inbox(self.access), (second,))

    def test_distinct_binding_dedup_namespaces(self):
        first = self.receive()
        second = self.context.receive(self.access, replace(self.ref, binding_id="fixture-b"), first.title)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(self.context.inbox(self.access)), 2)

    def test_unknown_binding_failure(self):
        with self.assertRaises(ContextError):
            self.context.receive(self.access, replace(self.ref, binding_id="missing"), "Observation")
        self.assertEqual(self.context.inbox(self.access), ())

    def test_org_actor_and_nonhuman_access_isolated(self):
        item = self.receive()
        for other in (access(org="other-org"), access(actor="other-actor"), access(kind="ai")):
            for operation in (lambda: self.context.inbox(other), lambda: self.context.timeline(other, self.project.id),
                              lambda: self.context.receive(other, self.ref, item.title),
                              lambda: self.context.propose_link(other, item.id, self.project.id, NOW)):
                with self.assertRaises(ContextError):
                    operation()

    def test_link_proposal_not_confirmation(self):
        item = self.receive()
        self.context.propose_link(self.access, item.id, self.project.id, NOW)
        self.assertEqual(self.context.timeline(self.access, self.project.id), ())
        self.context.review_link(self.access, item.id, self.project.id, "confirmed", NOW)
        self.assertEqual(self.context.timeline(self.access, self.project.id), (item,))
        self.context.review_link(self.access, item.id, self.project.id, "superseded", NOW)
        self.assertEqual(self.context.timeline(self.access, self.project.id), ())

    def test_unknown_endpoint_or_invalid_transition(self):
        item = self.receive()
        with self.assertRaises(ContextError):
            self.context.propose_link(self.access, item.id, "PRJ-missing", NOW)
        with self.assertRaises(ContextError):
            self.context.review_link(self.access, item.id, self.project.id, "confirmed", NOW)
        self.context.propose_link(self.access, item.id, self.project.id, NOW)
        self.context.review_link(self.access, item.id, self.project.id, "rejected", NOW)
        with self.assertRaises(ContextError):
            self.context.review_link(self.access, item.id, self.project.id, "confirmed", NOW)

    def test_new_revision_requires_fresh_link_review(self):
        item = self.receive()
        self.context.propose_link(self.access, item.id, self.project.id, NOW)
        self.context.review_link(self.access, item.id, self.project.id, "confirmed", NOW)
        self.context.receive(self.access, replace(self.ref, revision="r2", predecessor_revision="r1", digest="c"*64), "Updated")
        self.assertEqual(self.context.timeline(self.access, self.project.id), ())

    def test_revoked_source_suppresses_items_and_links(self):
        item = self.receive()
        self.context.propose_link(self.access, item.id, self.project.id, NOW)
        self.context.review_link(self.access, item.id, self.project.id, "confirmed", NOW)
        self.context.revoke_fixture_source(self.access, self.ref.binding_id)
        self.assertEqual(self.context.inbox(self.access), ())
        self.assertEqual(self.context.timeline(self.access, self.project.id), ())
        with self.assertRaises(ContextError):
            self.receive()

    def test_reject_unversioned_or_naive_source_metadata(self):
        for kwargs in ({"revision":""}, {"digest":"x"}, {"observed_at": NOW.replace(tzinfo=None)}, {"predecessor_revision":"r1"}):
            with self.assertRaises(ContextError):
                replace(self.ref, **kwargs)

    def test_reject_foreign_binding(self):
        foreign = replace(self.binding, scope=(self.binding.scope[0], ("actor","other","fixture-company")))
        with self.assertRaises(ContextError):
            FixtureContext(self.access, (foreign,), frozenset())
