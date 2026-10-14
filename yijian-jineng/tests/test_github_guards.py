import shutil, subprocess, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(shutil.which('powershell.exe'),'Windows PowerShell required')
class GithubGuards(unittest.TestCase):
    def run_guard(self,*args):
        return subprocess.run(['powershell.exe','-NoProfile','-File',str(ROOT/'tools/github-install.ps1'),*args],capture_output=True,text=True,errors='replace',timeout=20)
    def test_public_url_cannot_change_host(self):
        r=self.run_guard('-ReleaseUrl','https://example.com/a/b/releases/download/v1/data.zip','-Sha256','a'*64)
        self.assertNotEqual(r.returncode,0); self.assertIn('versioned GitHub',r.stderr)
    def test_private_repo_options_reject_injection(self):
        r=self.run_guard('-Repository','--evil/repo','-Version','v1','-Sha256','a'*64)
        self.assertNotEqual(r.returncode,0); self.assertIn('Invalid repository',r.stderr)
    def test_checksum_required_before_download(self):
        r=self.run_guard('-Repository','owner/repo','-Version','v1','-Sha256','bad')
        self.assertNotEqual(r.returncode,0); self.assertIn('SHA256 is required',r.stderr)
if __name__=='__main__': unittest.main()
