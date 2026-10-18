# 安卓执行环境：首选雷电模拟器9

2026-10-14。本轮为Windows选择雷电模拟器9作为首个接入目标。选择依据是官方提供ADB连接和多开设备识别说明，并非已实测所有媒体App兼容。

官方说明：https://help.ldmnq.com/docs/LD9adbserver 。下载仅从雷电官方站点完成：https://www.ldmnq.com/ 。不需要为了本工作流开启Root、安装改版App或伪装设备。

电脑上的AI负责调度，媒体App运行在模拟器中。先安装一个实例，成功后再扩展多开。Appium UiAutomator2作为设备执行接口，官方支持模拟器与真机：https://github.com/appium/appium-uiautomator2-driver 。遇到应用不兼容模拟器时改用安卓真机；不能承诺所有应用可在模拟器中稳定发布。

## 电脑准备

1. 在Windows电脑安装雷电9，按官方文档设置ADB连接。只使用本机调试连接，不开放网络上的远程ADB。
2. 安装与当前Appium兼容的Node.js、JDK和Android SDK Platform Tools；按当前官方驱动说明检查版本：https://appium.io/docs/en/latest/quickstart/ 。运行`appium driver install uiautomator2`安装官方驱动，不使用放宽安全限制的启动参数。
3. 将ADB所在目录加入本机PATH，在终端执行`adb devices -l`。从实际输出选择设备UDID，不能依靠模拟器窗口顺序猜设备。
4. 本机启动Appium：`appium --address 127.0.0.1 --port 4723`。不要把控制端口绑定到外网。
5. 在模拟器内从官方来源安装目标媒体App，在官方界面完成登录、验证码或实名验证；确认用户已接受必要协议。不要把凭证填进任务JSON。

以上是用户电脑操作步骤。本会话无法访问用户电脑，未代为安装模拟器或登录App。

## 读取真实页面，为平台执行器建立选择器

复制examples/publish-binding.json，替换项目、账号唯一ID和渠道ID；route改为android_emulator；填入实际device_udid及实际app_package。包名从设备上当前已安装应用核查，不填写示例包名。

```json
{
  "tenant_id": "internal",
  "project_id": "your-project",
  "account_id": "your-account-ref",
  "account_unique_id": "REAL_PLATFORM_ACCOUNT_ID",
  "channel_id": "taobao-guanghe",
  "route": "android_emulator",
  "device_udid": "REAL_ADB_UDID",
  "app_package": "REAL_INSTALLED_PACKAGE"
}
```

先把目标App打开到待检查页面，然后运行：

```powershell
python -m workbench android-doctor
python -m workbench android-inspect --binding binding.json --output device-inspections/editor.xml
```

android-inspect连接本机Appium，指定唯一设备，要求Appium回传同一UDID。保持noReset、禁用fullReset和autoLaunch；读取当前页面XML后关闭会话。不点击控件、不填写登录资料、不上传作品、不提交发布，不代表账号身份已经核验。Appium驱动可能为会话安装其官方测试组件，须由本机操作者按驱动官方说明配置。

页面XML可能含账号及私人资料，只保存在本机，不上传GitHub或聊天。device-inspections目录已加入忽略规则。不要改用网络服务来绕过本机连接限制。此命令没有持久化设备排他锁，首次只串行运行一个检查；不能在同一设备上并发执行生产任务。

## 自动化技能验收

媒体登记、官方发布证据、执行器开发、草稿实测和真实发布实测分别标记。每个平台确认形式、入口、账号身份、权限和当前版本，再开发上传、填写、预览、草稿保存及提交动作。设备身份匹配不等于平台账号身份匹配。

首次单账号单内容测试通过后再扩展到多账号。自动发布依赖明确范围的授权、真实审核版本、设备锁和发布结果查询。结果不明时先核查作品记录，不能重复点击发布。某个App的执行器通过不能推断其他App已自动化。

四端均通过统一任务和结果JSON交接。优先用一个有本机执行权限的客户端跑通，再增加WorkBuddy、豆包和千问适配；模型或聊天软件名称不能证明它具备浏览器与设备工具。

## 本轮实际结果

安卓检查协议接口已开发；会话参数、唯一设备身份、响应解析、错误处理、本机限定和重定向拒绝完成本地协议测试。总计49个Python测试通过。协议测试使用本机测试服务器，不是雷电、Appium驱动或真实App实测。当前没有实际连接安卓设备，平台专用登录和发布执行器尚未完成。

## 多账号检查队列

新增受设备互斥保护的检查工作进程。直接android-inspect命令仍没有队列锁；多账号检查应使用[DISPATCH.md](DISPATCH.md)中的dispatch-run-inspection，且不要与直接检查命令同时运行。
