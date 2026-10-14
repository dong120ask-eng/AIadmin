"""Observe or operate an explicitly selected local browser page with task/account guards."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
from urllib.parse import urlparse
HERE=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("ledger",HERE/"dsh-selfmedia-hub/scripts/ops.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("root","task","cdp","url","account-selector"): p.add_argument("--"+k,required=True)
    p.add_argument("action",choices=("observe","fill","files","click","submit"))
    p.add_argument("--selector"); p.add_argument("--text-file"); p.add_argument("--media",action="append",default=[])
    p.add_argument("--expected-dom"); p.add_argument("--output",required=True)
    a=p.parse_args(); endpoint=urlparse(a.cdp)
    if endpoint.scheme!="http" or endpoint.hostname not in ("localhost","127.0.0.1","::1"): raise ValueError("CDP只能明确连接本机已授权浏览器")
    l=m.Ledger(a.root)
    try:
        task=l.load(a.task)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.connect_over_cdp(a.cdp)
            pages=[p for c in browser.contexts for p in c.pages if p.url==a.url]
            if len(pages)!=1: raise ValueError("必须唯一匹配明确的页面URL，不能默认第一标签页")
            page=pages[0]; identity=page.locator(a.account_selector)
            if identity.count()!=1 or identity.inner_text().strip()!=task["instance"]["account_id"]: raise ValueError("页面账号不符或无法唯一验证")
            html=page.content(); dom=hashlib.sha256(html.encode()).hexdigest(); out=l.root/a.output
            if not out.resolve().is_relative_to(l.root) or out.exists(): raise ValueError("证据需工作区内新文件")
            out.parent.mkdir(parents=True,exist_ok=True)
            if a.action!="observe":
                l.owns(task); l.check(task)
                if a.expected_dom!=dom: raise ValueError("页面已改变，重新观察")
                if not a.selector: raise ValueError("需当前页面的精确选择器")
                node=page.locator(a.selector)
                if node.count()!=1: raise ValueError("节点不唯一")
                if a.action=="submit":
                    if task["state"]!="publishing": raise ValueError("需当前任务用户确认及begin")
                    l.change(task["id"],"attempt",observed=identity.inner_text().strip())
                    node.click()
                else:
                    if task["state"]!="reviewed": raise ValueError("编辑仅允许reviewed阶段")
                    if node.inner_text().strip() in ("发布","发表","提交","投稿","群发","发送","确认发布"): raise ValueError("对外提交需submit闸门")
                    if a.action=="fill": node.fill(l.path(a.text_file).read_text(encoding="utf-8-sig"))
                    elif a.action=="files": node.set_input_files([str(l.path(f)) for f in a.media])
                    else: node.click()
            page.screenshot(path=str(out),full_page=True)
            print(json.dumps({"task":task["id"],"dom_sha256":dom,"screenshot":str(out),
                "note":"每步后重新观察；submit只是尝试提交，真实结果仍需核验"},ensure_ascii=False))
    finally: l.db.close()
