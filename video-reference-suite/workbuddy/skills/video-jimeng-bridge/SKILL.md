---
name: video-jimeng-bridge
display_name: "即梦视频制作适配"
description: "将分镜与自有参考图转为即梦逐镜头制作任务和能力核验；用于即梦图生视频、关键帧、人物与产品参考及人工/API交接。"
description_zh: "将分镜与自有参考图转为即梦逐镜头制作任务和能力核验；用于即梦图生视频、关键帧、人物与产品参考及人工/API交接。"
description_en: "Plan original reference-based product videos and verify real artifacts within available tools."
version: "1.0.0"
author: "AIadmin contributors"
---


# 即梦视频制作适配

1. 读取 @references/handoff.md 和 @references/platform.md，先区分即梦、即创、豆包客户端与火山引擎API。
2. 检查已连接工具与当前账号实际功能。没有浏览器、官方CLI或API连接器时，仅提供网页人工任务，不声称已经提交。
3. 建立逐镜头表：输入图版本、提示词、目标比例、支持的时长、首/尾帧或参考模式、音频策略、预计预算（有依据才填）。
4. 指导员工先图片创作并检查关键帧，再到实际视频入口上传；多参考、真人、首尾帧和声音功能只在当前账号明确支持时使用。
5. 若真实API已连接，先阅读当日官方接口与权限文档，采用其鉴权、提交、查状态和下载方法；不得虚构URL、模型ID、参数或幂等能力。密钥不写进提示词和项目公开文件。
6. 保存真实任务回执、状态和文件；超时查询原任务后再判断重试。下载后核实可播放与内容，区分generated和reviewed。
7. 无法保持产品文字改实拍，无法稳定口型改旁白或实拍，真人被限制不得绕过。
