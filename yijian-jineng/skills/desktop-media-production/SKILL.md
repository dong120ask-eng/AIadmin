---
name: desktop-media-production
description: 在电脑生成中文卡片、配音字幕短视频并核验文件，随后将保存好的素材交给手机或模拟器发布。
---

# 电脑生成并保存
使用scripts/media.py。cards调用本包render_cards.py；video调用本包make_video.py；verify-video调用本包verify_output.py。源脚本来自用户本机制作工具，已适配ffmpeg路径和条件健康检查。
命令：PY media.py cards|video --root ROOT --spec 输出规格JSON --output 新产物目录。视频依赖见 requirements-video.txt，edge-tts需要联网；无网络或模型/配音依赖不齐时报告，不称完全离线。
先输出到outputs/批次/job/cards或video，不直接写手机。每个最终文件与正文、规格、字幕、封面、QA和版本一并保存。中文检查字体与截断；视频检查音画、画幅、字幕、编码、时长和平台当前要求。
产品regulated_health标记由实际产品属性确认，不能把药品稿标成普通品逃避内容审核。
图文和音视频制作方法及版权/规格要求由当前宿主根据用户材料补齐；安装依赖是软件技能职责。成品通过审核后platform-publish-router入队。
