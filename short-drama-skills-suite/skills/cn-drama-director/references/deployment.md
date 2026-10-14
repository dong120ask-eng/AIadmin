# 三个宿主的部署与验收

两个完整文件夹 cn-drama-director 与 global-short-drama 必须一起加载，不能只复制 SKILL.md 丢弃 scripts/assets/references。它们使用通用 name/description YAML、相对参考资料和 Python CLI，运行不依赖 Codex 专属 MCP。全流程需要宿主具备文件读写、shell、网络和用户允许的浏览器/官方发布工具。

本次按用户要求仅保留 D:/一键短剧 下的可审阅版本，不复制到任何实际技能根目录。下面是安装路线，不是已部署声明：

| 宿主 | 加载路线 | 已验证范围 |
|---|---|---|
| Codex | 两文件夹放入 C:/Users/120as/.codex/skills 或宿主认可的 .agents/skills | 标准 SKILL.md；本次不安装 |
| DeepSeek Harness | 项目 .dsh/skills 或 .agents/skills；也可配置 customSkillDirs | 官方代码确认 bundle 结构；需当前运行时启用技能 provider/loader，未启动宿主实测 |
| WorkBuddy | 使用技能页面添加/导入本地技能；本机存在 C:/Users/120as/.workbuddy/skills | 目录存在仅证明有技能根目录，不能证明自动发现；导入后须在技能页面验收 |

权威依据：[DeepSeek Harness 技能子系统](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md)、[WorkBuddy 技能说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)。不同版本技能启用机制可变，不写死未经确认的 WorkBuddy 安装命令。宿主中的方舟生成与宿主自身聊天模型独立；支持对话输入 Key 后用子进程标准输入传递，也支持子进程可见的 ARK_API_KEY。各宿主须支持非回显凭据输入或受保护通道；若只允许把密钥写进命令字符串，不能宣称已安全支持该路线，应采用环境变量或宿主凭据入口。

每个宿主的验收：确认两个技能在目录中→用同一句指令加载→产生合法导演 brief 与 project→离线 plan→经用户预算授权后生产第一集→检查普通话声画→用已授权平台后台完成一次发布并核对回执。前三步可复用本地文件测试，后几步需要实际账号，不能用模拟 API 代替。

统一调用示例：
“使用 cn-drama-director 和 global-short-drama。话题：失忆工程师与城市倒计时；6 集，每集 1 分钟，普通话；使用我的方舟模型配置，先出第 1 集样片，审核后准备红果、抖音、YouTube 的发布。”

“一键”指用户一次提出目标后代理推进阶段，遇预算变化、样片质量、平台登录、供片协议及上传/发布确认时仍按用户约定停下。脚本本身没有红果专用上传 API，安装三个宿主不会自动获得平台账号权限。
