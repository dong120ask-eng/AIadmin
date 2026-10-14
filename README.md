# AIadmin · 企业内容工作台

可运行的企业内部本机工具：录入产品事实和来源，建立内容任务，生成制作任务包，调用已配置的Codex CLI制作文本草稿，人工审核后导出交付包。

**目前已实现制作包与任务管理；真实CLI生成尚未通过当前环境的最小调用测试。视频、音频、音乐成品生成、自动发布、DeepSeek／火山及支付宝收款未接入。**

## 立即运行

需要Python 3.12或更新版本，应用本身没有第三方Python依赖。

Windows PowerShell，进入解压后的项目目录：

也可以直接双击`start-windows.bat`，它检查Python版本并启动本机工作台、尝试打开浏览器。保持启动窗口打开。首次Windows实机运行仍需验证；需要你准备的资料与操作见`USER-CHECKLIST.md`。

```powershell
py -3 -m unittest discover -v
py -3 -m workbench serve
```

Linux / macOS：

```bash
python3 -m unittest discover -v
python3 -m workbench serve
```

在同一台电脑打开 http://127.0.0.1:8765 。使用流程：新建产品项目 → 录入真实事实及来源 → 创建文章或短视频任务 → 查看制作包 → 下载交付包。

默认数据保存在项目目录的`data/`，重启保留。可以用`--data-dir`切换到其他持久化目录。数据库及运行目录不加入Git或源码压缩包；需要自行备份本机数据。

本工具只监听本机地址，不向公网开放。资料分区用于避免项目串数据，**不是用户身份认证**。同一操作者可切换所有分区，因此不能作为多客户在线SaaS使用。一个数据目录只运行一个服务实例，不要在生成任务仍运行时启动第二个服务或执行recover。

## 当前能力

| 能力 | 本轮状态 |
| --- | --- |
| 产品项目、事实来源、人群假设 | 已实现 |
| 账号资料与项目绑定 | 已实现；不保存密码或Cookies、不执行登录 |
| 八类内容任务与各自制作包 | 已实现 |
| 持久化、幂等、并发占用、状态记录 | 已实现 |
| 审核与ZIP导出 | 已实现；审核为人工确认 |
| Codex CLI安装与认证检测 | 已实现，当前环境检测通过 |
| CLI任务适配器 | 已实现并通过隔离测试；真实模型执行仍阻塞 |
| 图片／视频／音乐／音频成品 | 未接入 |
| 浏览器或官方接口发布 | 未接入；请求发布会阻塞，不伪报成功 |
| DeepSeek／火山模型 | 未接入 |
| 支付宝订单、验签和权益控制 | 未接入 |

八类：文章、图文、短视频、长视频、音频、小说、音乐、短剧。平台候选库包括小红书、抖音、头条号、公众号、视频号、快手、B站、喜马拉雅；库内类型仅作为研究候选，规格与账号权限必须另行核查。小说、音乐暂不配置投稿平台，仅制作创作任务包。

## 配置Codex CLI

已经全局安装Codex CLI时，本工具会查找PATH中的`codex`。也可使用`CODEX_BIN`指定实际可执行文件。项目还支持探测官方npm包的本地原生二进制。

可选本地安装（需要Node.js、npm及网络；本轮验证的版本是0.162.1）：

```bash
npm install --prefix .tools/codex @openai/codex@0.162.1 --no-audit --no-fund
```

Linux / macOS从本地包执行登录：

```bash
.tools/codex/node_modules/.bin/codex login
python3 -m workbench doctor
```

Windows使用npm安装生成的入口登录：

```powershell
& .\.tools\codex\node_modules\.bin\codex.cmd login
py -3 -m workbench doctor
```

如果Windows原生可执行文件没有被自动找到，使用`CODEX_BIN`指定官方包内的`codex.exe`，不要指定需要shell的`.cmd`作为应用执行器。当前交付环境是Linux；Windows启动说明尚未实机验证。

`doctor`只验证安装与认证，不发模型请求，也不把认证成功等同生成可用。不要把认证文件、API密钥或Cookies发给别人，也不要放进项目资料。

默认网页不调用模型。只有确认使用自己的现有额度、费用可能未知后才启用：

