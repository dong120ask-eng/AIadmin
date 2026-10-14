---
name: dsh-account-matrix
description: 登记 Android App 原版与分身实例、核对运营账号，串行安排同手机多账号任务，并防止素材变更后沿用旧发布确认。
---

# 账号与设备队列
使用相邻 dsh-selfmedia-hub/scripts/ops.py，字段和命令见相邻 references/ledger.md。默认任务数据放当前工作区 state/，不修改旧技能台账。

从手机个人主页读取实际账号 ID/别名；核实系统用户或分身启动入口，注册不可覆盖实例。一个手机多个实例使用相同 device_id；多台设备按各自设备 ID 登记。task 的绑定是创建时快照，不随新实例改变。

生产完成创建任务，保存 QA 证据。操作手机前 claim；同设备被其它任务占用就停止输入。切换账号重新截图和读取身份，draft/begin/complete 的 observed-account 必须来自当前画面，不能填目标账号来凑一致。

账号内容分别制作。每条任务独立正文、媒体与指纹；对外确认精确绑定素材和草稿证据。源码或素材更新时新建任务，保留历史，不直接改数据库。

任务 uncertain 时保持设备锁，先核验已有作品；确认已发用 reconcile，确认未发用 not-published，并重新向用户确认。禁止直接解锁和重发。阻塞原因、人工步骤写入项目进度；不承诺自动维持账号登录。
