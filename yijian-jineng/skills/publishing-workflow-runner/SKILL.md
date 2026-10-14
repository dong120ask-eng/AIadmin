---
name: publishing-workflow-runner
description: 按照已校准的具体账号页面执行真实文字、素材和草稿步骤；绑定台账与实时身份，最终提交只执行一次。
---

# Android网页草稿执行

默认只输出计划。observe可使用未校准的配置。prepare需质检reviewed及claim设备；每步重新核对账号、唯一控件和截图，最后核验可见性并存草稿。submit需现有用户确认及begin后的publishing，先登记attempt再点击一次；异常记uncertain，不自动重复。Android图片选择使用真实校准文件选择器，网页files使用当前任务文件。

使用实际Python执行 [脚本](scripts/engine.py)：

```text
python scripts/engine.py observe/prepare/submit --root 工作区 --task 任务ID --profile 校准配置JSON [--apply]
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