```bash
python3 -m workbench serve --enable-cli
```

这会允许本机网页按钮调用Codex。任务里的人民币预算目前只是计划字段，**不能替代供应商实际计费与硬性费用限制**；未接入计费接口前，不得将它用于商业自动扣款或承诺费用封顶。应用不会自动充值或购买服务。

每次生成在独立目录中执行，输入资料与结果分开。适配器运行`codex exec --json --sandbox workspace-write`，不使用审批绕过开关、不覆盖默认模型、不修改全局认证与配置。输出必须是真实且完整的`outputs/result.json`；只有进程退出0仍不足以认定生成成功。

## 命令行操作

以下示例资料清楚标注为演示，不是真实产品宣传。Windows将`python3`替换为`py -3`。

```bash
python3 -m workbench --tenant demo create-project --file examples/project.json
# 读取返回的项目id，替换下列PROJECT_ID
python3 -m workbench --tenant demo create-job --project PROJECT_ID --file examples/article-job.json
# 读取返回的任务id，替换下列JOB_ID
python3 -m workbench --tenant demo prepare-job --job JOB_ID
python3 -m workbench --tenant demo export-job --job JOB_ID --output delivery.zip
```

只在明确允许使用模型权益、已知费用可能未知时执行：

```bash
python3 -m workbench --tenant demo run-job --job JOB_ID --timeout 90 --allow-unknown-cost
```

文章产物是文字草稿；视频产物是脚本与分镜；音乐产物是歌词／创作需求。只有以后接通媒体生成与合成，才能生成真实媒体文件。

`recover`用于确认生成进程已经退出后的中断处理。服务重新启动时遗留running会标为unknown并等待人工确认，不会自动重复运行。

```bash
python3 -m workbench recover
```

## 检查与测试

```bash
python3 -m unittest discover -v
node --check workbench/static/app.js
```

可选DOM交互测试依赖JSDOM（只用于测试，非应用依赖）：

```bash
npm install --prefix .qa-tools jsdom@26.1.0 --no-audit --no-fund
JSDOM_MODULE="$PWD/.qa-tools/node_modules/jsdom" PYTHONPATH=. python3 scripts/ui-smoke.py
```

它检查真实HTTP服务上的页面交互与安全文本渲染，不等同真实浏览器视觉测试。当前环境的浏览器下载失败，因此未声称桌面／手机视觉检查已通过。

## 模块

- `workbench/store.py`：持久化、项目隔离、幂等、状态与导出。
- `workbench/recipes.py`：八类制作任务包和生成交付结构。
- `workbench/runner.py`：CLI探测、超时、输出检查、独立执行目录。
- `workbench/server.py`：本机HTTP接口、Host／Origin／请求令牌校验。
- `workbench/static/`：中文工作台。
- `tests/`：工作流、隔离、导出、CLI适配器与HTTP测试。

## 下一轮真实接入

先排查当前CLI最小调用阻塞，选择一个真实产品和一个选题，完成真实文章草稿与短视频脚本，再接视频生成服务。选择一个自有账号验证浏览器／官方接口登录、上传、审核与作品结果。付款能力另建商户接入、服务端验签、订单与权益账本，不以付款截图或用户回复作为自动授权依据。

公共部署前还需身份认证、服务端项目授权、TLS、生产级应用服务、受控队列、供应商成本计量、备份和发布审计。此MVP不应直接放在公网作为收费服务。

## 文档依据

- Codex CLI官方文档：https://developers.openai.com/codex/cli
- 非交互执行：https://developers.openai.com/codex/noninteractive
- Python SQLite：https://docs.python.org/3.12/library/sqlite3.html
- Python本地HTTP服务：https://docs.python.org/3.12/library/http.server.html

这些链接用于实现依据；当前平台规格与商业接入仍需各自核查。

## 媒体发现与执行计划扩展

打开本机工作台的`/media.html`查看分类清单。当前仅有发现登记、部分渠道证据及浏览器／安卓执行计划，未接通真实发布。使用方法与覆盖限制见[PUBLISHING-DEVELOPMENT.md](PUBLISHING-DEVELOPMENT.md)。
