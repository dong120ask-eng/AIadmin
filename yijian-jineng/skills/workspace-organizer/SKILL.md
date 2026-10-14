---
name: workspace-organizer
description: 整理本项目旧版本、资料、交付和运行成果，使用可恢复归档清单而非删除，保持技能相对资源路径完整。
---

# 干净目录与交付
scripts/organize.py只移动明确指定顶层项；先plan验证解析后的来源和目标均位于工作区，目标不冲突，再apply并保存全文件指纹清单。无删除命令。
保护运行目录 .agents/.codebuddy/.dsh/.venv-harness/state/outputs/evidence/work/自媒体技能套件/delivery。
将旧源码与对应依赖资料按原相对关系一起归档，保留原始名字；把新套件做唯一源码入口，交付只保留一个当前ZIP。旧ZIP与历史说明放archive，不混入当前交付。
先确认调用方不依赖要移动的路径；已部署技能资源独立且不依赖旧源码后再归档。根README改为当前索引，旧README也保留。
用tools/package.py生成清单并核对ZIP；排除虚拟环境、凭据、登录会话、运行数据库、真实账号证据和缓存，不能把私有素材打入通用技能包。
