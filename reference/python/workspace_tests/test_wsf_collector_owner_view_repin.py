"""Strict exact successor gate for one owner-authorized Mission Control repair."""
import subprocess
from unittest import TestCase
from wsf_collector_repin_operator import (
 exact_owner_view_successor,OWNER_VIEW_SOURCE,OWNER_VIEW_ANCHOR,
 OWNER_VIEW_DECISION,OWNER_VIEW_DELTA,CONTRACT,PUBLICATION_PIN,compatible)

class OwnerViewRePinTests(TestCase):
 target="a"*40
 def git(self,*args):
  if args in (("merge-base","--is-ancestor",OWNER_VIEW_SOURCE,OWNER_VIEW_ANCHOR),
              ("merge-base","--is-ancestor",OWNER_VIEW_ANCHOR,self.target)):return b""
  if args[0]=="rev-parse":return (PUBLICATION_PIN+"\n").encode()
  if args[0]=="diff":return ("\0".join(sorted(OWNER_VIEW_DELTA))+"\0").encode()
  raise AssertionError(args)
 def run_gate(self,git=None,source=OWNER_VIEW_SOURCE,decision=OWNER_VIEW_DECISION):
  return exact_owner_view_successor(source,self.target,decision,git=git or self.git)
 def test_exact_successor(self):self.assertTrue(self.run_gate())
 def test_denies_wrong_authority(self):
  self.assertFalse(self.run_gate(source="b"*40))
  self.assertFalse(self.run_gate(decision="OWNER-NO-APPROVAL"))
 def test_denies_new_code_outside_approved_delta(self):
  def wrong(*args):
   if args[0]=="diff":return self.git(*args)+b"reference/python/workspace_app/wsf_collector_runner.py\0"
   return self.git(*args)
  self.assertFalse(self.run_gate(git=wrong))
 def test_denies_contract_change(self):
  def wrong(*args):
   if args==("rev-parse",self.target+":"+CONTRACT):return ("f"*40).encode()
   return self.git(*args)
  self.assertFalse(self.run_gate(git=wrong))
 def test_denies_non_descendant(self):
  def wrong(*args):
   if args[0]=="merge-base":raise subprocess.CalledProcessError(1,args)
   return self.git(*args)
  self.assertFalse(self.run_gate(git=wrong))
 def test_generic_envelope_stays_fail_closed(self):
  self.assertFalse(compatible(["reference/python/workspace_app/f11_routes.py"]))
  self.assertFalse(compatible(["reference/python/workspace_app/wsf_collector_runner.py"]))
