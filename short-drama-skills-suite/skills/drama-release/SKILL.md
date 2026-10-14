---
name: drama-release
description: 将短剧成片转换为指定平台发布资料和质量缺口清单，通过授权后台协助提交，并保存作品回执与重复发布记录。
---

# 短剧平台分发适配

读取同级global-short-drama/references/platforms.md，平台规格以当前官方资料和实际后台为准。红果整剧供片、抖音短视频、抖音短剧内容库及海外专业应用是不同业务，不能互相替代。本技能的脚本实现发布准备与回执记录，没有内置红果或其他平台上传SDK；通过宿主实际可用的授权浏览器/官方连接器完成上传。没有该能力就保留待接入，不假装点击成功。

```text
python <skill>/scripts/release.py prepare --manifest <run>/publish-manifest.json --platform hongguo --account <账号标识> --out <release-directory>
python <skill>/scripts/release.py record --queue <release-directory>/queue.json --receipt <backend-receipt.json> --out <publish-log.jsonl>
```

prepare计算真实文件SHA256、导出标题/简介/视频/字幕路径，列出声画/字幕审阅、版权、国内编号等缺口。queue里的ready只是资料检查，不是账号已授权或平台必然受理；封面、演职员、主体与合同等材料还需对照后台补齐。所有实际上传、提交审核、公开发布之前展示平台/账号/集/语言/文件哈希/标题/可见性/材料并按用户约定确认。

必须剧本审稿通过且媒体与原QC一致。实际听校、观看和字幕核对完成后，才运行下面命令，将操作人的审阅声明绑定最终视频与字幕的SHA256。脚本不能自行看听，不得为消除缺项替用户作出声明。换视频、改字幕必须刷新清单并重新审阅；重新package会生成新清单，需再次绑定声明。

```text
python <skill>/scripts/release.py attest --manifest <publish-manifest.json> --reviewer <实际审阅人> --review-completed --out <reviewed-manifest.json>
python <skill>/scripts/release.py prepare --manifest <reviewed-manifest.json> --platform hongguo --account <账号> --out <release-directory>
```

现场核对平台回执，再用record保存状态。backend-receipt.json含release_id、status、remote_id、url、evidence（后台观察说明）。published必须有作品ID或HTTPS链接及证据，不能从本地文件猜测；submitted/in_review不能升级成published。脚本去重同一release_id的已发布记录，网络结果不确定用unknown并先查后台，不盲目重发。只是记录用户提供JSON不等于本技能自动验证了远端。

扩展平台时先发现合法后台/接口与权限、记录规格来源和核验日期，再生成平台专用资料，不添加虚构API。对外发布与上传所需登录/验证码/商务手续交用户完成；一次平台失败不修改其他平台结果。
