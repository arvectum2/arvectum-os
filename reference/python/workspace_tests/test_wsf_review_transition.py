import json,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from workspace_app.wsf_review_ticket import Ticket,digest
from workspace_app.wsf_review_transition import transition,admitted_bytes,validate_append
from workspace_app.wsf_manual_context import ManualContextError,_json
from review_ticket_fixture import Authority,Disk,sign,key,trust_for,ticket_for,NOW,EXP,atomic

class Company:
    """Minimal synthetic seam; actual Company writer tested separately."""
    @staticmethod
    def canonical(doc):return _json(doc)+b"\n"
    @staticmethod
    def replay(doc):return {e["record"]["id"]:e["record"] for e in doc["events"]}
def raw(records):
    kind="risk-exception-incident" if records[0]["id"].startswith("RSK") else "decision-approval-escalation"
    return Company.canonical({"schema":"arvectum.company."+kind+"-register/1","coverage":"partial","events":[{"at":NOW,"record":r} for r in records]})
def decision(rid):
    return {"id":rid,"decision_state":"decided","decision_outcome":"approve_with_conditions",
       "decision_authority":"Owner","accountable_position":"POS-001","effect_readiness":"blocked",
       "required_approval_refs":[],"decision_act_ref":"synthetic-act-"+rid}
def baseline():return [decision(k) for k in ("DEC-001","DEC-002","DEC-003","APR-001")]
def risk():
    return {"id":"RSK-002","risk_state":"active","risk_acceptance_decision_ref":None,
       "closure_ref":None,"owner_attention":"not_required","source_refs":["fixture"],
       "current_controls_refs":["fixture"],"next_control_point":"old","company_priority":"P1"}
