---
name: selfmedia-autopilot
description: 统一调度营销策划、爆款学习、混合账号内容生成、电脑制作、模拟器与USB发布任务；用户要求一键自媒体全流程时使用。
---

# 自媒体全流程总控
按当前项目工作目录执行。本包默认先生成并保存电脑成果，再交给明确的手机/模拟器/网页账号准备草稿和发布。
## 顺序
1. product-market-marketing：复用完整营销资料，确定产品、人群、已核实卖点、策略与内容边界。
2. viral-content-learning → content-framework-remix：收集有来源的样本，拆结构和逻辑，重做原创表达。
3. account-content-factory：按产品、分类、平台和账号设定计划；matrix.py 生成独立任务。可让当前宿主模型逐单生成，或在用户明确选定API端点后 generate.py --apply。
4. desktop-media-production：电脑生成图文、配音字幕视频，保存真实文件并QA。
5. dsh-account-matrix：登记真实账号、App实例和设备；platform-publish-router 入队。
6. 读取对应 publish-* 平台技能；USB走dsh-android-control，模拟器先memu-multi-instance，网页走browser-publish-control。
7. 用户确认精确草稿/账号/可见性后，approve→begin→一次attempt→提交→真实核验→complete。结果不明uncertain，先查作品。
## 调用
命令总表见 [执行手册](references/commands.md)。运行台账与UI工具使用项目 .venv-harness 或安装过本包依赖的实际Python。
一键模式自动处理已经提供且核验通过的输入、生成与准备步骤，不从软件安装授权推导发帖授权。批次审批须列出每个账号、素材指纹与预览；本任务按用户要求先开发后测试，不生成或发布真实内容。
读取manifest和进度后恢复，不重复生成已有产物或重复提交。状态、证据与必要人工步骤写入工作区，不在交付ZIP中打包登录数据。
