---
name: content-source-library
description: 导入公开或授权的文本、HTML与RSS，保存原始来源、采集时间和正文指纹，供爆款学习及事实追溯。
---

# 内容来源与证据库

metadata含source_url、access(public/authorized)、collected_at(带时区)。仅处理用户已有文件；网页采集由当前获授权工具完成并保存原文，不绕过登录/付费墙。HTML去除脚本样式，RSS拒绝实体声明；热度须另有真实指标证据。

使用实际Python执行 [脚本](scripts/sources.py)：

```text
python scripts/sources.py --root 工作区 --file 原始文件 --metadata 来源JSON
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
