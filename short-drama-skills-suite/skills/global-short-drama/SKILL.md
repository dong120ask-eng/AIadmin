---
name: global-short-drama
description: 多题材短剧生产，接收导演指令或话题，按类型规则调用火山方舟写稿、审稿返修、生成普通话视频与发布包，并在具备权限后协助平台发布。
---

# 短剧生产与分发

这是双技能中的生产技能，与 cn-drama-director 配合：导演技能生成 director-brief.json 和 project.json，本技能验证交接后生产。第一阶段默认普通话中国市场；可以为海外平台导出中文成片，不把“海外分发”误当作已本地化。多语言由用户后续显式开启。

新项目默认多题材质量模式。读取 [类型规则库](assets/genre-frameworks.json) 的选定主类型和辅助类型，不把所有故事写成逆袭。genre=auto时优先采用导演选择，否则由文本模型选择并保存genre.json；已有明确类型不额外分类。genre_rules进入故事圣经、逐集分镜与编辑审稿提示，不能只给配置贴标签。

可选配置ark.review_model采用与写稿不同的编辑模型，留空复用text_model；review报告明确记录是否实际采用不同模型。新圣经locations包含固定场景id、description、lighting、props、axis，分镜scene_id引用该场景；旧圣经未提供locations时保留兼容，但不能宣称场景设定已完整。地点、道具、轴线和相邻镜头进入视频请求，只生成当前镜头。模型输出的连续性仍需观看验收。

把用户给定的话题、集数、每集分钟数和方舟模型配置转换为可续跑的短剧项目。运行目录与技能目录分开；支持用户直接在对话框提供本次 API Key，代理通过标准输入传给脚本；也兼容 ARK_API_KEY 环境变量。不写入配置、技能、长期记忆或输出日志，不回显实际密钥。

## 对话触发与立即生产

用户触发本技能或导演技能后，检查本次对话及已有配置里的话题、集数、分钟数、text_model、video_model 和 API Key。已提供的信息不要重复索取。缺少密钥时可直接问“请提供本次火山方舟 API Key”，并简短说明聊天输入会留在宿主聊天记录；用户选择本机环境变量也可继续，不强制其设置环境变量。

用户同时提供完整参数并说开始生产，即授权按约定预算启动本次生产，不再重复询问是否可以使用密钥。配置里没有预算时先采用示例调用次数/秒数上限并展示价格未知；规模超限或付费范围变化时再确认。仅有 Key 不足以确定模型 ID，不能擅自猜测模型或绕过开通限制；集中补问缺失模型与制作参数。

接收密钥后只回复“已收到本次密钥”，不要输出前后缀、长度或完整值。代理使用宿主受保护的凭据传递通道（如可用）或子进程 stdin：调用 drama.py 时加 --key-stdin，首行输入密钥。不把密钥写进 shell 命令、命令行参数、临时文件、导演 JSON、project.json 或脚本源码。标准输入只避免程序落盘与回显，不能承诺聊天/工具记录不保留用户输入。当前会话续跑复用已提供密钥；换会话若无凭据则请求重新提供，不把记住密钥当作长期记忆任务。

参数齐全时加载 cn-drama-director，形成指令与配置，执行 plan 后立即 run --episode 1。向用户持续报告真实阶段；不要在只有剧本或任务 ID 时停止并称样片完成。用户说“只生成剧本”或中途修改目标时按最新范围执行。平台发布仍需原有授权与权限，生产授权不扩大到上传/公开发布。

## 开始

最少输入：topic、episodes、minutes_per_episode、ark.text_model。文本模型和视频模型需要分别在用户账户开通；不能把文本模型当作视频或配音模型。用户未指定时，先按中文源剧本、9:16、动画风格制作计划，海外市场语言与目标平台采用配置里的显式列表。不要擅自选定付费模型 ID，采用用户控制台给出的模型 ID 或推理接入点 ID。

读取 [配置与运行](references/workflow.md)。复制 assets/project.example.json 为项目配置；脚本不依赖第三方 Python 库，成片需要 FFmpeg/ffprobe。project.json 的 brief_path 指向导演技能交付的指令 JSON；plan 会验证协议，生成前需保持文件不变。先运行 plan，向用户展示总时长、各语言镜头数量、费用估算或“价格未知”、缺失权限。制作大系列先做第 1 集样片，检查人物与音色一致性后再扩展。

```powershell
python <skill>/scripts/drama.py plan --config <project.json> --out <run-directory>
python <skill>/scripts/drama.py write --config <project.json> --out <run-directory> --episode 1
python <skill>/scripts/drama.py review --config <project.json> --out <run-directory> --episode 1
python <skill>/scripts/drama.py video --config <project.json> --out <run-directory> --episode 1
python <skill>/scripts/drama.py render --config <project.json> --out <run-directory> --episode 1
python <skill>/scripts/drama.py package --config <project.json> --out <run-directory>
```

一键入口：`python <skill>/scripts/drama.py run --config <project.json> --out <run-directory> --episode 1`。代理重复调用run，在pending时短暂停留后查询，用户无需逐条操作。按集依次写稿→审稿/有限返修→推进一个视频任务→镜头齐全后合成→导出；同一集未审定不做视频，第一集尚未完成不提前写后续素材。审稿失败返回review_failed并保留报告，代理需向用户说明具体问题，不无限重试；只执行一轮推进并返回状态，不能把pending报成整剧完成。真实发布仍走下方授权与平台接入流程。

