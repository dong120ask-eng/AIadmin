---
name: video-format-adaptation
description: 将电脑已有长中短视频按指定时间段、尺寸和帧率转码，保持原片不覆盖，输出供不同平台发布的横竖版素材与实际元数据。
---

# 视频跨画幅处理

运行 [脚本](scripts/adapt.py)，默认输出计划，显式apply才处理真实本地视频。指定工作区内input/output及width/height，默认用补边保留原画面，不能默认裁掉字幕或人物。可选start/duration用于剪出明确片段；不从标题猜测镜头内容。

```text
python scripts/adapt.py --root 工作区 --input 已有视频 --output 新视频.mp4 --width 1920 --height 1080 --fps 30 [--start 秒 --duration 秒] [--apply]
```

需实际FFmpeg与FFprobe；可显式指定路径，依赖缺失交给software-install-maintain。脚本检查源文件、尺寸、非负时间和新输出，apply先读取源视频元数据，处理后核验目标视频宽高/音轨，再写指纹及元数据报告。字幕已烧录的竖片补边转横片会有空白边，横版重新设计应重新制作，不宣称补边等于高质量重剪。发布前按当前平台规则质检。
