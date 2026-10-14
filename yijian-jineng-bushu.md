# 一键技能：立即部署

现有私有仓库： https://github.com/dong120ask-eng/AIadmin
技能目录： https://github.com/dong120ask-eng/AIadmin/tree/main/yijian-jineng
完整安装包： https://github.com/dong120ask-eng/AIadmin/releases/tag/v2026.10.14-r6

GitHub构建及发布已核验成功，47个技能、便携Python与依赖均在完整Release ZIP内，52项回归通过。真实平台发布验收仍待执行。

## 给AI的指令

请从上述GitHub Release下载 yijian-jineng-20261014-r6.zip，不下载Source code ZIP。仓库私有，先确认有访问权限的浏览器已登录。GitHub下载包的SHA256必须等于 dcafb8f6090707baeb7ceaaf9bd36345dcaaf297ea1ffe693edee44edf61040b。核验后解压，读取包内AI一键部署指令.md，按用户指定项目目录执行tools/setup.ps1，部署全部47个技能及本地工具副本；默认项目为用户目录SelfMediaWorkspace。保留旧技能备份，不改原账号和发布台账。

如果没有GitHub CLI登录，直接用已登录浏览器下载完整ZIP，解压后双击一键部署.cmd即可。本次GitHub源码上传与发布已经通过连接器及GitHub Actions完成，不需要用户继续做之前的CLI设备授权。

如果CLI已登录，可执行包内脚本：

```powershell
.\tools\github-install.ps1 -Repository "dong120ask-eng/AIadmin" -Version "v2026.10.14-r6" -AssetName "yijian-jineng-20261014-r6.zip" -Sha256 "dcafb8f6090707baeb7ceaaf9bd36345dcaaf297ea1ffe693edee44edf61040b" -TargetRoot "E:\我的运营项目"
```

## U盘部署

把GitHub完整ZIP或本地交付ZIP解压到U盘，双击「自媒体技能套件/一键部署.cmd」。部署时运行环境不需要联网，模型API、配音和发布仍需要网络及已授权账号。部署完成后工具副本保存在目标电脑，U盘可以拔出。

GitHub包与本地包来自不同构建环境，ZIP指纹不同：上面的dcafb8...仅用于GitHub Release。本地 delivery/yijian-jineng-20261014-r6.zip 使用 delivery/SHA256.txt 中的3bb786...指纹，不可混用。

新增模块和每项验证见源码 docs/剩余技能补齐与交付清单.md。开发与隔离测试完成，17个平台的真实页面校准和账号发布仍需后续验收。
