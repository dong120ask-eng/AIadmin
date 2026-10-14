# 四种执行环境适配

记录本次具体产品名称、客户端版本、安装方式、文件能力、检索、媒体生成、浏览器与平台登录能力。下面区分官方格式依据、规则移植与未完成实测，不能宣称四端均已部署。

## Codex / ChatGPT Work
标准SKILL.md、agents/openai.yaml、references、assets与scripts已经按技能规范编写。在ChatGPT Work中通过技能仓库保存与Skills页面发现；在Codex CLI本机可安装到用户选择的.agents/skills目标目录并重新发现。使用suite_tools.py的install-codex先规划，显式--apply才复制；不覆盖已有不同技能。安装不是模型、视频或发布工具接入。

官方依据：https://developers.openai.com/codex/skills 。本轮检查日期2026-10-14。真实本机CLI执行和平台发布仍需单独实测。

## WorkBuddy
采用标准技能目录及依赖，依据官方“添加技能／上传技能”流程导入。本包脚本支持文件与Python不代表用户WorkBuddy环境已有Python、浏览器或媒体工具。单包导入时也要安装共享底座和相应依赖，检查客户端实际识别后才能标installed。

官方依据：https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market 与 https://intl.cloud.tencent.com/zh/document/product/1316/84503 。检查日期2026-10-14。未在用户客户端导入实测，不硬编码未经核实的安装路径或导入清单格式。

## 豆包
区分普通聊天、桌面助手、智能体配置和开发平台。当前已提供可复制的规则及交接提示词，用suite_tools.py compose --executor doubao生成。只有具体界面确认支持相应文件／工具后才映射；不能把普通聊天接收提示词称为原生Skill安装。没有文件或浏览器工具时交付文本，不承诺自动发布。豆包与火山引擎API是不同接入对象。

官方网站：https://www.doubao.com/ 。本轮未查到足以证明所有豆包产品支持任意标准技能包原生导入及浏览器发布的官方材料，状态为prompt_adapter_ready/native_install_unverified。

## 千问
区分千问APP／网页聊天、Qwen Agent、Qwen Code和其他阿里工具，不能因为使用同一模型就共用安装路径。提供suite_tools.py compose --executor qianwen规则移植；具体开发产品支持技能时再依据其官方文档映射。阿里云Skill目录说明不能直接证明千问APP支持同样本地目录或浏览器能力。

参考：https://help.aliyun.com/zh/skillsportal/understand-agent-skills 。本轮状态为prompt_adapter_ready/native_install_unverified，等待明确产品与版本后实测。

## 降级与交接
根据实际能力完成当前环节，交接项目、母稿版本、任务、事实、产物、审核与阻塞。缺少脚本执行器时输出同结构任务卡；缺少浏览器时交付发布包；缺少持续调度时只写待执行时间表。不能通过提示词获得实际未接通的权限、模型或外部服务。
