# USB安卓手机接入

本会话运行在云端。手机插进用户Windows电脑，不会自动出现在云端设备列表。需要用户电脑上的本机执行器；不能把本机ADB或Appium控制端口开放到公网。

## 首次连接

1. 确认手机是安卓。当前ADB/Appium方案不适用于iPhone；iPhone需另外设计接入，不能沿用本说明。
2. 在安卓手机上按厂商说明开启开发者选项和USB调试。用支持数据传输的数据线连接电脑，由用户在手机官方提示中决定是否允许这台可信电脑调试。
3. 从Android官方来源安装Platform Tools：https://developer.android.com/tools/releases/platform-tools 。在电脑本机终端运行：

```powershell
python scripts/android-usb-check.py
# ADB不在PATH时：
python scripts/android-usb-check.py --adb "C:\YOUR_PLATFORM_TOOLS\adb.exe"
```

4. ready为true且指定设备状态为device，才表示本机ADB已连通。unauthorized须由用户在手机处理调试授权，offline须检查连接。多个设备必须明确指定目标UDID。请只提供检测结果和手机型号，不提供密码、验证码或令牌。

脚本只执行adb devices -l，不点击手机，不登录，不自动切换账号。此会话实测结果仍为没有ADB／没有设备，不能宣称手机已连接。

## 从连接到自动化

根据ANDROID-SETUP.md配置本机Appium，route填android_device，使用实际device_udid和实际app_package。先打开App，使用DISPATCH.md的受设备锁保护的检查任务采集页面结构。之后才能为该App版本开发实际账号身份核查、编辑器操作、草稿保存和发布执行器。

让用户电脑上有本机执行能力的Codex CLI或WorkBuddy运行这些命令。当前云端会话没有到用户Windows的执行连接，不能远程替它运行；本机脚本的输出和经脱敏的结构信息可作为开发输入。

## 多账号方式

优先核查App官方账号切换，或手机厂商自带的应用分身。是否支持、可开多少实例、对应包名和账号权限逐App确认，不保证所有媒体都支持双开。不要安装未经核实的改版App或使用设备伪装。

每个账号绑定实际平台唯一ID和目标应用实例；切换后从当前页面复核实际账号身份，匹配后才编辑或发布。同一台手机串行执行多个账号任务；使用分身也不能让同一物理设备同时被两个工作进程操作。工作资料／应用分身的具体定位尚未实现，要先检查手机和目标App。

当前队列设备锁已开发，平台账号切换、应用分身定位和真实发布执行器仍待开发与实测。账号切换完成不等于新账号已获得创作权限；结果不明先查作品记录。
