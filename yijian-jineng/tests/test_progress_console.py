import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'tools/progress_console.py'
spec = importlib.util.spec_from_file_location('progress_console', SOURCE)
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)

class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    @contextmanager
    def database(self):
        (self.root / 'state').mkdir()
        db = sqlite3.connect(self.root / 'state/selfmedia.sqlite')
        db.executescript('CREATE TABLE instances(id TEXT,body TEXT);CREATE TABLE tasks(id TEXT,body TEXT);CREATE TABLE locks(device TEXT,task TEXT);')
        try:
            with db:
                yield db
        finally:
            db.close()
    def test_empty_workspace_does_not_create_state(self):
        result = console.snapshot(self.root)
        self.assertEqual(result['accounts_registered'], 0)
        self.assertFalse((self.root / 'state').exists())
    def test_unknown_result_prioritized_and_secrets_excluded(self):
        with self.database() as db:
            db.execute('INSERT INTO tasks VALUES(?,?)', ('t1', json.dumps({'state':'uncertain','title':'SECRET_TITLE','instance':{'platform':'douyin','account_id':'SECRET_ACCOUNT'}})))
            db.execute('INSERT INTO locks VALUES(?,?)', ('SECRET_DEVICE','t1'))
        result = console.snapshot(self.root)
        self.assertIn('结果不明', result['next_steps'][0])
        self.assertNotIn('SECRET_', json.dumps(result))
        self.assertEqual(result['locked_task_ids'], ['t1'])
    def test_html_escapes_platform_and_never_embeds_raw_json(self):
        result = console.snapshot(self.root)
        result['tasks'] = [{'id':'<script>bad()</script>','platform':'<img onerror=x>','label':'待检查','next':'核验'}]
        page = console.render(result)
        self.assertNotIn('<script>bad()', page)
        self.assertNotIn('<img onerror=x>', page)
        self.assertIn('&lt;script&gt;', page)
    def test_damaged_database_reports_incomplete_counts(self):
        (self.root / 'state').mkdir()
        (self.root / 'state/selfmedia.sqlite').write_bytes(b'broken')
        result = console.snapshot(self.root)
        self.assertTrue(result['warnings'])
        self.assertTrue(any('不完整' in x for x in result['next_steps']))
    def test_export_refuses_workspace_escape(self):
        with self.assertRaises(ValueError):
            console.export(self.root, '../outside')
    def test_export_refuses_unrelated_existing_files(self):
        target = self.root / 'outputs'
        target.mkdir()
        (target / 'body.md').write_text('keep', encoding='utf-8')
        with self.assertRaises(ValueError):
            console.export(self.root, target)
        self.assertEqual((target / 'body.md').read_text(), 'keep')

if __name__ == '__main__':
    unittest.main()
