# GitHub工具核查与整合

检查日期2026-10-14。以下为官方项目源码及文档核查，尚无用户真机验收。

- droidrun/mobile-harness：MIT。提供可移植手机操作技能，Python入口mobilerun_core.Mobilerun；本地Android可明确选择local-android-adb。按其最小Android指南检查能力、先观察后操作再核验；不是内置执行运行时。来源：https://github.com/droidrun/mobile-harness 。本次读取SKILL.md、README.md、AGENTS.md、platforms/android/GUIDE.md和LICENSE。自媒体账号／发布约束使用本企业工作流；本包没有导入其凭证保存或云端默认设置。
- openatx/uiautomator2：MIT。官方README明确使用设备序列号连接、获取dump_hierarchy及元素操作。适合确定性App控件动作。来源：https://github.com/openatx/uiautomator2 。本机检查适配器已编写，但依赖未安装、手机未连接；不能宣称真机运行成功。
- Genymobile/scrcpy：Apache-2.0。USB或网络投屏和键鼠控制，适合人工接管和可视核验，不自行完成内容生成／账号授权／发布核查。来源：https://github.com/Genymobile/scrcpy 。本次核查LICENSE与项目说明，未复制程序或安装。
- zai-org/Open-AutoGLM：Apache-2.0。ADB结合视觉模型的手机智能体候选，需要模型端点、运行环境和成本核查。来源：https://github.com/zai-org/Open-AutoGLM 。本次核查项目说明和LICENSE，未接入，不默认发送私人屏幕到模型服务。
- appium/appium-uiautomator2-driver：既有本机检查路径。官方支持安卓模拟器及真机；连接成功不等于某媒体App兼容。来源：https://github.com/appium/appium-uiautomator2-driver 。继续沿用现有显式设备身份及排他队列。

本包为企业工作流适配，参考Mobile Harness的本地后端、最小资料加载与观察核验流程。保留Droidrun MIT许可于upstream-mobile-harness-license.md。未打包第三方SDK源码或二进制；其运行时单独从官方项目／标准包仓库安装并记录实际版本，保留各自许可。不要声称四个项目已经整体合并并跑通。
