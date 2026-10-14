import sys,types,unittest
from unittest.mock import patch
from workbench.android_sdks import LocalSdkInspector,require_device
from workbench.store import Problem

class OptionalSdkTests(unittest.TestCase):
    def binding(self):return {'tenant_id':'internal','project_id':'qa','account_id':'qa','account_unique_id':'qa-only','channel_id':'taobao-guanghe','route':'android_device','device_udid':'SERIAL-QA','app_package':'com.example.qa'}
    def test_uiautomator_receives_explicit_device(self):
        calls=[];device=types.SimpleNamespace(serial='SERIAL-QA',dump_hierarchy=lambda:'<hierarchy/>')
        module=types.SimpleNamespace(connect=lambda serial:(calls.append(serial) or device))
        with patch.dict(sys.modules,{'uiautomator2':module}),patch('workbench.android_sdks.require_device'):
            client=LocalSdkInspector('uiautomator2');client.connect(self.binding());self.assertEqual(client.source(),'<hierarchy/>');client.close()
        self.assertEqual(calls,['SERIAL-QA'])
    def test_mobilerun_never_selects_cloud(self):
        calls=[];device=types.SimpleNamespace(ui=lambda:{'nodes':[{'text':'QA only'}]})
        facade=types.SimpleNamespace(connect=lambda serial,**kwargs:(calls.append((serial,kwargs)) or device))
        module=types.SimpleNamespace(Mobilerun=lambda:facade)
        with patch.dict(sys.modules,{'mobilerun_core':module}),patch('workbench.android_sdks.require_device'):
            client=LocalSdkInspector('mobilerun');result=client.connect(self.binding());self.assertIn('mobilerun-ui-json',client.source())
        self.assertEqual(calls,[('SERIAL-QA',{'backend':'local-android-adb'})]);self.assertFalse(result['cloud_backend_selected'])
    def test_returned_device_mismatch_rejected(self):
        module=types.SimpleNamespace(connect=lambda serial:types.SimpleNamespace(serial='OTHER'))
        with patch.dict(sys.modules,{'uiautomator2':module}),patch('workbench.android_sdks.require_device'):
            with self.assertRaises(Problem):LocalSdkInspector('uiautomator2').connect(self.binding())
    def test_missing_dependency_reports_setup_failure(self):
        with patch('workbench.android_sdks.importlib.import_module',side_effect=ImportError):
            with self.assertRaises(Problem):LocalSdkInspector('mobilerun')
    def test_missing_target_does_not_fall_back_to_other_device(self):
        proc=types.SimpleNamespace(returncode=0,stdout='List of devices attached\nOTHER\tdevice\n')
        with patch('workbench.android_sdks.shutil.which',return_value='/qa/adb'),patch('workbench.android_sdks.subprocess.run',return_value=proc):
            with self.assertRaises(Problem):require_device('SERIAL-QA')
    def test_disconnected_target_blocks_source(self):
        device=types.SimpleNamespace(serial='SERIAL-QA',dump_hierarchy=lambda:'<hierarchy/>')
        with patch.dict(sys.modules,{'uiautomator2':types.SimpleNamespace(connect=lambda serial:device)}),patch('workbench.android_sdks.require_device',side_effect=[None,Problem('offline')]):
            client=LocalSdkInspector('uiautomator2');client.connect(self.binding())
            with self.assertRaises(Problem):client.source()
