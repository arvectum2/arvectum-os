"""Durable reviewer-side authority tests, all keys and records disposable."""
import tempfile,unittest
from pathlib import Path
from dataclasses import replace
from workspace_app.wsf_review_authority import ReviewAuthority
from workspace_app.wsf_review_transition import transition,admitted_bytes
from workspace_app.wsf_review_ticket import digest
from workspace_app.wsf_manual_context import ManualContextError
from review_ticket_fixture import Disk,key,sign,trust_for,ticket_for,NOW,EXP,atomic
from test_wsf_review_transition import Company,raw,baseline,decision

@unittest.skipUnless(Path("/usr/bin/ssh-keygen").is_file(),"system verifier unavailable")
class StoreTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.d=Path(t.name).resolve()
        self.k=key(self.d)
        self.trust=trust_for(self.k,"decision")
        self.old=raw(baseline());self.new=raw(baseline()+[decision("DEC-004")])
        self.db=self.d/"authority.sqlite"
        self.a=ReviewAuthority.initialize(self.db,self.trust,baseline=digest(self.old),authenticated_operator=self.trust.operator)
        self.t=ticket_for(self.trust,self.a.head("decision"),self.old,self.new,"DEC-004")
        self.sig=sign(self.d,self.k,self.t)
        self.io=Disk(self.d/"operator",self.old);self.io.new=self.new
    def reopen(self):
        self.a=ReviewAuthority(self.db,self.trust,authenticated_operator=self.trust.operator)
    def run_t(self):
        return transition(self.t,self.sig,trust=self.trust,authority=self.a,io=self.io,company=Company,verify_historical_act=lambda r:True,clock=lambda:NOW)
    def read(self):return admitted_bytes(trust=self.trust,authority=self.a,io=self.io,clock=lambda:NOW)
    def test_durable_reservation_and_competing_ticket(self):
        self.a.reserve(self.trust,self.t,self.sig,NOW);self.reopen()
        self.a.reserve(self.trust,self.t,self.sig,NOW)
        alt=replace(self.t,successor="8"*64)
        with self.assertRaises(ManualContextError):self.a.reserve(self.trust,alt,sign(self.d,self.k,alt),NOW)
        with self.assertRaises(ManualContextError):self.a.read_head("decision")
        self.assertEqual(self.run_t(),"completed")
        self.reopen();self.assertEqual(self.read(),self.new)
    def test_sequential_transition_reopen_and_rollback_denial(self):
        self.run_t();self.reopen()
        old_t,old_sig=self.t,self.sig
        self.io.old=self.new;self.io.new=raw(baseline()+[decision("DEC-004"),decision("DEC-005")])
        self.t=ticket_for(self.trust,self.a.head("decision"),self.io.old,self.io.new,"DEC-005")
        self.sig=sign(self.d,self.k,self.t)
        self.run_t();self.reopen()
        self.assertEqual(self.a.head("decision")[0],2)
        with self.assertRaises(ManualContextError):self.a.reserve(self.trust,old_t,old_sig,NOW)
        atomic(self.io.source,self.new);atomic(self.io.backup,self.new)
        with self.assertRaises(ManualContextError):self.read()
    def test_partial_append_resume_after_reopen(self):
        self.io.interrupt="source"
        with self.assertRaises(OSError):self.run_t()
        self.reopen()
        with self.assertRaises(ManualContextError):self.read()
        self.io.interrupt=None
        self.assertEqual(self.run_t(),"completed")
        self.assertEqual(self.read(),self.new)
    def test_revocation_persists_and_no_reset(self):
        self.a.reserve(self.trust,self.t,self.sig,NOW);self.a.revoke();self.reopen()
        with self.assertRaises(ManualContextError):self.run_t()
        with self.assertRaises(FileExistsError):ReviewAuthority.initialize(self.db,self.trust,baseline=digest(self.old),authenticated_operator=self.trust.operator)
        self.assertEqual(self.io.read_source(),self.old)
    def test_tamper_wrong_identity_and_missing_authority(self):
        with self.assertRaises(ManualContextError):ReviewAuthority(self.db,self.trust,authenticated_operator="other")
        with self.assertRaises(ManualContextError):self.a.reserve(self.trust,self.t,b"bad",NOW)
        with self.assertRaises(ManualContextError):self.a.reserve(self.trust,self.t,self.sig,EXP)
        self.db.chmod(0o644)
        with self.assertRaises(ManualContextError):self.a.head("decision")
        self.db.chmod(0o600);self.db.unlink()
        with self.assertRaises(FileNotFoundError):self.a.head("decision")
        self.assertFalse(self.db.exists())

    def test_rpc_commit_requires_reservation_and_uses_server_clock(self):
        from workspace_app.wsf_review_rpc import RemoteAuthority,dispatch
        from workspace_app.wsf_manual_context import _json
        remote=RemoteAuthority(self.trust,lambda raw:dispatch(raw,store=self.a,clock=lambda:NOW))
        old=remote.head("decision");new=(self.t.sequence,self.t.id(),self.t.successor)
        with self.assertRaises(ManualContextError):
            remote.compare_and_set("decision",old,new,self.trust,self.t,self.sig,NOW)
        self.assertEqual(remote.head("decision"),old)
        for op in ("revoke","initialize","sign","reset"):
            with self.assertRaises(ManualContextError):
                dispatch(_json({"operation":op,"register":"decision"}),store=self.a,clock=lambda:NOW)
        with self.assertRaises(ManualContextError):
            dispatch(_json({"operation":"head","register":"decision","clock":NOW}),store=self.a,clock=lambda:NOW)
        expired=RemoteAuthority(self.trust,lambda raw:dispatch(raw,store=self.a,clock=lambda:EXP))
        with self.assertRaises(ManualContextError):expired.reserve(self.trust,self.t,self.sig,NOW)
        self.assertEqual(transition(self.t,self.sig,trust=self.trust,authority=remote,io=self.io,company=Company,
            verify_historical_act=lambda r:True,clock=lambda:NOW),"completed")
        self.assertEqual(remote.read_head("decision"),new)

    def test_rpc_unavailable_does_not_fall_back_to_stale_cache(self):
        from workspace_app.wsf_review_rpc import RemoteAuthority,dispatch
        self.run_t()
        def outage(raw):raise TimeoutError()
        remote=RemoteAuthority(self.trust,outage)
        with self.assertRaises(ManualContextError):
            admitted_bytes(trust=self.trust,authority=remote,io=self.io,clock=lambda:NOW)

    def test_reservation_survives_failure_before_local_journal(self):
        from unittest.mock import patch
        with patch.object(self.io,"begin",side_effect=OSError("after reservation")):
            with self.assertRaises(OSError):self.run_t()
        self.assertIsNone(self.io.journal())
        self.assertEqual(self.io.read_source(),self.old)
        self.reopen()
        with self.assertRaises(ManualContextError):self.a.read_head("decision")
        self.assertEqual(self.run_t(),"completed")
        self.assertEqual(self.read(),self.new)
