# GitHub 老仓库部署

使用现有私有仓库 `dong120ask-eng/AIadmin`，技能源码放在 `yijian-jineng/`，老仓库原有文件保留。连接器可以上传这些源码，不要求这台电脑GitHub CLI登录。

GitHub Actions 从固定版本和SHA256的Python、GitHub CLI及31个依赖wheel构建Windows x64完整离线包，执行技能校验、58项回归和部署计划校验，再发布Release附件。构建使用GitHub为该任务提供的临时令牌，无需把个人密码、token或Cookie写入仓库。

目标版本 `v2026.10.14-r7`，附件 `yijian-jineng-20261014-r7.zip`。以实际Release状态为准：源码上传不代表构建已成功，构建失败时不得声称下载附件可用。

## 首次部署，不需要命令行登录

在有仓库访问权限的浏览器登录GitHub，打开仓库Releases，下载完整ZIP，解压后双击「一键部署.cmd」。也可把同一ZIP放进U盘，去另一台Windows x64电脑离线部署。

## 已有GitHub CLI登录时

从可信Release发布说明取SHA256，再执行：

```powershell
.\tools\github-install.ps1 -Repository "dong120ask-eng/AIadmin" -Version "v2026.10.14-r7" -AssetName "yijian-jineng-20261014-r7.zip" -Sha256 "实际发布的64位SHA256" -TargetRoot "E:\我的运营项目"
```

仓库保持私有。新电脑需用有访问权限的GitHub账号下载；本包不绕过权限。普通浏览器登录和CLI登录是两种状态，浏览器下载路径不要求CLI登录。不要下载「Source code ZIP」代替完整离线附件，它没有Python二进制运行环境。

旧的github-publish.ps1与「GitHub独立仓库发布.md」仅保留作新建独立仓库的备选工具，当前老仓库方案不调用它们。
