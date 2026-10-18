# GitHub安卓多手机项目核查与整合

2026-10-14。用户要求查找手机操作技能并合并现有企业内容工作流。本轮完成项目文档及许可证核查、新增安卓多手机操作技能、本机可选SDK页面检查适配器；尚未在用户真机上验证。

| 项目 | 核查的许可 | 用途 | 本轮整合状态 |
|---|---|---|---|
| droidrun/mobile-harness | MIT，版权Droidrun 2026 | AI手机控制的可移植技能；本地ADB和其他后端 | 适配观察—操作—核验及本地后端选择；新增mobilerun_core本地页面检查接口，依赖未安装 |
| openatx/uiautomator2 | MIT，版权openatx 2017 | 明确设备序列号的UI控件操作与结构读取 | 新增显式serial连接和dump_hierarchy检查接口，依赖未安装 |
| Genymobile/scrcpy | Apache-2.0 | USB投屏、键鼠控制、人工接管 | 工具候选与接管说明，未复制、未安装 |
| zai-org/Open-AutoGLM | Apache-2.0 | ADB＋视觉模型的手机智能体 | 备选方案，未接入模型、未发送手机屏幕或调用付费接口 |

官方项目：
- https://github.com/droidrun/mobile-harness
- https://github.com/openatx/uiautomator2
- https://github.com/Genymobile/scrcpy
- https://github.com/zai-org/Open-AutoGLM

Mobile Harness是技能资料，不包含自身执行运行时。其正常API为mobilerun_core.Mobilerun。本轮读取SKILL.md、AGENTS.md、Android GUIDE、README.md和LICENSE，参考最小资料加载、本地后端、观察—操作—核验流程。保留Droidrun MIT许可在新增安卓技能的references/upstream-mobile-harness-license.md；没有整体复制上游工程、App卡或凭证保存逻辑。

## 本机执行方式

现有Appium仍是默认检查后端。在用户电脑隔离环境按官方文档安装所选依赖并记录版本；程序不会替用户自动下载安装或升级：

```powershell
# 选择uiautomator2时，对应PyPI包：uiautomator2
# 选择Mobile Harness本地后端时，对应PyPI包：mobilerun-core[local]
python -m workbench dispatch-run-inspection --backend appium
python -m workbench dispatch-run-inspection --backend uiautomator2
python -m workbench dispatch-run-inspection --backend mobilerun
```

仅运行实际选择的那一条。SDK在显式选择时才加载，缺少依赖在领取队列任务前报安装问题。uiautomator2明确connect(device_udid)，并验证返回serial；Mobilerun明确connect(device_udid, backend="local-android-adb")，没有选择cloud。每次连接及读取前用本机ADB检查目标仍在线，不能自动切换到其他在线设备。

uiautomator2页面保存为其原生UI XML；Mobilerun结构保存为标记清楚的mobilerun-ui-json XML容器，不声称原生UIAutomator树。关闭本地SDK对象不等于停止设备侧服务；异常恢复仍要确认旧进程停止。依赖可能启动或安装其官方设备测试组件，按用户电脑和手机实际权限配置。

这两条可选接口当前只检查页面，不点击、不填内容、不切号、不提交作品。Mobile Harness上游具有动作能力，但本应用尚未把其所有动作接入自动发布。账号切换、应用分身与目标平台专用执行器需真实设备和页面再开发。

## 多台手机与多账号

每台手机单独绑定UDID；同一物理设备受队列排他锁保护，不能镜像广播操作到所有手机。手机厂商分身、工作资料和ADB别名需核实，不能以不同账号名或应用实例名绕开同一手机锁。切换账号后再次读取当前实际平台账号唯一ID。

内容项目总发布工作流新增安卓技能路由；共享清单增加android-device-operator，规则套件由42增至43个技能。保存及安装结果以最终核对为准；技能安装不等于依赖安装、用户USB手机连接或真实账号发布成功。

云端本会话没有用户Windows或USB设备连接。USB-START.md提供本机检测步骤；检测到本机在线后，再安排单手机只读检查、单账号草稿、真实发布和多手机任务验收。

## 验证

72个Python测试通过。新增SDK接口测试使用受控模拟模块和本机ADB测试响应，未运行第三方SDK或真实手机。媒体页面7项JSDOM检查通过；其余页面本轮未改动。手机检测脚本实际返回ADB不可用，不能称手机已接入。
