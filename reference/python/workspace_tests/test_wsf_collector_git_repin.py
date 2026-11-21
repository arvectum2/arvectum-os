"""Exact-source Owner approval cannot become a generic collector change grant."""
from unittest import TestCase
import subprocess
from wsf_collector_repin_operator import (
    exact_git_first_successor, GIT_FIRST_SOURCE, GIT_FIRST_DECISION,
    GIT_FIRST_FILES, CONTRACT, compatible,
)


class GitFirstGateTests(TestCase):
    target="e"*40
    blob="b"*40
    def git(self,*args):
        if args==("merge-base","--is-ancestor",GIT_FIRST_SOURCE,self.target):return b""
        if args==("rev-parse",GIT_FIRST_SOURCE+":"+CONTRACT) or args==("rev-parse",self.target+":"+CONTRACT):
            return (self.blob+"\n").encode()
        if args==("diff","--name-only","--no-renames","-z",GIT_FIRST_SOURCE,self.target):
            return ("\0".join(sorted(GIT_FIRST_FILES))+"\0").encode()
        raise AssertionError(args)
    def test_only_exact_candidate(self):
        self.assertTrue(exact_git_first_successor(GIT_FIRST_SOURCE,self.target,GIT_FIRST_DECISION,git=self.git))
    def test_wrong_source_or_decision(self):
        self.assertFalse(exact_git_first_successor("a"*40,self.target,GIT_FIRST_DECISION,git=self.git))
        self.assertFalse(exact_git_first_successor(GIT_FIRST_SOURCE,self.target,"OWNER-OTHER",git=self.git))
    def test_changed_contract_rejected(self):
        def bad(*args):
            if args==( "rev-parse",self.target+":"+CONTRACT):return ("c"*40).encode()
            return self.git(*args)
        self.assertFalse(exact_git_first_successor(GIT_FIRST_SOURCE,self.target,GIT_FIRST_DECISION,git=bad))
    def test_extra_file_rejected(self):
        def bad(*args):
            out=self.git(*args)
            if args[0]=="diff":return out+b"reference/python/workspace_app/wsf_collector_runtime.py\0"
            return out
        self.assertFalse(exact_git_first_successor(GIT_FIRST_SOURCE,self.target,GIT_FIRST_DECISION,git=bad))
    def test_non_descendant_rejected(self):
        def bad(*args):
            if args[0]=="merge-base":raise subprocess.CalledProcessError(1,args)
            return self.git(*args)
        self.assertFalse(exact_git_first_successor(GIT_FIRST_SOURCE,self.target,GIT_FIRST_DECISION,git=bad))
    def test_generic_envelope_unchanged(self):
        self.assertFalse(compatible(["reference/python/workspace_app/wsf_collector_source.py"]))
        self.assertFalse(compatible(["reference/python/workspace_app/wsf_collector_git_source.py"]))
