# 企业内容工作台 MVP — 本轮开发与验收

## 用户目标

公司内部先跑通真实产品的内容服务，后续再软件化与收费。用户授权安装Codex CLI、配置开发环境并开始开发；八类创作任务需要共用产品项目档案，先文章与短视频制作包，其他内容类别可作为任务类型。需要真实源码、运行说明与验证结果，不能只交规划。我们尚未收到真实产品、平台登录和支付商户资料。

## 本轮范围

采用 Python 3.12 标准库 + SQLite + 本地HTML/CSS/JS，零外部运行依赖。建立可运行的内部工作台与命令行。它是内部单操作者工具，不是开放互联网SaaS；默认仅监听127.0.0.1。没有实际接入时明确显示：视频成片未接入、浏览器自动发布未接入、支付未接入、DeepSeek/火山未接入。工具返回状态不能假装实现。

### 必须实现

1. 项目档案：tenant_id、project_id、产品名称、facts[{text,source}]、待证实主张、素材引用、目标人群假设、业务目标、品牌口吻、预算。缺失信息保持空或null；事实必须附来源标签，至少区分“用户提供”和“外部验证”。创建与查看项目；展示录入表单。
2. 账号：绑定企业/项目、平台、唯一账号标识、显示名称、定位、credential_ref（仅引用）、发布授权。不得存密码或Cookies。跨企业、项目不可串号。
3. 共享平台库：小红书、抖音、头条号（文章和微头条）、公众号、视频号、快手、B站、喜马拉雅作为候选，标记格式规则待核实、发布适配器未接入。不要声称今天已核实上传规则或自动发布可用。可用类别需作为“候选类型”标注。
4. 八类任务：article、image_text、short_video、long_video、audio、novel、music、short_drama；topic、targets、account_id、预算、幂等键、version。任务创建要求企业项目匹配；重复同一键返回原任务，冲突负载返回409；类型与账号平台不适配则拒绝或明确待核实。不得自动扩大发布范围。
5. 制作包：根据产品事实、选题、口吻、形式产生完整执行brief.md、事实清单、证据缺口、产物检查清单、机器可读manifest.json。文章要求标题备选、摘要、结构、正文与来源；视频要求开头、逐镜脚本、旁白、字幕及成片检查；八类各有自己的模板。未连接模型的模式仅交付制作任务包，UI明确“任务包已生成，内容尚未生成”。不能把模板当模型成品。
6. Codex CLI 适配器：doctor检测 CLI 可执行性及认证状态，不读取或输出认证令牌；支持显式配置CODEX_BIN路径与环境继承；用codex exec --json --sandbox workspace-write -C <隔离工作目录>调用，prompt从stdin输入，不用shell，不使用绕过审批开关，不指定模型覆盖默认设置。每个生产任务有独立工作目录，内含任务包与只读参考，要求生成结果只写在outputs里。只有操作者显式启用CLI生成时才运行；命令行提供 run-job。CLI失败/未安装/超时须诚实状态；每任务日志写脱敏结构事件和最后结果，不能保存令牌。限制时间和返回数据大小。模型调用计费未知要标记unknown，不伪报0。网页不能接受任意shell/CLI路径/参数或启动任意命令。
7. 提供离线默认recipe模式；实际codex模式输出文章Markdown或视频脚本JSON，按内容类型验证outputs结果存在、非空、字段完整。校验失败标记failed且不能进入审核通过。不要只依据进程exit0判成功。成本未知情况下显式提示；本轮不要在测试中发实际模型请求。
8. 状态：planned、brief_ready、running、draft_ready、checked、awaiting_approval、blocked、failed等。发布状态单独保存not_connected/draft/submitted/under_review/published/unknown；未连接时任何发布请求不能成为published。审核需记录检查结果。拒绝非法跳转；修改产物后不能沿用旧审核。首次MVP允许人工检查清单确认，明确该检查不等于事实已自动核实。检查项facts、rights、format、ai_label均通过才能checked；发布还要授权、账号核验与真实适配器，本轮发布按钮说明缺少适配器并保持blocked。
9. SQLite持久化、时间戳UTC展示上海时区、审计事件、内容sha256；包导出ZIP仅包含当前企业项目任务的文本交付，不包含DB、凭证、完整日志与其他企业资料；导出路径固定服务端控制。合法重试仅failed/blocked等，不重复生成running任务；启动检测遗留running标记unknown或blocked，不自动重跑。若并发存在，用数据库原子占用防重复运行。
10. UI 中文，简洁专业，桌面可用且手机自适应：左导航或顶导航、能力状态提示、项目创建、项目概览、任务创建（8类）、任务列表状态、任务详情、产物查看、下载包、审核记录与下一步。不可给用户看一堆内部字段；关键字段解释清晰。可读的空状态，不默认塞假账号和假爆款。
11. CLI: python3 -m workbench serve / doctor / create-project / create-job / prepare-job / run-job / export-job（精简可用）。README包含Windows PowerShell、Linux运行方式、Codex CLI安装和登录说明、CODEX_BIN配置、示例与实际范围。提供scripts/setup.ps1和scripts/setup.sh仅检查Python/安装本项目，不擅自登录或购买，不需要venv依赖安装。创建Dockerfile可选，不是必须。
12. 测试：持久化重启、租户及项目隔离、幂等键负载冲突、状态非法跳转、审核要求、导出不越界、path traversal、CLI fake可执行程序隔离与真实产物校验、CLI失败/超时、发布未接入不能published、HTTP接口与XSS安全。UI smoke用真实本地服务验证。可使用Node/Python现有工具，不引入依赖。

## CLI驱动开发记录

本轮代码由Codex CLI开发，然后主对话审查并验证。CLI研发进程不等于应用已接入DeepSeek、视频模型或发布平台。开发任务交付源代码，内容任务交付制作包或经验证的内容产物，分清二者。

## 架构与安全

HTTP服务仅本机使用，禁止绑定0.0.0.0；校验Host、Origin，限制请求体，使用same-origin防护令牌或等效措施，禁止CORS开放，HTML用textContent等安全渲染。无身份系统不得称真实安全多租户；tenant_id只是本地资料隔离，公共部署前要补身份认证/服务端授权。不要开发伪支付宝付款模拟器；能力表说明后续需商户接入、验签、权益账本和正式回调验证。

## 完成动作

运行python -m unittest discover及必要smoke checks，修复所有问题，记录测试与已知限制在DELIVERY.md。不要修改SPEC.md降低验收条件，不伪造结果。提交前不要将SQLite数据库、生产输出、日志、认证文件、node_modules或临时文件加入版本库。
