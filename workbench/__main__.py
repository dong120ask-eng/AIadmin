import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

from .runner import doctor, run_job
from .media import media_index, android_doctor, execution_plan
from .android import AndroidInspector
from .dispatch import DispatchQueue
from .server import make_server
from .store import Problem, Store


def main():
    p = argparse.ArgumentParser(description="企业内容工作台 · 内部本机版")
    p.add_argument("--data-dir", default=os.environ.get("WORKBENCH_DATA", "data"))
    p.add_argument("--tenant", default="internal", help="本机资料分区，不是身份认证")
    sub = p.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--enable-cli", action="store_true", help="允许网页调用现有Codex权益；实际调用费用未知")
    serve.add_argument("--open-browser", action="store_true", help="启动后打开本机工作台")
    sub.add_parser("doctor")
    media = sub.add_parser("media-index")
    media.add_argument("--category")
    media.add_argument("--keyword")
    sub.add_parser("android-doctor")
    inspect = sub.add_parser("android-inspect", help="读取已连接设备页面结构；不登录、不发布")
    inspect.add_argument("--binding", required=True)
    inspect.add_argument("--server", default="http://127.0.0.1:4723")
    inspect.add_argument("--output", required=True, help="保存本机页面XML，可能含个人资料；不得上传源码仓库")
    publish = sub.add_parser("publish-plan")
    publish.add_argument("--binding", required=True)
    publish.add_argument("--request", required=True)
    queue_add=sub.add_parser("dispatch-enqueue",help="任务入队；真实发布仍需平台执行器")
    queue_add.add_argument("--binding",required=True)
    queue_add.add_argument("--request",required=True)
    queue_add.add_argument("--key",required=True)
    queue_add.add_argument("--action",choices=["inspect_only","draft","publish"],default="inspect_only")
    sub.add_parser("dispatch-list")
    sub.add_parser("dispatch-recover",help="过期任务标记未知，保留设备隔离")
    queue_run=sub.add_parser("dispatch-run-inspection",help="在已连接安卓设备执行一个页面检查")
    queue_run.add_argument("--worker",default="local-inspector")
    queue_run.add_argument("--server",default="http://127.0.0.1:4723")
    queue_resolve=sub.add_parser("dispatch-resolve",help="确认旧进程停止后取消状态未知任务，不重发")
    queue_resolve.add_argument("--task",required=True)
    queue_resolve.add_argument("--reason",required=True)
    queue_resolve.add_argument("--worker-stopped",action="store_true")
    sub.add_parser("recover", help="确认没有运行中进程后恢复中断任务")
    project = sub.add_parser("create-project")
    project.add_argument("--file", required=True)
    job = sub.add_parser("create-job")
    job.add_argument("--project", required=True)
    job.add_argument("--file", required=True)
    for command in ["prepare-job", "run-job", "export-job"]:
        parser = sub.add_parser(command)
        parser.add_argument("--job", required=True)
        if command == "run-job":
            parser.add_argument("--timeout", type=int, default=90)
            parser.add_argument("--allow-unknown-cost", action="store_true")
        if command == "export-job":
            parser.add_argument("--output", required=True)
    args = p.parse_args()
    try:
        if args.command.startswith("dispatch-"):
            queue=DispatchQueue(Path(args.data_dir).resolve()/"dispatch.sqlite3")
            if args.command=="dispatch-enqueue":
                result=queue.enqueue(args.tenant,json.loads(Path(args.binding).read_text(encoding="utf-8")),json.loads(Path(args.request).read_text(encoding="utf-8")),args.key,args.action)
            elif args.command=="dispatch-list":
                result=queue.tasks(args.tenant)
            elif args.command=="dispatch-recover":
                result=queue.recover()
            elif args.command=="dispatch-resolve":
                result=queue.resolve_unknown(args.tenant,args.task,args.reason,args.worker_stopped)
            else:
                result=queue.inspect_next(args.tenant,args.worker,args.server)
        elif args.command == "media-index":
            result = media_index(args.category, args.keyword)
        elif args.command == "android-doctor":
            result = android_doctor()
        elif args.command == "android-inspect":
            target=Path(args.output).resolve()
            if target.exists():
                raise Problem("输出文件已存在；选择新文件，避免覆盖")
            binding=json.loads(Path(args.binding).read_text(encoding="utf-8"))
            inspector=AndroidInspector(args.server)
            try:
                result=inspector.connect(binding)
                content=inspector.source()
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open("x",encoding="utf-8") as f:
                    f.write(content)
                result["output"]=str(target)
            finally:
                inspector.close()
        elif args.command == "publish-plan":
            result = execution_plan(json.loads(Path(args.binding).read_text(encoding="utf-8")), json.loads(Path(args.request).read_text(encoding="utf-8")))
        elif args.command == "doctor":
            result = doctor()
        else:
            data = Path(args.data_dir).resolve()
            store = Store(data / "workbench.sqlite3")
            if args.command == "serve":
                if not 0 <= args.port <= 65535:
                    raise Problem("端口范围为0至65535")
                # Explicit recovery, not automatic re-execution.
                recovered = store.recover_interrupted()
                server = make_server(store, args.port, args.enable_cli, data / "runtime")
                print(f"工作台：http://127.0.0.1:{server.server_port} · 仅本机访问", flush=True)
                if recovered:
                    print(f"{recovered}个中断任务标记为状态未知，请人工核对。", flush=True)
                print("CLI网页生成：" + ("已启用；费用可能未知" if args.enable_cli else "未启用"), flush=True)
                if args.open_browser:
                    try:
                        webbrowser.open(f"http://127.0.0.1:{server.server_port}")
                    except (OSError, webbrowser.Error):
                        print("请手动在浏览器打开上方本机地址。", flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
                return 0
            if args.command == "recover":
                result = {"recovered": store.recover_interrupted()}
            elif args.command == "create-project":
                result = store.create_project(args.tenant, json.loads(Path(args.file).read_text(encoding="utf-8")))
            elif args.command == "create-job":
                result = store.create_job(args.tenant, args.project, json.loads(Path(args.file).read_text(encoding="utf-8")))
            elif args.command == "prepare-job":
                result = store.prepare(args.tenant, args.job)
            elif args.command == "run-job":
                result = run_job(store, args.tenant, args.job, data / "runtime", args.timeout, args.allow_unknown_cost)
            else:
                output = Path(args.output).resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(store.export(args.tenant, args.job))
                result = {"output": str(output), "status": "exported"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (Problem, ValueError, OSError) as error:
        message = str(error) if isinstance(error, Problem) else "参数文件或本机路径无效，请检查输入"
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
