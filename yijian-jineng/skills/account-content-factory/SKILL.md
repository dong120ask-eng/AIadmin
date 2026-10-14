---
name: account-content-factory
description: 按分类、产品、平台和账号人设混合规划独立内容任务，生成账号专属稿件与制作规格，用于一键批量内容工厂。
---

# 分类混合账号内容工厂
scripts/matrix.py --root ROOT --spec config/campaign.json --output work/plan.json。输入字段见 [混合分配](references/matrix.md)。
读取真实产品brief及营销结论，为账号匹配 product_ids、categories、persona、format、max_items。每个选题产生独立job、输出目录和源资料指纹。
可由当前宿主模型写入 content.json/body.md/cards.json/video.json；采用scripts/generate.py时指定providers文件与provider，先计划，用户选定端点后apply。不会自动使用豆包/千问聊天账户，API模型名和密钥环境变量必须真实配置。
正文、封面、视频口播、来源与待核对项分别保存。已有输出不覆盖，资料改变重建计划和任务。生成后事实/合规/媒体QA，随后入队；生成成功不是发布成功。