需要进程自动推进到样片检查点时加--until-ready --max-steps 300 --poll-seconds 10；同一进程只读取一次stdin密钥，输出每步状态。到成片review、审稿失败或有限步数上限即停，不自动上传。配置execution.max_inflight_video_tasks默认3，先提交至有限在途数，再轮询不同任务，避免只等待首镜；状态仍顺序保存。宿主支持进程会话时读取该会话进度，不另起重复进程；每60秒向用户报告真实状态。

方舟 API 直接内置在 scripts/drama.py：`https://ark.cn-beijing.volces.com/api/v3/chat/completions` 与 `https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`。鉴权为 `Authorization: Bearer <本次密钥>`。这是地址与调用实现，不含用户实际密钥。对话密钥运行入口为 `python <skill>/scripts/drama.py run --config <project.json> --out <run-directory> --episode 1 --key-stdin`，密钥由代理传入标准输入，不加到命令字符串中。

允许在已有授权及预算内连续执行；新付费范围先确认，不通过反复调用消耗预算。用户插话视为任务调整；暂停时保留已有任务 ID。脚本一次 video 命令只提交或查询一个镜头，不持续阻塞轮询。没有 task ID 的网络超时标为 unknown_submission，不自动重投。

## 创作与多语言

write 分两层：系列故事圣经、逐集分镜，再逐语言本地化。圣经包含人物固定 ID、外形、服装、动机、地点、伏笔和集间因果。剧本应有开场冲突、升级与结尾悬念，结局兑现伏笔，不机械套用每集同一反转。跨集接续以上一集完整剧本为依据。

新稿使用v2结构：story明确目标/阻力/策略/选择/后果/兑现/承接，镜头注明scene_id、purpose、audio_kind与单一speaker；伏笔记录对应镜头和引入/回收集。对白按规划语速预检，允许无台词环境镜头，避免每镜抢话。视频提示明确带入出场人物的固定外形、服装和声音描述；这只是更完整的模型输入，不保证绝对一致。

生成视频前读取 [质量检查与返修](references/quality.md)，执行review：十维评分各有真实镜头证据、主类型标准逐条检查；默认无0分且至少16/20分，无严重问题，最多2轮返修。通过后的报告绑定剧本和上下文，变更后不能继续用旧报告提交视频。分数仅为编辑参考，不是爆款概率。关闭quality仅用于用户明确要求的导入/低成本测试，并标记未编辑验证。

本地化保留事件与人物 ID，调整名字译法、口语、文化隐喻、货币及字幕阅读速度；不同市场的剧情改编另建项目，避免翻译版本改变主线。区域偏好只作创作假设，研究市场时使用最新可靠来源，不承诺爆款或收益。翻译要逐语言检查，禁止把机器翻译完成等同于母语审校通过。

默认每语言分别生成含本地语言对白的视频；这是原生音频路线，成本随语言增加。模型未支持音频或语种效果不合格时，改为共享画面 + 已授权 TTS/人工配音：按 [媒体替换](references/workflow.md) 提供 audio 文件，测量时长、同步字幕并重新渲染。没有配音能力就明确停在待配音，不把静音视频称为多语言成片。不得克隆未授权真人音色。

## 样片与成片检查

逐镜头检查角色外形、人数、服装、场景轴线、文字伪影、对白语言和发音。脚本做媒体流、时长及输入变更检查，人工/视觉审片不可省略。需要参考图时加载同级drama-assets，配置assets.manifest_path并确认reference_images_supported；支持reference_image、首帧或首尾帧载荷，模式不可混用，实际权限和限制以官方文档为准。下载先核验视频流再落正式镜头。参考图接入不等于绝对锁脸、音色一致或唇形同步，这些仍需样片验收。

将后期交给drama-postproduction，发布准备及回执交drama-release，真实数据反馈交drama-growth；可用short-drama-hub统一触发。无台词镜头不产生空字幕。镜头/配音或master变化会使缓存QC失效，重新渲染再导出，不能把存在的旧文件当成当前作品。

字幕初稿以镜头时间划分，未经 ASR/人工校时不能判定发布就绪。添加授权音乐、封面、片头片尾或备案信息时须计算在单集时长内；调整后重新做时长、可读性、黑帧、响度、版权与地区适龄检查。不要靠循环旧画面或加速对白凑分钟数。

## 平台发布

读取 [平台接入与发布](references/platforms.md)。package 创建完整性报告及发布清单，不上传、不发布。代理通过当前可用官方连接器或登录后的浏览器协助真实发布；没有权限的平台保留 blocked_access。

红果的整剧供片与抖音公开视频是不同发布业务；不得用发抖音视频替代红果上架。海外专业短剧应用也常有供片合作要求，不编造开放接口。每次上传、提交审核或公开发布前，按用户的 interruptible-execution 约定确认明确的平台、账号、集数、语言、可见性和材料。先展示可审阅成片及资料；发布成功必须取得平台作品 ID/URL 或后台回执，审核中与已上线分开记录。

交付报告说明：完成哪些阶段、哪些仅做离线测试、缺少哪些模型权限/配音/平台账号；引用真实产物路径。完整流水线的完成条件是目标平台回执齐全，不是生成了发布清单。
