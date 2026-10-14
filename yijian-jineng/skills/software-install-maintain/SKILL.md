---
name: software-install-maintain
description: 核对并安装自媒体所需电脑依赖、官方软件与指定Android组件，保留版本和安装记录，不重复安装。
---

# 电脑与手机软件安装
scripts/install.py支持已知winget包、项目requirements与指纹已核验的官方EXE/MSI；默认计划，apply仅在明确安装授权范围执行。
优先复用已有adb/scrcpy/ffmpeg/Python。用官方软件站或已核对清单获取安装包；安装前核对签名、SHA256、版本、许可与目标路径。逍遥官方安装器的参数以本机实际版本为准，不伪造静默参数。
Python装在项目独立环境；requirements-base/video/browser分开，记录pip freeze和检查结果。不要全局升级全部软件，不能把API SDK安装叫作API账号已接通。
手机只对明确序列号操作；已有App不卸载、不降级。官方APK确认来源和摘要后再adb -s SERIAL install；uiautomator2使用已安装包随附组件。登录和系统安全/UAC交给用户处理，不绕过验证。
用户明确要求安装必要软件时，按当前授权范围检查并安装，不重复询问已经确认的同一操作。新用户或新环境不得把开发会话中的安装许可当作现有许可。发布授权仍另行取得，真实安装/运行状态仅按实际记录填写。
