"""Static release validation. Does not operate accounts, devices, models or emulators."""
import ast,json,re,sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
errors=[]; entries=[]
for f in sorted((ROOT/"skills").glob("*/SKILL.md")):
    text=f.read_text(encoding="utf-8")
    try:
        front=yaml.safe_load(text.split("---",2)[1]); name=front["name"]; desc=front["description"]
        if name!=f.parent.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",name) or not desc: raise ValueError("元数据无效")
        for link in re.findall(r"\]\(([^)]+)\)",text):
            if "://" not in link and not link.startswith("#") and not (f.parent/link.split("#")[0]).exists(): errors.append(str(f)+":缺资源"+link)
        entries.append({"name":name,"description":desc,"files":sum(1 for p in f.parent.rglob("*") if p.is_file())})
    except Exception as e: errors.append(str(f)+":"+str(e))
for f in ROOT.rglob("*.py"):
    if "__pycache__" not in f.parts and 'offline' not in f.relative_to(ROOT).parts:
        try: ast.parse(f.read_text(encoding="utf-8"),str(f))
        except Exception as e: errors.append(str(f)+":"+str(e))
for f in (ROOT/"config").glob("*.json"):
    try: json.loads(f.read_text(encoding="utf-8"))
    except Exception as e: errors.append(str(f)+":"+str(e))
print(json.dumps({"static_validation":not errors,"skills":entries,"errors":errors,"note":"静态校验不等于真机/API/模拟器/平台发布验收"},ensure_ascii=False,indent=2))
sys.exit(bool(errors))