@unittest.skipUnless(Path("/usr/bin/ssh-keygen").is_file(),"system verifier unavailable")
class ReviewedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.d=Path(self.temp.name).resolve();self.k=key(self.d)
        self.trust=trust_for(self.k,"decision")
        self.old=raw(baseline());self.new=raw(baseline()+[decision("DEC-004")])
        self.a=Authority(self.old);self.io=Disk(self.d/"disk",self.old);self.io.new=self.new
        self.t=ticket_for(self.trust,self.a.value,self.old,self.new,"DEC-004")
        self.sig=sign(self.d,self.k,self.t)
        self.now=NOW;self.act=True
    def run_t(self,t=None,sig=None):
        return transition(t or self.t,self.sig if sig is None else sig,trust=self.trust,authority=self.a,
           io=self.io,company=Company,verify_historical_act=lambda r:self.act,clock=lambda:self.now)
    def read(self):return admitted_bytes(trust=self.trust,authority=self.a,io=self.io,clock=lambda:self.now)
    def test_two_transitions_no_rebuild_and_old_ticket_replay(self):
        self.assertEqual(self.run_t(),"completed");self.assertEqual(self.run_t(),"already-completed")
        self.assertEqual(self.read(),self.new)
        old_t,old_sig=self.t,self.sig
        self.io.old=self.new;self.io.new=raw(baseline()+[decision("DEC-004"),decision("DEC-005")])
        self.t=ticket_for(self.trust,self.a.value,self.io.old,self.io.new,"DEC-005");self.sig=sign(self.d,self.k,self.t)
        self.assertEqual(self.run_t(),"completed");self.assertEqual(self.read(),self.io.new)
        with self.assertRaises(ManualContextError):self.run_t(old_t,old_sig)
        atomic(self.io.source,self.new);atomic(self.io.backup,self.new)
        with self.assertRaises(ManualContextError):self.read()
    def test_recovery_at_every_write_gate(self):
        for step in ("source","backup","archive","head"):
            self.io.interrupt=step;self.a.interrupt=step=="head"
            with self.assertRaises(OSError):self.run_t()
            with self.assertRaises(ManualContextError):self.read()
        self.io.interrupt=None;self.a.interrupt=False
        self.assertEqual(self.run_t(),"completed");self.assertEqual(self.read(),self.new)
    def test_forged_signature_namespace_and_scope(self):
        for sig in (b"bad",sign(self.d,self.k,self.t,"wrong-namespace")):
            with self.assertRaises(ManualContextError):self.run_t(sig=sig)
        t=replace(self.t,grant="other")
        with self.assertRaises(ManualContextError):self.run_t(t,sign(self.d,self.k,t))
        self.assertEqual(self.io.read_source(),self.old)
    def test_wrong_key_well_formed_signature(self):
        q=self.d/"other";q.mkdir();k=key(q)
        with self.assertRaises(ManualContextError):self.run_t(sig=sign(self.d,k,self.t))
    def test_expiry_and_revocation_before_or_during_write(self):
        self.now=EXP
        with self.assertRaises(ManualContextError):self.run_t()
        self.now=NOW;self.io.interrupt="source"
        with self.assertRaises(OSError):self.run_t()
        self.a.live=False;self.io.interrupt=None
        with self.assertRaises(ManualContextError):self.run_t()
        self.assertEqual(self.io.read_backup(),self.old)
    def test_revocation_after_completion_denies_read(self):
        self.run_t();self.a.live=False
        with self.assertRaises(ManualContextError):self.read()
    def test_unsigned_source_and_unverified_historical_act(self):
        self.act=False
        with self.assertRaises(ManualContextError):self.run_t()
        self.act=True;self.io.new=self.old
        with self.assertRaises(ManualContextError):self.run_t()
        self.assertIsNone(self.io.journal())
    def test_missing_journal_and_mixed_backup(self):
        atomic(self.io.backup,self.new)
        with self.assertRaises(ManualContextError):self.run_t()
        atomic(self.io.backup,self.old);atomic(self.io.source,self.new)
        with self.assertRaises(ManualContextError):self.run_t()
    def test_risk_field_boundary_and_provenance(self):
        base=[{**risk(),"id":"RSK-001"},risk(),{**risk(),"id":"RSK-003"}];old=raw(base);t=trust_for(self.k,"risk")
        for change in ({"risk_acceptance_decision_ref":"DEC-004"},{"company_priority":"P0"},{"source_refs":["replacement"]},{"closure_ref":"fake"}):
            new=raw(base+[{**risk(),**change}]);ticket=ticket_for(t,(0,"0"*64,digest(old)),old,new,"RSK-002")
            with self.assertRaises(ManualContextError):validate_append(ticket,old,new,Company,lambda r:True,NOW)
        new=raw(base+[{**risk(),"next_control_point":"reconciled"}])
        ticket=ticket_for(t,(0,"0"*64,digest(old)),old,new,"RSK-002")
        self.assertEqual(validate_append(ticket,old,new,Company,lambda r:True,NOW)["RSK-002"]["next_control_point"],"reconciled")
    def test_noncanonical_ticket_and_duplicate_fields(self):
        self.assertEqual(Ticket.decode(self.t.raw()),self.t)
        with self.assertRaises(ManualContextError):Ticket.decode(self.t.raw()+b" ")
    def test_repeat_risk_review_without_new_code(self):
        base=[{**risk(),"id":"RSK-001"},risk(),{**risk(),"id":"RSK-003"}]
        self.trust=trust_for(self.k,"risk");old=raw(base);self.a=Authority(old)
        self.io=Disk(self.d/"risk-disk",old)
        for note in ("first review","second review"):
            self.io.old=self.io.read_source()
            base.append({**base[-1],"id":"RSK-002","next_control_point":note})
            self.io.new=raw(base)
            self.t=ticket_for(self.trust,self.a.value,self.io.old,self.io.new,"RSK-002")
            self.sig=sign(self.d,self.k,self.t)
            self.assertEqual(self.run_t(),"completed")
            self.assertEqual(self.read(),self.io.new)
        self.assertEqual(self.a.value[0],2)
