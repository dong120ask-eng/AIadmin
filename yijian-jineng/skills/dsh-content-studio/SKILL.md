---
name: dsh-content-studio
description: 在本地制作中文图文、平台稿件和短视频素材；复用已有渲染器并产出可交接的质检报告，适用于手机发布前的内容生产。
---

# 内容制作
当前完整套件优先用相邻desktop-media-production，其渲染器、视频制作器和检查器已随技能打包；原本机工具作为可选来源。
先确定输入资料、受众、目标平台、账号和内容体裁。写稿与规格建议由模型完成；当前热点、规则与引用依据需检索。先做一条样稿，再扩大产量。存入工作区 outputs/，不覆盖旧成果。

## 中文卡片
用相邻 dsh-selfmedia-hub/scripts/doctor.py 找本机 cn-card-render 的脚本和带 PIL 的 Python。已存在的 cn-card-render/SKILL.md 是规格参考，输出路径遵守本项目。
用本技能 scripts/render.py --root 工作目录 --spec 规格JSON --python 已验证Python --renderer 已存在渲染器。
规格需非空 cards，output_dir 为工作区内的新目录；支持的 layout/size/theme 从实际渲染器检查，不虚构参数。产出后打开图片，核对文字裁切、中文字体、尺寸、事实和来源。脚本存在不代表样张已通过。

## 文章
输出 title/body/tags、配图和资料来源；分别适配公众号、小红书、头条号等，当前平台规格从官方来源或实际后台核对。涉及产品用核准资料，不编造销量、疗效或资质。正文是实际文件，不仅聊天文本。

用 [文章排版](scripts/formatting.py) --root ROOT --title 标题 --text 正文MD --output 新HTML 导出保守Markdown子集的内联样式HTML，正文原始HTML被转义，非HTTPS链接不变成可执行链接。排版后仍需预览；图片上传和公众号后台粘贴按实际发布流程处理，不把本地HTML说成已发布。

## 视频
复用本机 make_video.py、verify_output.py 和既有 cn-video-auto 流程，运行前核对 Python 模块、ffmpeg/ffprobe 路径。edge-tts 需要网络，不宣称完全离线。旧脚本依赖/素材不足就记录真实缺口。
产出视频、封面、字幕、制作单和质检；检查画幅、音轨、字幕、时长与平台实际要求。缺少运行依赖时不得把脚本方案说成已出片。

完成后以实际正文/媒体文件创建任务，质检报告存 evidence/ 再记录 qa。未通过质量或事实审核的内容不进入草稿。
