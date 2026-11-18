import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import p9_11_workspace_login_start as start
import p9_11_workspace_process as process

RELEASE="a"*40

class LoginTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve();(self.root/"run").mkdir(mode=0o700)
        self.exact={"state":process.CURRENT_EXACT,"release_sha":RELEASE}
        for target,kwargs,name in (
            ("p706.current_release",{"return_value":RELEASE},"current"),
            ("p706.verify_release",{},"verify"),
            ("p911.status",{"return_value":{"state":process.NOT_RUNNING}},"status"),
            ("p911._require_p702_health",{},"health"),
            ("p911.start",{"return_value":self.exact},"spawn"),
        ):
            p=patch("p9_11_workspace_login_start."+target,**kwargs)
            setattr(self,name,p.start());self.addCleanup(p.stop)
    def execute(self):
        return start.start_once(self.root,RELEASE,attempts=2,sleep=lambda _:None)
    def test_exact_start_once(self):
        def spawn(root):
            self.assertTrue(all((root/"run"/x/"pid").is_file() for x in start.LOCKS))
            return self.exact
        self.spawn.side_effect=spawn
        self.assertEqual(self.execute(),self.exact)
        self.assertEqual(list((self.root/"run").iterdir()),[])
    def test_already_running(self):
        self.status.return_value=self.exact
        self.assertEqual(self.execute(),self.exact);self.spawn.assert_not_called()
    def test_unknown_or_stale_never_signalled(self):
        for state in (process.UNKNOWN,process.STALE_KNOWN_EXACT):
            self.status.return_value={"state":state}
            with self.assertRaises(start.LoginStartError):self.execute()
        self.spawn.assert_not_called()
    def test_existing_deployment_or_desktop_lock_preserved(self):
        for name in start.LOCKS:
            lock=self.root/"run"/name;lock.mkdir();(lock/"pid").write_text("other")
            with self.assertRaises(start.LoginStartError):self.execute()
            self.assertEqual((lock/"pid").read_text(),"other")
            (lock/"pid").unlink();lock.rmdir()
        self.spawn.assert_not_called()
    def test_core_health_or_release_change(self):
        self.health.side_effect=process.WorkspaceProcessError("not ready")
        with self.assertRaises(start.LoginStartError):self.execute()
        self.assertEqual(self.health.call_count,2)
        self.health.side_effect=None;self.current.side_effect=[RELEASE,"b"*40]
        with self.assertRaises(start.LoginStartError):self.execute()
        self.spawn.assert_not_called()
        self.assertEqual(list((self.root/"run").iterdir()),[])
    def test_plist_one_shot_no_watchdog_or_network(self):
        d=start.agent_spec(self.root)
        self.assertTrue(d["RunAtLoad"]);self.assertTrue(d["AbandonProcessGroup"])
        self.assertFalse(any(k in d for k in ("KeepAlive","StartInterval","StartCalendarInterval","Sockets")))
        self.assertEqual(d["ProgramArguments"][-1],str(self.root))
        self.assertNotIn("launchctl",d["ProgramArguments"][2])
