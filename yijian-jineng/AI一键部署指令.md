# 复制下面的指令给 AI

请部署这个自媒体技能套件。先定位本文件所在目录，不要假定 U 盘盘符或 D 盘路径。读取 docs/剩余技能补齐与交付清单.md 和 docs/技能检查与优化报告.md，确认 Windows 10/11 x64、目标项目目录和可用空间。默认项目目录为当前用户目录下 SelfMediaWorkspace，用户指定路径优先。

执行 tools/setup.ps1 -TargetRoot "目标项目绝对路径" -Plan，核对清单与指纹。用户已要求部署时，继续执行同一命令去掉 -Plan。一次部署到 .dsh/skills、.codebuddy/skills、.agents/skills 三个目录；保留原有其他技能，记录每个宿主的备份位置。不要删除原数据。失败时停止，说明已经完成哪些宿主、哪个宿主失败，按日志恢复或重跑。部署不等于已完成真实平台验收。

从 deployment-latest.json 读取本地工具包和 Python 的实际路径；之后运行本地副本，U 盘可以拔出。用该 Python 执行 tools/check_release.py。让用户在 DeepSeek Harness、WorkBuddy 或 Codex 中打开目标项目，再检查技能是否被宿主识别。

豆包和千问的普通聊天客户端不能因为复制这些文件就获得电脑执行权限：有本地执行能力的宿主读取 skills/selfmedia-autopilot/SKILL.md；普通客户端上传需要的技能指令和资料；API 模式按 config/providers.example.json 配置真实模型和环境变量密钥。不要把密钥写进指令或提交 GitHub，不要假设登录客户端就是 API 授权。

软件安装按 software-install-maintain 技能检查缺项；本包已经携带 Python 3.13.16 x64 和 Python 依赖，部署本身无需联网。包内不包含 DeepSeek Harness、WorkBuddy、逍遥、FFmpeg、scrcpy 和浏览器安装程序。缺少的程序需按官方安装流程联网获取；离线电脑应事先放入官方安装包并核验。手机必须明确设备序列号并接受 USB 调试授权。多开实例与真实账号逐个登记，不假设所有 App 都支持分身，不用旧电脑账号状态替代新电脑登录。

内容任务先策划、学习拆解、原创生成和保存电脑，再质检和进入正确账号草稿。用户确认具体作品、账号、可见性后执行发布并核验结果。遇到验证码、账号不符、页面变化或结果不明就停，结果不明先查作品是否已经发布，避免重复投稿。

## 自己点击部署

解压整个压缩包到 U 盘，进入「自媒体技能套件」，双击「一键部署.cmd」。默认部署到 `%USERPROFILE%\SelfMediaWorkspace`。指定目录可运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "U盘实际路径\自媒体技能套件\tools\setup.ps1" -TargetRoot "E:\我的运营项目"
```

## GitHub 方式

使用现有私有仓库 `dong120ask-eng/AIadmin`，技能放在全拼目录 `yijian-jineng`（一键技能），完整交付 ZIP 名称为 `yijian-jineng-20261014-r6.zip`。先核验实际Release。当前方案采用已连接GitHub上传源码及GitHub Actions构建发布，不要求本机CLI登录；具体见 docs/GitHub老仓库部署.md。

仓库拥有者把完整 ZIP 上传到版本化 GitHub Release，并在可信发布说明中给出 ZIP 的 SHA256。下载并查看 tools/github-install.ps1 后，运行：

```powershell
.\github-install.ps1 -Repository "dong120ask-eng/AIadmin" -Version "v2026.10.14-r6" -AssetName "yijian-jineng-20261014-r6.zip" -Sha256 "发布说明中的64位SHA256" -TargetRoot "E:\我的运营项目"
```

这是参数示例，尚不是已发布的实际链接。仓库、版本和文件名必须与实际发布值一致；不可把 ZIP 文件上传进 Git 源码历史。私有入口需CLI登录；也可先通过已登录GitHub浏览器下载完整ZIP，再双击部署。公开仓库可以使用 -ReleaseUrl 指定真实Release链接。
