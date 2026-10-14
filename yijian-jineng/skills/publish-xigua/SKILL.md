---
name: publish-xigua
description: 为西瓜视频的自有账号准备内容和草稿，按当前界面核验身份、字段、发布确认与作品结果。
---

# 西瓜视频发布
先读相邻platform-publish-router/SKILL.md和dsh-account-matrix/SKILL.md，确定真实任务、账号实例、设备与内容类型。

需准备：视频、封面、标题、简介、版权信息与账号权限。
核验方式：创作后台中的作品ID与状态。
官方创作入口参考：https://studio.ixigua.com/。入口与权限按当前页面核对，未在本轮登录或测试。

手机/逍遥实例走dsh-android-control，网页走browser-publish-control或宿主真实浏览器工具；包名必须设备apps确认，不能由候选名推断已安装。每次切换实例重新观察账号，selector来自当前XML/DOM，不硬编码未经实测坐标。

先保存在电脑的正文和媒体，通过QA才claim并上传。保存草稿与实际预览，再让用户确认精确账号、素材、正文、可见性；submit前一次attempt。提交后核验作品ID和实际审核状态，未知就uncertain，不重复点击。

本文件是可执行控制器的西瓜视频操作约定；具体账号/版本界面在下一阶段测试中校准。没有该体裁入口或权限就保存阻塞原因，不虚报上传和发布成功。
