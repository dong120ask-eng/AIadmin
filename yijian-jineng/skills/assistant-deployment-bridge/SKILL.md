---
name: assistant-deployment-bridge
description: 向Harness、WorkBuddy与Codex部署真实技能目录，为普通豆包和千问客户端导出资料与调用指令。
---

# 四助手技能部署桥

通过deployment-latest.json定位本地工具包，或显式指定工作区内bundle。执行宿主使用正规技能目录并备份；普通聊天客户端仅导出知识包，不宣称获得本机/手机操作权。密钥、模型/API权限另行配置。

使用实际Python执行 [脚本](scripts/bridge.py)：

```text
python scripts/bridge.py --root 工作区 --host harness/workbuddy/codex/doubao/qwen [--bundle 完整包] [--output 导出目录] [--apply]
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
