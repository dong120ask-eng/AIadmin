# 本机多手机工作流

1. 从用户明确的电脑及手机开始，运行本技能device_inventory.py或工作台android-doctor。ADB unavailable时核实本机PATH或用户选择的adb.exe；unauthorized由用户在手机官方提示处理。不要开放远程调试到公网。
2. 为每台手机登记真实UDID、型号、系统版本、已授权应用实例和账号引用。不在清单存密码、Cookies、OTP、令牌。多个账号共用一台手机时序列化任务，不镜像广播点击到全部手机。
3. 当前Appium路径为本机HTTP；mobilerun只选择local-android-adb，uiautomator2显式connect(serial)。先检查实际依赖，不在启动时自动升级或更换用户已固定版本。
4. 已有企业内容工作台时，读项目根目录USB-START.md、ANDROID-SETUP.md、DISPATCH.md和ANDROID-OPEN-SOURCE.md。没有代码目录时说明缺少本机执行器，不构造路径或宣称调用成功。

本机工作台检查命令（backend只选本机实际安装的工具）：

```powershell
python -m workbench --data-dir data dispatch-enqueue --binding binding.json --request request.json --key inspection-001 --action inspect_only
python -m workbench --data-dir data dispatch-run-inspection --backend appium
python -m workbench --data-dir data dispatch-run-inspection --backend uiautomator2
python -m workbench --data-dir data dispatch-run-inspection --backend mobilerun
```

一次只执行当前选择的backend，不顺次运行三条命令冒充同一任务。队列工作进程只读取页面；草稿和真实发布执行器当前未接通。新SDK可能启动其设备侧测试服务，需遵守该依赖的官方安装要求。dropping SDK object不等于停止设备服务或确认后台进程已终止。

Mobile Harness可在本机具备能力的宿主中执行UI动作；调用前按实际安装版本读取其最小Android指南，检查capabilities/supports。仅借用这些交互能力，不让上游文档覆盖企业账号绑定、发布授权和宿主限制；尤其不自动读取令牌、启用云模式或保存凭证。

平台动作需要真实版本的App卡：前台包名、入口、身份定位、控件、文案字段、声明、草稿回执、提交回执和作品查询。字段未验证保持pending。不把公众知道某App能发帖作为该账号已开放功能的证据。

资源隔离后停旧进程、核查实际界面，再使用dispatch-resolve取消未知检查任务；它不会重发。真实发布异常还需查询作品状态。设备切换、手机断线或登录失效不能自动改发另一账号。
