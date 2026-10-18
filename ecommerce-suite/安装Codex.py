from pathlib import Path
import argparse,shutil
p=argparse.ArgumentParser();p.add_argument("project",type=Path);a=p.parse_args()
s=Path(__file__).resolve().parent/"Codex"; d=a.project.resolve()/".agents"/"skills"
conflicts=[x.name for x in s.iterdir() if (d/x.name).exists()]
if conflicts:raise SystemExit("存在旧技能，未写入任何文件，请先核版本："+", ".join(conflicts))
d.mkdir(parents=True,exist_ok=True)
for x in s.iterdir():shutil.copytree(x,d/x.name)
print("已复制22个技能，请重新打开项目验证识别")
