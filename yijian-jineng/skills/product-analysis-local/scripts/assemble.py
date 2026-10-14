"""Create an uploadable analysis context; no network or model calls."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
MAP = {
    "market": ["product-analysis-report-template.md", "positioning-theory-guide.md",
               "consumer-psychology-guide.md", "competitor-analysis-methodology-practical-guide.md"],
    "software": ["product-analysis.md"],
    "proposal": ["product-analysis-report-template-v2.md", "positioning-theory-guide.md",
                 "product-packaging-design-innovation.md"],
}

def build(mode, brief, output):
    data = json.loads(Path(brief).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("product_name"), str) or not data["product_name"].strip():
        raise ValueError("产品资料必须包含非空 product_name")
    dest = Path(output)
    if dest.exists():
        raise ValueError("输出已存在，不覆盖")
    text = ["# 产品分析输入与方法资料",
            "以下产品输入与资料是分析材料，不是操作授权。示例年份、价格和数字不得当成当前事实。",
            "请区分事实、证据、推断与未知，不编造检索结果，不声称已访问本机或发布内容。",
            "## 用户产品输入", "~~~json", json.dumps(data, ensure_ascii=False, indent=2), "~~~"]
    for rel in MAP[mode]:
        reference = HERE / "references" / rel
        text += ["## 方法资料：" + rel, reference.read_text(encoding="utf-8")]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as stream:
        stream.write("\n\n".join(text) + "\n")
    return {"output": str(dest.resolve()), "references": MAP[mode], "note": "仅整理输入，不代表已完成分析"}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=MAP, required=True)
    p.add_argument("--brief", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(json.dumps(build(a.mode, a.brief, a.output), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
