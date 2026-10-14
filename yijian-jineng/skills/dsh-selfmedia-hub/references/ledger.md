# 台账操作
以下命令把 SCRIPT 替换成当前技能目录/scripts/ops.py 的绝对路径，PY 替换成 doctor 验证过的 Python。ROOT 为实际工作目录。脚本使用 Python 标准库，无需 pip 安装。通过 subprocess 参数数组或 PowerShell 参数传递调用，避免拼接 shell 字符串。

## 命令
~~~text
PY SCRIPT --root ROOT register --file instance.json
PY SCRIPT --root ROOT create --instance phone-xhs-a --title 标题 --text outputs/text.md --media outputs/card.png --visibility 公开
PY SCRIPT --root ROOT show --task TASK
PY SCRIPT --root ROOT list
PY SCRIPT --root ROOT qa --task TASK --evidence evidence/qa.json
PY SCRIPT --root ROOT claim --task TASK
PY SCRIPT --root ROOT draft --task TASK --observed-account ACCOUNT_ID --evidence evidence/draft.png
PY SCRIPT --root ROOT release --task TASK
PY SCRIPT --root ROOT approve --task TASK --approval evidence/approval.json
PY SCRIPT --root ROOT claim --task TASK
PY SCRIPT --root ROOT begin --task TASK --observed-account ACCOUNT_ID --evidence evidence/pre-submit.png
PY SCRIPT --root ROOT attempt --task TASK --observed-account ACCOUNT_ID
PY SCRIPT --root ROOT complete --task TASK --observed-account ACCOUNT_ID --evidence evidence/result.png --result 真实作品链接或ID
PY SCRIPT --root ROOT uncertain --task TASK --evidence evidence/uncertain.png
PY SCRIPT --root ROOT reconcile --task TASK --observed-account ACCOUNT_ID --evidence evidence/result.png --result 真实作品链接或ID
PY SCRIPT --root ROOT not-published --task TASK --observed-account ACCOUNT_ID --evidence evidence/confirmed-not-published.png
~~~

所有素材和证据必须在 ROOT 内，证据非空。qa、draft 等是对实际完成步骤的记录，不代替制作、质检或界面操作。begin 只作提交前闸门，不执行平台发布。complete/reconcile 的成功必须由执行器先看作品列表或真实回执，CLI 不验证截图中内容或作品链接真实性。
attempt 是提交前的一次性记录，UI 桥接在点击前自动调用；一旦记录不得再次尝试。进程在记录后、点击前中断时也先核验，不能猜测重试。其它宿主执行最终按钮前同样记录 attempt。

## 实例 JSON
必填 id（英文小写连字符）、device_id、platform、package_name、account_id、account_alias、launch_mode。
launch_mode 为 primary / android-user / manual-clone；android-user 另填整数 android_user_id；manual-clone 另填 clone_entry。真实值从设备和个人主页读取，不从示例猜测。登记不可覆盖已有 ID，身份改变时新增实例，保留旧任务。

## 确认 JSON
在用户看到真实草稿并明确确认本任务发布后写入：
~~~json
{
  "task_id": "从show读取",
  "fingerprint": "从show读取",
  "draft_sha256": "从show的draft读取",
  "approved_by": "实际确认者",
  "consent": true
}
~~~
此文件记录人工确认，不是密码学签名；脚本不能证明确认者身份，执行器必须依据实际用户回复生成。修改正文、媒体、标题、可见性或实例需新建任务并再次展示预览。

同一手机多个实例共用 device_id，设备锁因此串行。claim 失败停止界面操作。publishing/uncertain 不能 release；成功核验后自动释放。确认未发布的 not-published 会取消旧审批，返回 draft 并释放锁。任何解锁前须实际核验，不靠人工修改数据库跳过。
