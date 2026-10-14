---
name: asset-library
description: 用内容指纹登记图片视频来源与权利，记录账号使用，检查库内素材变化和跨账号复用。
---

# 素材权利与去重库

权利JSON的rights仅接受owned/licensed/public-domain，source填真实出处。use --sha 指纹 --account 账号 --task 任务记录用途；跨账号复用必须显式--allow-reuse，且先核对素材许可。

使用实际Python执行 [脚本](scripts/assets.py)：

```text
python scripts/assets.py --root 工作区 ingest --file 素材 --metadata 权利JSON
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
