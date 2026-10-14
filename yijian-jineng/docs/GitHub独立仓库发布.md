# GitHub 独立仓库

用户已选择新建独立仓库，名称 `yijian-jineng`，目标账号 `dong120ask-eng`。默认私有，避免无意公开本地营销资料。创建及上传需要本机 GitHub CLI 登录授权；创建和上传结果以 GitHub 实际页面及本地交付证据为准，不能把未核验的示例链接当成可用下载。

## 首次登录

双击包内 GitHub登录.cmd，在终端和 GitHub 官方网页完成登录。使用 dong120ask-eng 账号，授权动作由用户操作；不要把密码、验证码或 token 发给 AI。GitHub 连接器登录与 GitHub CLI 登录是两个独立状态。

登录、上传和私有下载入口会沿用当前电脑已经配置的 Windows 系统代理，仅设置当前 PowerShell 进程的 HTTPS_PROXY；不修改系统代理、不关闭证书校验，也不在脚本中记录代理地址或凭据。

## 创建及上传

tools/github-publish.ps1 默认只输出计划。它只允许创建上述目标私有仓库，拒绝复用已经存在的仓库；失败时保留本地源码和远端已完成结果，核对后再决定续跑，不自动重复创建或覆盖。

维护者将去掉运行环境和电脑私有数据的源码树准备好后，执行：

```powershell
.\tools\github-publish.ps1 -SourcePath "准备好的源码树绝对路径" -PackagePath "完整ZIP绝对路径"
.\tools\github-publish.ps1 -SourcePath "准备好的源码树绝对路径" -PackagePath "完整ZIP绝对路径" -Apply
```

脚本创建私有仓库，上传源码，创建 v2026.10.14-r3 Release，把完整ZIP作为Release附件上传，并在发布说明中记录 SHA256。需要 Git，便携 gh 已包含。Git 凭据助手仅在本次 push 命令使用，不修改全局 Git 设置。ZIP、exe、DLL、依赖wheel不进入源码历史。

## 私有仓库部署

登录有访问权限的账号后，从可信发布说明取得 SHA256，再执行：

```powershell
.\tools\github-install.ps1 -Repository "dong120ask-eng/yijian-jineng" -Version "v2026.10.14-r3" -AssetName "yijian-jineng-20261014-r3.zip" -Sha256 "发布说明中的64位指纹" -TargetRoot "E:\我的运营项目"
```

私有入口通过 gh release download 下载，复用CLI登录状态，指令不嵌入凭据。公开 ReleaseUrl 下载模式也保留。二者都核验 ZIP 指纹、压缩包路径与大小，再执行相同的本地 setup.ps1。

如果电脑没有任何工具：在已登录 GitHub 的浏览器中下载完整Release ZIP，解压后双击一键部署.cmd；或把相同ZIP放入U盘离线部署。这些是首次部署入口，源码目录本身不包含 Python 二进制，不能把源码ZIP误当完整离线Release。
