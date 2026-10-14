---
name: model-provider-runtime
description: 调用明确选择的兼容模型API，记录每日令牌预留与调用上限，对429有限退避，连接结果不明时停止。
---

# 模型端点与预算执行

profile需真实model、api_key_env、base_url及daily_call_limit/daily_token_budget/max_output_tokens。默认仅计划；apply才把指定资料送选定端点。预算是保守预留，不是实际账单；只重试429，超时不自动重复计费调用。不要记录凭据或原错误响应。

使用实际Python执行 [脚本](scripts/client.py)：

```text
python scripts/client.py --root 工作区 --profiles 提供商JSON --provider 名称 --messages 消息JSON --output 结果JSON [--apply]
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
