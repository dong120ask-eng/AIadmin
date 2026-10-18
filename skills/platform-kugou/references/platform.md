# 酷狗音乐专项适配

## 创作角度
核实音乐人／发行入口和实际账号资质；检查曲目信息、音频、封面与授权；只写歌词时不得投稿为音频成品。

从项目母稿提取对该账号用户有用的一件事；写独立的开头、结构、标题、封面、说明与相关标签。保留共享事实与来源，避免同一矩阵原样搬运。

## 入口与规则核查
通过官方资料与实际账号后台确认creator_entry、account_kind、supported_formats、title_limit、body_limit、image_rules、video_rules、audio_rules、labels、links、scheduling、frequency、rights、eligibility和source_url/verified_at。未知值不能补猜。官方公开资料不能代替此账号权限，客户端与网页入口不能混为一谈。

## 发布步骤
调用共享工作流，使用已授权浏览器／官方API，核对账号唯一ID→作品列表防重→正确编辑器→上传真实文件→完善元信息→声明→预览→审核digest与授权核对→提交／定时→作品记录核验。

## 失败处理
记录真实登录、权限、工具、审核或网络问题。没有可用工具时只交付包；不虚构接口、选择器或发布结果。酷狗音乐的规则、入口及真实发布测试本轮状态为pending_e2e；实际测试后才更新verified_at与能力记录。
