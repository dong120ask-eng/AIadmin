import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = ROOT / 'skills' if (ROOT / 'skills').is_dir() else ROOT


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cases = [('core', SKILL_ROOT/'global-short-drama/scripts', 'test_*.py'), ('bundle', ROOT/'verification', 'test_bundle.py')]
    results = []
    for name, folder, pattern in cases:
        command = [sys.executable,'-m','unittest','discover','-s',str(folder),'-p',pattern,'-q']
        started = time.monotonic()
        completed = subprocess.run(command,capture_output=True,encoding='utf-8',errors='replace')
        output = completed.stdout + completed.stderr
        count = re.search(r'Ran (\d+) tests',output)
        results.append({'suite':name,'count':int(count.group(1)) if count else None,'passed':completed.returncode==0,'elapsed_seconds':round(time.monotonic()-started,3),'command':command,'output':output})
    structure = subprocess.run([sys.executable,str(ROOT/'verification/verify_bundle.py')],capture_output=True,encoding='utf-8',errors='replace')
    record = {'client_date':'2026-10-14','passed':all(x['passed'] for x in results) and structure.returncode==0,'test_count':sum(x['count'] or 0 for x in results),'suites':results,'structure_check':{'passed':structure.returncode==0,'output':structure.stdout+structure.stderr,'method':'zero_dependency_subset_frontmatter_resources_json_handoff'},'official_skill_validator':'not_passed_missing_PyYAML_no_install','real_ffmpeg_tests':True,'model_and_api_tests':'mocked_no_paid_provider_calls','actual_provider_acceptance':False,'actual_client_deployment':False,'actual_platform_upload':False,'visual_and_listening_acceptance':False}
    (ROOT/'verification/验收记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':record['passed'],'tests':record['test_count'],'suites':[{'name':x['suite'],'passed':x['passed'],'count':x['count']} for x in results],'structure':structure.returncode==0},ensure_ascii=False))
    if not record['passed']:
        for result in results:
            if not result['passed']:
                print(result['output'])
        if structure.returncode:
            print(structure.stdout+structure.stderr)
        sys.exit(1)


if __name__=='__main__':
    main()
