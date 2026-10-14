# 配置、运行及恢复

Python 3.10+；render 需要 PATH 中 ffmpeg 和 ffprobe。不自动安装软件。示例 model 字段为空，必须填写控制台实际模型 ID；API Key 可以在对话框提供，由代理以 --key-stdin 首行标准输入传给 Python，或采用当前进程 ARK_API_KEY 环境变量。不得用包含密钥的 shell 命令、命令行参数或临时文件。脚本仅持有本进程凭据，state.json、plan.json、项目 JSON 和成片目录不保存它；宿主聊天/工具记录可能保存输入，不作完全无痕承诺。模型参数受账户权限、版本影响；先查官方文档再修改 video_options，不硬编码“最新模型”。

先执行plan（离线，无API），再执行write（付费文本与可选自动类型选择）、review（付费编辑审稿/有限返修），再多次执行video（每次最多一个镜头提交/查询/下载），全部镜头到齐后render，最后package。推荐直接由代理推进run，它按集顺序完成上述流程，复用通过的审稿与已完成集，不重复付费轮询文本。--episode指定样片；省略代表所有集。API网络调用最长45秒，返回任务ID后保存，稍后再查询，不持续阻塞，允许用户暂停。genres命令离线列出类型代码。

例如在 PowerShell 中：
```powershell
python D:/一键短剧/global-short-drama/scripts/drama.py plan --config D:/一键短剧/project.json --out D:/一键短剧/runs/pilot
```
其余命令可替换plan为write/review/video/render/package/run；不要在缺少模型配置时启动付费调用。首次生成将episodes设为实际目标值，使用--episode 1保持系列圣经完整。review_failed或结构不合格须报告原因，不能绕过审稿继续消耗视频预算。类型框架和质量说明分别见assets/genre-frameworks.json与references/quality.md。

状态保存在state.json，配置、导演指令及框架哈希绑定项目；它们发生变化必须新建运行目录，不覆盖旧项目。任务预算按调用次数和累计提交秒数保守预留，失败不自动退回，价格缺失则不得报告人民币上限已受控。供应商余额/限额是实际金额控制来源。预算覆盖全部重试但不能保证供应商计费粒度；人工处理unknown_submission前查询供应商任务记录及账单。

文件包含bible.json、genre.json、epNNN/source.json、各语言script.json/review.json/drafts、shots/*.mp4、captions.srt、master.mp4、qc.json以及invalid-drafts。字幕是镜头级初稿；实际时长以ffprobe为准。source与本地化JSON可审阅，但开始视频后改提示或参考图应新建run；替换逐镜配音/视频会通过尺寸/修改时间指纹使渲染缓存失效，正式发布文件另计算SHA256。此缓存策略用于日常素材修改检测，不声称防恶意篡改。

通过run --until-ready自动推进时，密钥只在该进程内存中复用，默认300步到检查点；步数耗尽保留状态，可继续run，不将耗尽当成完成。execution.max_inflight_video_tasks控制服务端在途生成任务，默认3，仍以账户并发额度为上限；遇限流或结果不确定先检查供应商，不自动增加并发或重投未知任务。参考图能力与后期工具分别由同级drama-assets、drama-postproduction补齐。

## 媒体替换

可将已制作/授权的镜头放到对应 shots/001.mp4 等位置；实际视频需至少达到分镜时长且带音轨。无音轨时，需为相同镜头提供 shots/001.wav（完整覆盖该镜头的配音与音效），render 将替换视频音轨；也可给带音轨镜头提供 wav 替换为已校对的译制音轨。渲染不自动生成 TTS，也不做时间拉伸；音频不足时阻止成片，返回待补录。

渲染按目标时长截取已够长的镜头，不足则拒绝，不复制帧补齐。每集保留干净画面 master.mp4 + SRT，方便平台侧字幕和进一步烧录。需要烧字幕时由代理基于实际字体执行 FFmpeg/libass，中文/阿拉伯文/RTL 等须预览验证。默认渲染保留原始镜头声音，跨镜头音色和响度需审片后调整。发布包报告包含机械 QC；仅当人工审片、字幕校时、素材授权和平台条件都完成后可进入上传。

## 已核验的接口来源（2026-10-14）

- [方舟 Chat API](https://docs.volcengine.com/docs/ark/chat-api?lang=zh)：POST /chat/completions。
- [创建视频任务](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)：POST /contents/generations/tasks。
- [视频教程](https://docs.volcengine.com/docs/ark/video-generation-tutorial?lang=zh&redirect=1)：GET /contents/generations/tasks/{id}，succeeded 时读取 content.video_url。

脚本测试通过只表明本地逻辑有效。无用户密钥时不进行真实付费验收；需要开通真实模型、生成第一集、核查声画，才可宣称供应商端已验证。
