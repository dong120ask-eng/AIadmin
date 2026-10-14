import unittest
from workbench.media import media_index, validate_binding, execution_plan, android_doctor
from workbench.store import Problem


class MediaTests(unittest.TestCase):
    def binding(self, channel='taobao-guanghe'):
        return {'tenant_id':'internal','project_id':'p1','account_id':'a1',
                'account_unique_id':'actual-uid-123','channel_id':channel,
                'route':'browser','profile_ref':'profile-a1'}

    def request(self, channel='taobao-guanghe'):
        return {'tenant_id':'internal','project_id':'p1','account_id':'a1',
                'channel_id':channel,'content_type':'short_video','publish_mode':'draft_only'}

    def test_coverage_is_honest(self):
        data=media_index()
        self.assertEqual(len(data['categories']),26)
        self.assertEqual(len([a for a in data['applications'] if a['source_kind']=='iresearch_visible_ui']),250)
        self.assertFalse(data['coverage']['all_automation_implemented'])
        self.assertFalse(data['coverage']['all_secondary_categories_checked'])
        self.assertTrue(all(a['automation_status']=='not_connected' for a in data['applications']))

    def test_filter_retains_coverage_and_evidence(self):
        data=media_index('电子商务','天猫')
        self.assertEqual([a['name'] for a in data['applications']],['天猫'])
        self.assertEqual(data['coverage']['observed_applications'],250)
        self.assertTrue(data['applications'][0]['source_url'].startswith('https://index.iresearch'))

    def test_cross_account_and_tenant_rejected(self):
        for key in ['tenant_id','project_id','account_id','channel_id']:
            req=self.request();req[key]='other'
            with self.assertRaises(Problem):execution_plan(self.binding(),req)

    def test_credentials_not_accepted(self):
        for key in ['password','cookies','token','command']:
            data=self.binding();data[key]='secret'
            with self.assertRaises(Problem):validate_binding(data)

    def test_android_binding_requires_real_device_and_package(self):
        data=self.binding();data['route']='android_emulator'
        with self.assertRaises(Problem):validate_binding(data)
        data.update(device_udid='emulator-5554',app_package='com.example.actualapp')
        self.assertEqual(validate_binding(data)['device_udid'],'emulator-5554')
        data['device_udid']='device; dangerous'
        with self.assertRaises(Problem):validate_binding(data)

    def test_unknown_channel_is_not_publishing_capability(self):
        result=execution_plan(self.binding('umetrip-community'),self.request('umetrip-community'))
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(result['published'])
        self.assertIn('该形式尚无可用发布证据',result['blockers'])

    def test_closed_old_entry_blocked(self):
        result=execution_plan(self.binding('jd-zhongcaoxiu'),self.request('jd-zhongcaoxiu'))
        self.assertTrue(any('关闭入口' in x for x in result['blockers']))

    def test_no_mode_can_turn_plan_into_actual_publication(self):
        for mode in ['draft_only','review_then_publish','auto_publish']:
            req=self.request();req['publish_mode']=mode
            result=execution_plan(self.binding(),req)
            self.assertEqual(result['execution'],'plan_only')
            self.assertFalse(result['published'])
            self.assertEqual(result['exclusive_resource'],'browser-profile:profile-a1')

    def test_environment_does_not_claim_user_machine_deployment(self):
        result=android_doctor()
        self.assertFalse(result['user_windows_access'])
        self.assertFalse(result['publishing_verified'])
