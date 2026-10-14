"""Optional uiautomator2 UI bridge with observed hierarchy and task gates."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from phone import run, parse_devices, require_device

def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--adb", required=True)
    p.add_argument("--serial", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--observed-account", required=True)
    p.add_argument("--ops-script", required=True)
    s = p.add_subparsers(dest="cmd", required=True)
    observe = s.add_parser("observe"); observe.add_argument("--output-base", required=True)
    for action in ("click", "set-text", "submit"):
        q = s.add_parser(action)
        q.add_argument("--selector", required=True, help="JSON object using text or resourceId")
        q.add_argument("--expect-hierarchy-sha256", required=True)
        if action == "set-text":
            q.add_argument("--text-file", required=True)
    a = p.parse_args()
    require_device(parse_devices(run(a.adb, "devices", "-l")), a.serial)
    if importlib.util.find_spec("uiautomator2") is None:
        raise ValueError("缺少 uiautomator2；先确认并安装到项目环境。未进行 UI 操作。")
    module_spec = importlib.util.spec_from_file_location("selfmedia_ops", a.ops_script)
    ops = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(ops)
    ledger = ops.Ledger(a.root)
    try:
        operate(a, ledger)
    finally:
        ledger.db.close()

def operate(a, ledger):
    task = ledger.load(a.task)
    if task["instance"]["device_id"] != a.serial:
        raise ValueError("任务与设备不匹配；登记 device_id 必须为 adb 序列号")
    ledger.account(task, a.observed_account)
    if a.cmd != "observe":
        ledger.owns(task)
        ledger.check(task)
    import uiautomator2 as u2
    device = u2.connect(a.serial)
    current = device.app_current()
    if current.get("package") != task["instance"]["package_name"]:
        raise ValueError("当前 App 与任务实例不匹配，未进行输入")
    hierarchy = device.dump_hierarchy()
    digest = sha(hierarchy)
    if a.cmd == "observe":
        base = (ledger.root / a.output_base).resolve()
        if not base.is_relative_to(ledger.root):
            raise ValueError("观察证据必须位于工作目录内")
        xml = Path(str(base) + ".xml"); png = Path(str(base) + ".png")
        if xml.exists() or png.exists():
            raise ValueError("观察文件已存在，不覆盖")
        base.parent.mkdir(parents=True, exist_ok=True)
        with xml.open("x", encoding="utf-8") as stream:
            stream.write(hierarchy)
        device.screenshot(str(png))
        result = {"hierarchy": str(xml), "screenshot": str(png), "hierarchy_sha256": digest,
                  "app": current, "note": "执行器仍须从实际个人主页核实 observed-account"}
    else:
        if digest != a.expect_hierarchy_sha256:
            raise ValueError("界面已变化，重新 observe，不使用旧定位")
        selector = json.loads(a.selector)
        if not isinstance(selector, dict) or not selector or any(k not in ("text", "resourceId") or not isinstance(v, str) or not v for k,v in selector.items()):
            raise ValueError("仅支持实际观察到的精确 text/resourceId")
        node = device(**selector)
        if node.count != 1:
            raise ValueError("定位不是唯一元素，未操作")
        final_labels = {"发布", "发表", "投稿", "群发", "发送", "提交", "确认发布", "立即发布"}
        if a.cmd == "submit":
            if task["state"] != "publishing":
                raise ValueError("先有本次用户确认并运行 begin")
            for evidence in ("approval", "draft", "qa"):
                if ledger.file(task[evidence]["path"]) != task[evidence]:
                    raise ValueError("发布确认或证据已变化")
            ledger.change(task["id"], "attempt", observed=a.observed_account)
            node.click()
            result = {"task": task["id"], "submission_attempted": True,
                      "note": "不代表发布成功，必须再次 observe 并核验作品，再 complete 或 uncertain"}
        else:
            if task["state"] != "reviewed":
                raise ValueError("编辑操作只允许 reviewed 状态，避免修改已确认的草稿")
            label = node.info.get("text", "")
            if label in final_labels:
                raise ValueError("疑似对外提交控件，必须走 submit 的用户确认闸门")
            if a.cmd == "set-text":
                node.set_text(ledger.path(a.text_file).read_text(encoding="utf-8-sig"))
            else:
                node.click()
            result = {"operation": a.cmd, "note": "立即重新 observe 并核对结果，禁止沿用旧哈希"}
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"error": str(error), "note": "输入异常时先观察结果，不盲目重试"}, ensure_ascii=False))
        sys.exit(2)
