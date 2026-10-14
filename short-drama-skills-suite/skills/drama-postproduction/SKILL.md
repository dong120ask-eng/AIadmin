---
name: drama-postproduction
description: 对已生成短剧做字幕时间轴校验与烧录、封面抽帧、授权背景音乐混音和黑帧静音检测，生成成片检查报告。
---

# 短剧后期与成片检查

scripts/media.py使用Python标准库与FFmpeg/ffprobe。输入为真实成片，输出新文件，不覆盖输入。提供以下实际命令：

```text
python <skill>/scripts/media.py subtitles --video <master.mp4> --cues <timed-cues.json> --out <aligned.srt>
python <skill>/scripts/media.py burn --video <master.mp4> --srt <aligned.srt> --out <delivery.mp4>
python <skill>/scripts/media.py cover --video <master.mp4> --time 1 --title <标题> --font <中文字体.ttf> --out <cover.jpg>
python <skill>/scripts/media.py mix --video <master.mp4> --music <授权音乐.wav> --gain 0.12 --out <mixed.mp4>
python <skill>/scripts/media.py qc --video <delivery.mp4> --out <media-qc.json>
```

字幕输入为{segments:[{start:秒,end:秒,text:文本}]}，支持导入ASR输出或人工时间轴；脚本检查有限数值、顺序、重叠和越界，不自动做ASR。听校之后才能标记subtitle_aligned；烧录成功只证明技术步骤成功。没有听校时间轴时可预览镜头级初稿，但不能声称精准对齐。

封面可抽取指定帧并使用提供的字体添加标题；不要用未核验自动首帧代表封面质量。预览人物表情、字距、错字、平台裁切与标题真实性，再选定封面。混音输入必须有授权，不凭空称音乐已清权；单次loudnorm是技术归一化，不是专业听审。黑帧/长静音属于候选问题，环境静音和黑场可能有叙事意义，不能自动切掉。

结果统一交drama-release，包含实际视频路径、SRT、封面、时长和SHA256。检查声画、人物漂移、口型、台词、音乐遮挡、字幕可读性；当前没有自动视觉理解或唇形修正API。不要为了机械通过改变声音速度或循环旧画面。查看官方滤镜定义：https://ffmpeg.org/ffmpeg-filters.html 。
