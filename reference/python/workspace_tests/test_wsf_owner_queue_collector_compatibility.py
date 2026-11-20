"""Exact approved queue bridge must not weaken generic collector compatibility."""
import subprocess
import unittest
from wsf_collector_repin_operator import (
    compatible, exact_queue_successor, QUEUE_SOURCE, QUEUE_DECISION,
    QUEUE_ANCHOR, QUEUE_CONTRACT, QUEUE_CONTRACT_BLOB, QUEUE_SUCCESSOR_FILES,
)

class QueueCollectorTest(unittest.TestCase):
    target = "a"*40
    def git(self, *args):
        if args == ("merge-base", "--is-ancestor", QUEUE_ANCHOR, self.target):
            return b""
        if args == ("rev-parse", self.target + ":" + QUEUE_CONTRACT):
            return QUEUE_CONTRACT_BLOB.encode() + b"\n"
        if args == ("diff", "--name-only", "--no-renames", "-z", QUEUE_ANCHOR, self.target):
            return ("\0".join(sorted(QUEUE_SUCCESSOR_FILES))+"\0").encode()
        raise AssertionError(args)
    def check(self, git=None, source=QUEUE_SOURCE, decision=QUEUE_DECISION):
        return exact_queue_successor(source,self.target,decision,git=git or self.git)
    def test_exact(self):
        self.assertTrue(self.check())
    def test_old_or_unknown_source(self):
        self.assertFalse(self.check(source="b"*40))
    def test_wrong_decision(self):
        self.assertFalse(self.check(decision="different"))
    def test_unrelated_change(self):
        def git(*args):
            value=self.git(*args)
            return value+b"reference/python/workspace_app/wsf_collector_runtime.py\0" if args[0]=="diff" else value
        self.assertFalse(self.check(git))
    def test_contract_drift(self):
        self.assertFalse(self.check(lambda *a: b"b"*40 if a[0]=="rev-parse" else self.git(*a)))
    def test_not_descendant(self):
        def git(*args):
            if args[0]=="merge-base":
                raise subprocess.CalledProcessError(1,args)
            return self.git(*args)
        self.assertFalse(self.check(git))
    def test_existing_gate_not_weakened(self):
        self.assertFalse(compatible(["reference/python/workspace_app/main.py"]))
        self.assertFalse(compatible(["reference/python/workspace_app/wsf_collector_runtime.py"]))
        self.assertFalse(compatible(["reference/python/workspace_app/wsf_owner_queue.py"]))
