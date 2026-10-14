import hashlib,json,re
from pathlib import Path
def read(path): return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def save(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8",newline="\n") as f:
        f.write(value) if isinstance(value,str) else json.dump(value,f,ensure_ascii=False,indent=2)
def inside(root,value,exists=False):
    root=Path(root).resolve(); path=(root/value).resolve()
    if not path.is_relative_to(root) or (exists and not path.is_file()): raise ValueError("文件路径必须在工作区内且符合存在条件")
    return path
def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""): h.update(chunk)
    return h.hexdigest()
def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",value): raise ValueError("标识须用英文小写、数字、连字符")
    return value
