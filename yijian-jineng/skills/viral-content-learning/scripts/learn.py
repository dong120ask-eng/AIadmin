"""Normalize observed content; popularity remains unverified without real evidence."""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"selfmedia-autopilot/scripts"))
from common import read,save,inside
def collect(data):
    result=[]; seen=set()
    for item in data["records"]:
        if item["id"] in seen: raise ValueError("样本ID重复")
        seen.add(item["id"]); url=item.get("source_url","")
        if url and urlparse(url).scheme not in ("http","https"): raise ValueError("来源URL无效")
        if not item.get("platform") or not item.get("observed_at") or not (url or item.get("source_file")): raise ValueError("缺平台、观察时间或来源")
        m=item.get("metrics",{})
        if any(not isinstance(v,(int,float)) or v<0 for v in m.values()): raise ValueError("指标不是实际非负值")
        views=m.get("views"); rate=sum(m.get(k,0) for k in ("likes","comments","shares","saves"))/views if views else None
        structure=item.get("structure",{})
        result.append({"id":item["id"],"platform":item["platform"],"source_url":url,"source_file":item.get("source_file"),
            "observed_at":item["observed_at"],"title":item.get("title",""),"metrics":m,"interaction_rate":rate,
            "popularity_verified":bool(item.get("popularity_evidence")),"popularity_evidence":item.get("popularity_evidence"),
            "framework":{k:structure.get(k,"") for k in ("hook","problem","progression","evidence","turn","ending","visual_rhythm")},
            "reuse_boundary":"仅借用结构、叙事逻辑和节奏；事实与表达重新制作"})
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("root","input","output"): p.add_argument("--"+k,required=True)
    a=p.parse_args(); data=collect(read(inside(a.root,a.input,True)))
    save(inside(a.root,a.output),{"samples":data,"note":"缺证据不标爆款，不强行跨平台排名"})
    print(json.dumps({"samples":len(data),"output":a.output},ensure_ascii=False))
