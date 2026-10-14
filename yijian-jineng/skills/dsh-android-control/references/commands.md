# 手机命令
PY 为可用 Python，SCRIPT 为 scripts/phone.py 绝对路径，ROOT 为工作区，ADB 为 doctor 返回的 adb.exe。参数用独立数组传递。

~~~text
PY SCRIPT --root ROOT --adb ADB devices
PY SCRIPT --root ROOT --adb ADB --serial SERIAL info
PY SCRIPT --root ROOT --adb ADB --serial SERIAL apps
PY SCRIPT --root ROOT --adb ADB --serial SERIAL users
PY SCRIPT --root ROOT --adb ADB --serial SERIAL screenshot --output evidence/phone-001.png
PY SCRIPT --root ROOT --adb ADB --serial SERIAL open --package 已实测包名
PY SCRIPT --root ROOT --adb ADB --serial SERIAL open --package 已实测包名 --user 已确认整数系统用户
PY SCRIPT --root ROOT --adb ADB --serial SERIAL push --file outputs/card.png --task 任务ID
~~~
截图只能创建工作区内新文件，不覆盖。open 发起 launcher 启动，不验证身份；部分机型/系统用户可能不支持 monkey --user，失败后走已验证的真实入口，不盲目重试。
push 文件名以 SHA256 指纹和原扩展名组成，目标为 /sdcard/Download/selfmedia/任务ID/，只支持图片、MP4、MP3、字幕和文本。分身存储隔离、媒体库显示须再验证。
本脚本不点击手机界面、不判断账号、不登录、不提交。平台适配由 dsh-app-publishing 配合宿主真实界面工具执行。

## 可选 UI 桥接（依赖与真机流程未验收）
ui.py 共用参数：--root ROOT --adb ADB --serial SERIAL --task TASK --observed-account 实际看到的账号ID --ops-script 台账脚本绝对路径。
先 observe --output-base evidence/ui-001，读取 XML 与截图。selector 为实际节点的 JSON text 或 resourceId；只操作唯一匹配元素。
编辑：click --selector 精确选择器JSON --expect-hierarchy-sha256 上次观察哈希；set-text 另加 --text-file 工作区文字文件。
每次输入后重新 observe，旧哈希不复用。动态界面导致哈希变化时重新观察，不能放宽检测。
最终提交：仅在用户确认、approve/begin 后用 submit；同样要求当前界面哈希与唯一元素。submit 只表明尝试点击，需观察并核验作品后 complete，结果不明 uncertain。账号识别来自执行器对实际画面的核对，不能把目标值当作观察值。
