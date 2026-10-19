# 经授权组件复用（可选目录）

此目录复用现有代码，不替换 AIadmin 工作台、队列、技能清单、安装入口或发行包配置。营销素材技能未安装至任何客户端，未接入自动执行路由。

`install/` 六个脚本和 `tests/test-install.ps1` 原样来自 Aladmin；公司原创声明、逐文件 SPDX MIT 与原 LICENSE 一并保留。`skills/marketing-material-generator/` 四个源文件原样保留上游 MIT 许可。精确来源树和 Git blob 哈希见 PROVENANCE.json。仅这一个技能进入本目录，另外18项不包含在内。

离线检查：`python reuse/aladmin/verify.py`。Windows 行为检查：`powershell -NoProfile -File reuse/aladmin/tests/test-install.ps1` 或 `pwsh -NoProfile -File reuse/aladmin/tests/test-install.ps1`。测试只使用临时目录中的示例，不读取用户账号或修改真实客户端。

可选安装预览（先指定目标）：

```powershell
powershell -NoProfile -File reuse/aladmin/install/install-codex.ps1 -TargetDir C:\chosen-project\.agents\skills -WhatIf
powershell -NoProfile -File reuse/aladmin/install/install-workbuddy.ps1 -TargetDir C:\chosen-project\.codebuddy\skills -WhatIf
```

确认预览后移除 `-WhatIf` 才复制文件；默认保留已有技能，`-Update` 才替换并保留备份。不要与旧 Python 安装器同时运行：两者锁协议不同。此安装器按技能恢复，不是跨平台全局事务。SHA256校验用于检查暂存复制一致性，不是上游真实性证明；真实性由固定来源和 PROVENANCE 哈希记录提供。

运行依赖：飞书多维表格副本、lark-cli 授权、图像生成工具、image_to_video 映射。上游模板链接的可访问性、模板复制权和账号权限须分别确认；源码 MIT 不授予在线服务权限。固定模型名、2048方图与8秒视频是上游默认值，须在实际服务与目标平台规格确认后使用。五环节流程只是一套技能指令，未包含通用执行器、费用控制、断点状态或真实成品生成验收。文件安装成功不等于客户端加载成功。
