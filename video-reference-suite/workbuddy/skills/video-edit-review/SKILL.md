---
name: video-edit-review
display_name: "视频剪辑交接与质检"
description: "组织实际视频素材、配音、字幕和剪辑交接并按时间码质检；用于剪映组装、视频验收、返工和真实交付状态核查。"
description_zh: "组织实际视频素材、配音、字幕和剪辑交接并按时间码质检；用于剪映组装、视频验收、返工和真实交付状态核查。"
description_en: "Plan original reference-based product videos and verify real artifacts within available tools."
version: "1.0.0"
author: "AIadmin contributors"
---


# 视频剪辑交接与质检

1. 读取 @references/handoff.md，核对实际素材、定稿脚本和声音版本；缺文件标待补，不制造占位MP4或虚构路径。
2. 输出CSV或Markdown交接表：镜头、源文件、素材入出点、时间线入出点、声音入点、字幕与时间、转场、音效、备注。
3. 核对时长、文件存在与连续性，字幕逐句校对专有名词。字幕SRT须有实际时间依据；未对齐时只交文稿，不伪造准确字幕时间。
4. 有真实剪辑工具才执行工程创建和导出；否则给剪映员工步骤。普通CSV或自定义JSON不能称为可导入剪映工程。
5. 检查实际视频的人物、包装文字、手部动作、画面连续、声音同步、字幕、主张证据、授权和标识。每项记录检查方式、时间码与证据，无法检查的为uninspected。
6. 输出问题严重度、返工镜头、复检条件和可交付/需返工/信息不足。产品身份错误、虚假主张、素材使用范围不符、文件不可播放阻止放行。
7. 导出参数按目标平台当前要求核对；内部可先用1080×1920竖屏MP4/H.264、AAC、匹配素材帧率作为工作目标，不能当全平台强制标准。
