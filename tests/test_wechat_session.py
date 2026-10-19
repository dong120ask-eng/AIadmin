"""Offline protocol tests; no Windows/WeChat UI claims."""
import multiprocessing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from workbench.wechat_session import ProfileLease, login
from workbench.wechat_ui import WechatBrowserUI
from workbench.store import Problem


def try_lock(path, output):
    lease = ProfileLease(path)
    try:
        lease.acquire(); output.put(True)
    except Problem:
        output.put(False)
    finally:
        lease.close()


class SessionTests(unittest.TestCase):
    def test_process_exclusion_and_release(self):
        with tempfile.TemporaryDirectory() as root:
            lease = ProfileLease(root).acquire()
            ctx = multiprocessing.get_context('spawn')
            output = ctx.Queue()
            child = ctx.Process(target=try_lock, args=(root, output))
            child.start(); child.join(10)
            self.assertFalse(child.is_alive()); self.assertEqual(child.exitcode, 0)
            self.assertFalse(output.get(timeout=2))
            lease.close()
            child = ctx.Process(target=try_lock, args=(root, output))
            child.start(); child.join(10)
            self.assertEqual(child.exitcode, 0); self.assertTrue(output.get(timeout=2))
            output.close()

    def run_login(self, identity=None, expected=None, url='https://mp.weixin.qq.com/'):
        lease, engine, context, page = Mock(), Mock(), Mock(), Mock()
        page.url = url
        config = {'profile_ref':'qa','ui_verified_at':'fixture',
                  'selectors':dict.fromkeys(WechatBrowserUI.REQUIRED, '.fixture')}
        with patch('workbench.wechat_session.open_profile', return_value=(lease,engine,context,page)), \
             patch.object(WechatBrowserUI,'identity',return_value=identity):
            try:
                return login(Path('/unused'), 'qa', config if expected else None,
                             expected, prompt=lambda _:None)
            finally:
                context.close.assert_called_once(); engine.stop.assert_called_once(); lease.close.assert_called_once()

    def test_manual_login_is_not_verified(self):
        self.assertFalse(self.run_login()['identity_verified'])
    def test_matching_identity(self):
        result = self.run_login('fixture', 'fixture')
        self.assertTrue(result['identity_verified']); self.assertFalse(result['draft_saved'])
    def test_wrong_identity(self):
        with self.assertRaises(Problem): self.run_login('other', 'fixture')
    def test_nonofficial_page(self):
        with self.assertRaises(Problem): self.run_login(url='https://example.org/')
    def test_mismatched_profile_before_browser(self):
        with patch('workbench.wechat_session.open_profile') as launch:
            with self.assertRaises(Problem):
                login('/unused', '../bad')
            launch.assert_not_called()
