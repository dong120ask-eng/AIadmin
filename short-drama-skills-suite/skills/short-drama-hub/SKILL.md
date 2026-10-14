---
name: short-drama-hub
description: 一键短剧总控，串联导演策划、资产一致性、方舟审稿生产、后期、平台供片和数据复盘，支持对话提供本次API Key。
---

# 一键短剧总控

与同级的cn-drama-director、global-short-drama、drama-assets、drama-postproduction、drama-release、drama-growth、drama-market-research一起部署。这些是当前套装全部技能，按阶段加载，不一次塞入所有参考资料。仅调用当前宿主实际提供的文件、shell、网络、浏览器和模型能力，不跨聊天发送任务。

用户只需话题、集数、每集分钟数及可用方舟文本/视频模型配置，可在对话框提供本次Key。已有参数不重复索取；按生产技能--key-stdin传递，不落项目文件或长期记忆，不回显。用户给齐参数并要求生产即启动当前预算内的样片制作，不重复确认同一生产动作；没有参数只一次补问缺项。平台账号与发布授权独立。

## 启动与进度

1. 用scripts/project.py init创建独立项目，再doctor离线检查Python、FFmpeg/ffprobe、模型字段。输出缺项不冒充API权限验证；缺密钥但用户已在聊天提供时采用stdin即可。
2. 需要当前市场对标时先加载drama-market-research，再由cn-drama-director将证据、反例和原创试验写入v2导演指令，更新project.brief_path。展示plan规模和价格未知或估算，超出预算再确认。
3. 先写第一集。需要参考图时加载drama-assets，按账户模型能力和素材权利准备清单；不自动上传未经确认素材。配置清单后用新run开始生产。
4. 调用global-short-drama的run --episode 1 --until-ready --key-stdin，默认最多300个推进步骤，等待时每次不超过60秒。进程输出每步JSON用于报告进度；宿主执行超时取回会话继续读，不启动另一个同run进程。Ctrl+C保留任务状态，不保存密钥。支持在配置范围内最多3个服务端视频任务同时生成，一次本地请求仍顺序落盘，不并发修改state。
5. 到review或review_failed检查点停下，交可观看样片和报告，确认后再扩展。后续集按run顺序写稿、审稿和生产，避免改前集却提前生成后集。
6. 加载drama-postproduction补字幕、封面、声音及成片检测。听校和视觉检查合格后由drama-release准备供片，明确确认实际上传/提交/公开发布，再核对回执。没有上传能力就交材料与缺口，不伪称全自动上线。
7. 有实际观看数据才加载drama-growth复盘并给下一版本指令；不自动创建监控、刷量或承诺爆款。

## 状态含义

submitted/running/downloaded只表示镜头任务；editorial_pass只是模型编辑通过；review是成片待实际审阅；package_created只表示发布清单生成；published必须有真实平台回执。失败保留原始稿、返修、任务ID与媒体；未知提交先核对供应商。禁止为“无人值守”跳过预算、样片、账号、合同或发布确认。

## 本地工具

```text
python <skill>/scripts/project.py init --topic <话题> --episodes 6 --minutes 1 --out <项目目录>
python <skill>/scripts/project.py doctor --config <项目目录>/project.json
```

将自动化结果视为候选作品。故事因果、角色表演和真实观看数据共同决定质量；类型框架、主观分数或Key鉴权成功都不证明能出爆款。
