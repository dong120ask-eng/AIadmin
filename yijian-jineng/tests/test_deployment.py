import importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('deployment',ROOT/'tools/deploy.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.source=self.root/'source'; self.source.mkdir()
        (self.source/'demo').mkdir(); (self.source/'demo/SKILL.md').write_text('new')
        self.target=self.root/'project/.agents/skills'
    def test_plan_does_not_mutate(self):
        self.assertEqual(module.deploy(self.source,self.target)['skill_count'],1)
        self.assertFalse(self.target.exists())
    def test_deploy_and_repeat_preserve_other_skills(self):
        self.target.mkdir(parents=True); (self.target/'custom').mkdir(); (self.target/'custom/SKILL.md').write_text('mine')
        module.deploy(self.source,self.target,True,True)
        self.assertEqual(module.deploy(self.source,self.target,True,True)['changed'],0)
        self.assertEqual((self.target/'custom/SKILL.md').read_text(),'mine')
    def test_changed_requires_backup(self):
        module.deploy(self.source,self.target,True)
        (self.source/'demo/SKILL.md').write_text('newer')
        with self.assertRaises(ValueError): module.deploy(self.source,self.target,True)
        result=module.deploy(self.source,self.target,True,True)
        self.assertEqual((Path(result['backup'])/'demo/SKILL.md').read_text(),'new')
    def test_file_directory_conflict_keeps_original(self):
        (self.target/'demo/SKILL.md').mkdir(parents=True)
        with self.assertRaises(ValueError): module.deploy(self.source,self.target,True,True)
        self.assertTrue((self.target/'demo/SKILL.md').is_dir())
        self.assertFalse((self.target.parent/'.skill-deploy.lock').exists())
    def test_ancestor_and_unexpected_target_rejected(self):
        for p in (self.source,self.root,self.root/'arbitrary'):
            with self.assertRaises(ValueError): module.deploy(self.source,p,True,True)
    def test_failed_swap_rolls_back(self):
        module.deploy(self.source,self.target,True)
        (self.source/'demo/SKILL.md').write_text('newer'); original=Path.rename
        def fail_stage(p,target):
            if p.name.startswith('.skill-stage-'): raise OSError('simulated disk failure')
            return original(p,target)
        with patch.object(Path,'rename',fail_stage):
            with self.assertRaises(OSError): module.deploy(self.source,self.target,True,True)
        self.assertEqual((self.target/'demo/SKILL.md').read_text(),'new')
    def test_concurrent_lock_blocks_mutation(self):
        self.target.parent.mkdir(parents=True); (self.target.parent/'.skill-deploy.lock').touch()
        with self.assertRaises(FileExistsError): module.deploy(self.source,self.target,True)
        self.assertFalse(self.target.exists())
if __name__=='__main__': unittest.main()
