# 电商运营壳 Windows 启动入口自动化验收

日期：2026-10-23（北京时间）。PR：[#15](https://github.com/dong120ask-eng/AIadmin/pull/15)，继续保持草稿，不合并main。

## 结论与证据

程序提交 `79d4860f5e2a960cd7a9be9ab0a302333a5f9df0` 已通过真实Windows启动入口回归。不是仅运行 `-CheckOnly`，不是模拟正常服务响应。

- [运营壳四组CI：39906417775](https://github.com/dong120ask-eng/AIadmin/actions/runs/39906417775)：Windows/Ubuntu × Python3.12/3.13全部成功。每组84项工作台回归、独立源码HTTP、解压包12项回归及HTTP成功。
- [电商套件CI：39906417735](https://github.com/dong120ask-eng/AIadmin/actions/runs/39906417735)：四环境的36项离线回归及14项安装/隔离/回滚回归成功，第五项跨环境发行包重现性也成功。
- 已下载并逐项核对两个Windows作业的JSON证据：每个Shell的 `tests_run=11`、`passed=true`，失败/错误/跳过均为0，11个case逐一标记passed。共44次生命周期测试成功。

| Windows CI Python | PowerShell 5.1.26100.33438 | PowerShell 7.6.6 |
|---|---|---|
| 3.12.10 | 11/11通过 | 11/11通过 |
| 3.13.16 | 11/11通过 | 11/11通过 |

Windows runner为Windows Server 2025，不能代表用户Windows11电脑。Linux不运行Windows专用用例，不能把Linux上的条件跳过算成PowerShell通过。

[Python3.12证据及日志](https://github.com/dong120ask-eng/AIadmin/actions/runs/39906417775/artifacts/12481271642)、[Python3.13证据及日志](https://github.com/dong120ask-eng/AIadmin/actions/runs/39906417775/artifacts/12481117365)。CI产物有保存期限，应结合代码、工作流和下述复现命令使用。

本次后续文档补录只修改说明，不改变该受测程序、测试或工作流；最新提交的CI以PR Checks为准。

## 修改内容

1. `scripts/start-ecommerce.ps1`：PATH中选取单个Python解释器；使用字面路径与Windows参数转义；真实HTTP就绪后才打开浏览器；保留UTF-8环境检查、启动及服务stdout/stderr日志；异常和超时返回非零。
2. 使用Windows Job Object的KILL_ON_JOB_CLOSE清理本次启动的服务与后代。纯内存声明原生接口，避免PS5.1 CodeDom在中文TEMP目录的临时编译失败，不安装编译器、不生成DLL、不修改全局策略。
3. `scripts/verify-ecommerce-windows.py`：真正调用PS5.1/7，从独立源码ZIP解压运行；正常路径运行实际应用，故障注入只修改隔离副本并明确标记。
4. `.github/workflows/ecommerce-pilot.yml`：两种Shell各自运行完整生命周期测试，失败时也上传JSON和诊断日志；保留四组操作系统/Python矩阵。
5. `docs/ECOMMERCE-PILOT.md`：更新启动、排障、复现及员工现场验收说明。

迭代中实际定位并修正：多Python路径返回数组、活动日志读取的Windows共享模式冲突、PS5.1临时编译目录失败，以及测试重启后误读历史PID。最终结论采用上方全部通过的运行，不采用先前失败运行。

## 11项实际验证

| 用例 | 验证内容 |
|---|---|
| 真实启动、合成操作、停止及重启 | 中文/空格/方括号/`&`源码与数据路径，数据路径末尾反斜杠；真实HTTP页面、配置、合成演示、305.00元合成贡献利润、ZIP回读；停止后同目录重启回读 |
| 仅检查 | 检查成功，但没有服务PID、HTTP服务或经营数据库 |
| 端口冲突 | 已有真实HTTP服务不得被误认就绪、不得被终止；本应用不创建经营数据库 |
| 错误数据目录 | 用合成普通文件阻止目录创建，非零退出并保留Python错误日志 |
| 就绪前异常退出 | 临时服务注入exit23，核对退出码与中文stderr |
| HTTP 503超时 | 临时故障服务实际响应503，核对真实探测发生、没有就绪标记、超时退出与端口清理 |
| 就绪后服务被终止 | 启动器检测异常、返回非零、进程退出且端口可用 |
| 启动器被强杀 | 不依赖finally，验证服务退出及端口释放 |
| 后代进程清理 | 实际应用临时副本额外启动合成等待子进程；强杀启动器后核对两级进程退出 |
| 旧停止信号 | 已有停止信号文件时拒绝启动，不产生服务PID |
| 日志目录错误 | 日志路径被普通文件占用时，在隔离TEMP内保留诊断并非零退出 |

进程验收持有本次创建进程的Windows句柄，避免PID复用误判；不按进程名称批量结束Python。所有服务仅监听127.0.0.1。

## 复现与边界

完整仓库、Windows及Python3.12+：

```powershell
python scripts/verify-ecommerce-windows.py --shell powershell --output build/ecommerce-pilot/windows-ps51-evidence.json
python scripts/verify-ecommerce-windows.py --shell pwsh --output build/ecommerce-pilot/windows-ps7-evidence.json
```

PowerShell7须已安装；测试不自动安装软件。正常员工入口仍为根目录 `启动电商运营壳.cmd`。详细字段与可选 `-LogDir`、`-StartupTimeoutSeconds`、`-StopFile` 见ECOMMERCE-PILOT.md。

本次只用合成数据和临时目录，不连接真实店铺、不调用模型、不打开浏览器、不执行采购、投放、改价或库存写入。未扩大只读运营功能。

## 员工现场仍需完成

- [ ] 用户Windows11电脑：双击CMD，默认浏览器正常打开，中文页面及操作可用。
- [ ] 真实控制台按Ctrl+C、关窗、重开；确认服务停止与端口释放。CI强杀和停止信号测试不代替实际控制台手势。
- [ ] 电脑已安装的Python、目录权限、安全软件及实际解压路径兼容；收集系统/Python版本与脱敏错误截图。
- [ ] 授权店铺人工导出的真实CSV/XLSX：核对字段、来源、统计区间、SKU前导零与仓库边界，至少抽查3个SKU。
- [ ] 库存风险、采购价异常与贡献利润逐项对账；缺少相应真实数据的项保持未验收。
- [ ] 人工异常备注、报告导出、停服备份恢复及运营人员首轮试用记录。

尚无员工实机或真实经营验收结果，不宣称已完成内部上线，也不据此开放店铺写入。
