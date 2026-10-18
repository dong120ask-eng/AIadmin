import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from workbench.android import AndroidInspector
from workbench.store import Problem

class AndroidTransportTests(unittest.TestCase):
    def setUp(self):
        self.requests=[];self.actual='emulator-5554';self.redirect=False
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,value):
                raw=json.dumps({'value':value}).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((self.command,self.path,data))
                if owner.redirect:
                    self.send_response(302);self.send_header('Location','http://example.com/');self.end_headers();return
                self.reply({'sessionId':'session-123','capabilities':{'appium:udid':owner.actual}})
            def do_GET(self):
                owner.requests.append((self.command,self.path,None));self.reply('<hierarchy><node text="QA only"/></hierarchy>')
            def do_DELETE(self):
                owner.requests.append((self.command,self.path,None));self.reply(None)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.binding={'tenant_id':'internal','project_id':'test','account_id':'a1','account_unique_id':'qa-account',
          'channel_id':'taobao-guanghe','route':'android_emulator','device_udid':'emulator-5554','app_package':'com.example.qa'}
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def test_session_and_read_only_source(self):
        client=AndroidInspector(self.url)
        result=client.connect(self.binding)
        self.assertTrue(result['device_verified']);self.assertFalse(result['account_verified'])
        self.assertIn('QA only',client.source());client.close()
        caps=self.requests[0][2]['capabilities']['alwaysMatch']
        self.assertTrue(caps['appium:noReset']);self.assertFalse(caps['appium:fullReset']);self.assertFalse(caps['appium:autoLaunch'])
        self.assertEqual([x[0] for x in self.requests],['POST','GET','DELETE'])
    def test_remote_or_credential_urls_rejected(self):
        for url in ['https://127.0.0.1:4723','http://example.com','http://user:secret@localhost:4723','http://localhost:4723/?token=x','http://localhost:4723/arbitrary']:
            with self.assertRaises(Problem):AndroidInspector(url)
    def test_device_identity_mismatch_closes_session(self):
        self.actual='emulator-5556';client=AndroidInspector(self.url)
        with self.assertRaises(Problem):client.connect(self.binding)
        self.assertIsNone(client.session);self.assertEqual(self.requests[-1][0],'DELETE')
    def test_redirect_not_followed(self):
        self.redirect=True
        with self.assertRaises(Problem):AndroidInspector(self.url).connect(self.binding)
        self.assertEqual(len(self.requests),1)
    def test_browser_binding_cannot_open_android_session(self):
        self.binding.update(route='browser',profile_ref='p1')
        with self.assertRaises(Problem):AndroidInspector(self.url).connect(self.binding)
        self.assertEqual(self.requests,[])
    def test_unconnected_source_rejected(self):
        with self.assertRaises(Problem):AndroidInspector(self.url).source()
