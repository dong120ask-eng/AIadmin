# Short Drama Skills Suite · 一键短剧技能套装

普通话优先的原创短剧工作流，适合 Codex、DeepSeek Harness、WorkBuddy 支持的 SKILL.md 加 Python 执行环境。

**目前可以编排候选样片生产，尚未完成真实模型、三个客户端和平台上传的端到端验收。** API Key 由本次对话经 stdin 或 ARK_API_KEY 环境变量输入，不放在技能、配置和 Git 中。仅有文本模型Key不足以生成视频，还需实际开通的文本/视频模型ID与预算。

## 八个技能

| 技能 | 工作 |
|---|---|
| short-drama-hub | 对话入口、项目初始化、环境检查、阶段编排 |
| drama-market-research | 可核验案例、反例、数据口径、原创试验假设 |
| cn-drama-director | 18类框架、观众与情绪承诺、人物和逐集任务、伏笔回收 |
| global-short-drama | 方舟写稿、有限返修审稿、视频任务、下载、FFmpeg合成 |
| drama-assets | 角色场景计划及授权参考图/音频/视频清单 |
| drama-postproduction | 字幕、封面、混音及黑帧/静音候选检测 |
| drama-release | 审稿与最终文件审阅校验、供片资料、回执去重 |
| drama-growth | 同条件加权留存/完播/续看/互动复盘 |

## 快速开始

Python 3.10+，FFmpeg/ffprobe（字幕烧录需libass）。八个技能需放在同一个skill root。仓库内的skills目录可作为技能源。

```shell
python tools/deploy.py --target codex
python tools/deploy.py --target deepseek --root <实际技能目录>
python tools/deploy.py --target workbuddy --root <实际技能目录>
```

默认预览；用户决定安装后增加 `--apply`，已有文件夹会拒绝覆盖。WorkBuddy优先使用其实际UI导入目录/ZIP；直接复制必须确认客户端已发现技能。DeepSeek Harness版本及工具权限也需要实际检查。

对话示例：`用 short-drama-hub 制作原创普通话悬疑漫剧，6集，每集1分钟，先做第一集。文本模型ID……，视频模型ID……，生成预算……。` Key只在会话传入，不写到示例命令。

```shell
python skills/short-drama-hub/scripts/project.py init --topic "原创话题" --episodes 6 --minutes 1 --out projects/demo
python skills/short-drama-hub/scripts/project.py doctor --config projects/demo/project.json
python skills/global-short-drama/scripts/drama.py plan --config projects/demo/project.json --out runs/demo
```

导演技能生成v2导演指令并设置brief_path；配置真实模型和预算后执行`run --episode 1 --until-ready --key-stdin`。生产停在样片审阅检查点。完整命令、宿主差异、目录与参数见 [统一功能部署操作说明](短剧技能套装_功能部署操作与优化说明.md)。

## 质量与市场边界

框架已经包含主流叙事要素，不能保证爆款。当前三个红果案例仅有分享简介，未观看全集。声音、脸型、表演和字幕需要真实样片看听；机械QC和模型编辑分数不代替这些检查。

`ark.review_model`可选独立审稿模型；固定场景和相邻镜头进入视频提示。音视频参考按实际模型启用能力标记及上限，默认不启用。发布审阅声明绑定视频/字幕SHA256，变更后失效。

平台模块目前负责准备与回执，**没有红果或全平台自动上传SDK**。红果整剧供片与短视频后台上传不同，需要真实平台接入、账号和业务手续。详细问题、已优化项与优先级见 [市场审查与升级记录](市场适配审查与升级记录.md)。

## 验证与打包

```shell
python verification/run_checks.py
python tools/build_bundle.py
```

测试含真实FFmpeg合成/烧字幕/封面/混音，API为模拟响应，不消耗方舟费用。[本次验收摘要](verification/verification-summary.json)列出真实验收边界。官方技能校验器缺PyYAML时仅有备用结构检查，不报告官方校验通过。build_bundle会在当前目录生成完整套装和单技能ZIP。

`.gitignore`排除密钥、cookies、成片和运行目录；仍需在提交前检查实际暂存内容。用户项目、演员素材和付费生产状态不属于本代码库。
