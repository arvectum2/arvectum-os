"""Candidate forward-only transaction protocol; no live I/O or entrypoint.

An operator must independently verify Company approval, effective OS contract,
external backup volume, quiescence and exclusive lock. Authenticated plan
is not derived from candidate source text.
"""
from dataclasses import dataclass
import re
from .wsf_manual_context import ManualContextError,_json

STEPS=("source","backup","policy","receipt")

@dataclass(frozen=True)
class Plan:
    predecessor:str
    successor:str
    policy:str
    receipt:str
    old_policy:str
    old_receipt:str
    decision:str
    contract:str

    def __post_init__(self):
        for value in (self.predecessor,self.successor,self.policy,self.receipt,self.old_policy,self.old_receipt):
            if not isinstance(value,str) or not re.fullmatch(r"[a-f0-9]{64}",value):
                raise ManualContextError("invalid exact digest")
        if self.predecessor==self.successor:
            raise ManualContextError("successor must differ")
        if not isinstance(self.contract,str) or not re.fullmatch(r"[a-f0-9]{40}",self.contract):
            raise ManualContextError("invalid contract pin")
        if not isinstance(self.decision,str) or not re.fullmatch(r"OWNER-[A-Z0-9-]{4,154}",self.decision):
            raise ManualContextError("invalid decision reference")

    def journal(self):
        return _json({"schema":"arvectum.workspace.ac401-cutover-candidate/1",
             **self.__dict__})

    def phase(self,observed):
        before=(self.predecessor,self.predecessor,None,None)
        after=(self.successor,self.successor,self.policy,self.receipt)
        if not isinstance(observed,dict) or set(observed)!=set(STEPS):
            raise ManualContextError("invalid observation")
        value=tuple(observed[k] for k in STEPS)
        for n in range(5):
            if value==after[:n]+before[n:]:return n
        raise ManualContextError("unexpected partial state")

def advance(plan,io):
    """Resume exact approved transaction. Never roll back Company history."""
    steps=getattr(plan,"steps",STEPS)
    count=len(steps)
    with io.exclusive():
        io.preflight(plan)
        saved=io.read_journal()
        phase=plan.phase(io.observe())
        if saved is None:
            if phase==count:
                io.verify_final(plan)
                return "already-completed"
            if phase!=0:
                raise ManualContextError("partial state without journal")
            io.create_journal(plan.journal())
        elif saved!=plan.journal():
            raise ManualContextError("different reviewed transaction")
        for n in range(phase,count):
            io.preflight(plan)
            if io.read_journal()!=plan.journal() or plan.phase(io.observe())!=n:
                raise ManualContextError("transaction changed")
            io.write(steps[n],plan)
            if plan.phase(io.observe())!=n+1:
                raise ManualContextError("write verification failed")
        io.preflight(plan)
        io.verify_final(plan)
        if io.read_journal()!=plan.journal() or plan.phase(io.observe())!=count:
            raise ManualContextError("final state changed")
        io.remove_journal()
        return "completed"
