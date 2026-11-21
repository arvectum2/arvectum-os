"""A single Company read-only adapter + Python 3.14 fix is an exact exception."""
from unittest import TestCase
import subprocess
from wsf_collector_repin_operator import (
    exact_source_sync_successor,SOURCE_SYNC_ANCHOR,SOURCE_SYNC_DECISION,
    SOURCE_SYNC_FILES,CONTRACT,compatible,
)

class BoundedSyncGateTests(TestCase):
    target="c"*40
    blob="d"*40
    def git(self,*args):
        if args==("merge-base","--is-ancestor",SOURCE_SYNC_ANCHOR,self.target):return b""
        if args in (("rev-parse",SOURCE_SYNC_ANCHOR+":"+CONTRACT),("rev-parse",self.target+":"+CONTRACT)):
            return (self.blob+"\n").encode()
        if args==("diff","--name-only","--no-renames","-z",SOURCE_SYNC_ANCHOR,self.target):
            return ("\0".join(sorted(SOURCE_SYNC_FILES))+"\0").encode()
        raise AssertionError(args)
    def admitted(self,git=None,source=SOURCE_SYNC_ANCHOR,decision=SOURCE_SYNC_DECISION):
        return exact_source_sync_successor(source,self.target,decision,git=git or self.git)
    def test_exact_read_only_candidate(self):self.assertTrue(self.admitted())
    def test_source_and_decision_bound(self):
        self.assertFalse(self.admitted(source="0"*40))
        self.assertFalse(self.admitted(decision="OWNER-OTHER"))
    def test_extra_collector_or_access_file_denied(self):
        def bad(*args):
            v=self.git(*args)
            return v+b"reference/python/workspace_app/wsf_collector_runner.py\0" if args[0]=="diff" else v
        self.assertFalse(self.admitted(bad))
    def test_unapproved_contract_change_denied(self):
        def bad(*args):
            if args==("rev-parse",self.target+":"+CONTRACT):return ("f"*40).encode()
            return self.git(*args)
        self.assertFalse(self.admitted(bad))
    def test_unrelated_history_denied(self):
        def bad(*args):
            if args[0]=="merge-base":raise subprocess.CalledProcessError(1,args)
            return self.git(*args)
        self.assertFalse(self.admitted(bad))
    def test_old_general_compatible_envelope_unchanged(self):
        self.assertFalse(compatible(["reference/python/workspace_app/company_source_watch_evidence.py"]))
        self.assertFalse(compatible(["reference/python/workspace_app/f11_routes.py"]))
