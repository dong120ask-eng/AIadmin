# 微信公众号网页草稿执行器：开发交付与验收缺口

基线：AIadmin main@280401c1ceedb42aab9ec38315204aab74163934。日期：2026-10-18。

## 当前结论

完成工作台/账号/队列集成及可配置网页驱动代码、隔离回归；**未完成真实公众号网页适配验收，不能开箱运行或宣称真实草稿成功**。本轮没有登录公众号、上传真实素材、保存真实草稿或发布文章。

官方后台访问在云端浏览器站点安全检查时被拒绝，尚未进入二维码界面。没有尝试其他浏览器、CDP、网络请求或代理绕过该限制。当前环境也未安装可选Playwright运行时。生产选择器、账号页身份字段及上传素材稳定ID必须在允许访问的授权环境中观察核验；本交付不提供猜测的选择器。

此前AIadmin-wechat-draft-mvp.zip已读取核对。它实现官方API草稿，依赖AppID/密钥；本次没有把该接口方案当作扫码网页方案，也未将旧文件整体覆盖main。

## 代码与边界

- `workbench/wechat_browser.py`：读取工作台已审核result.json、核对账号/项目/企业、文章与素材SHA256；草稿专用入队、持久化创建意图、单次保存、重新打开草稿回读；已知草稿ID的只读恢复。
- `workbench/wechat_ui.py`：显式配置的可选Playwright驱动，官方域名检查、唯一元素检查、标题/纯文本正文填写、封面及正文图片上传、保存按钮文字白名单、草稿列表按稳定ID查找并重新打开核对。**代码接口已写，当前真实DOM兼容性未验证**。
- `workbench/dispatch.py`：按动作领取任务，安卓检查不能领取浏览器草稿；保留浏览器会话锁，新增公众号账号锁，防止同账号不同profile同时写入；异常/租约到期保留两把锁。
- `workbench/__main__.py`：增加草稿入队、执行、只读恢复三个CLI入口。工作台原有公开发布入口保持阻塞，未新增发布功能。
- `tests/test_wechat_browser.py`：隔离测试，不访问网络、不使用真实账号。

核心仍使用Python标准库+SQLite。Playwright只在显式启用网页驱动时惰性导入，不自动安装。专用持久化profile仅存在操作者本地，可能包含浏览器会话，不进入任务JSON、仓库、日志或交付包。扫码、验证码在官方界面完成，本次未发生扫码。

本轮未增加网页按钮；从现有工作台生成/审核文章后，通过CLI驱动同一Store和DispatchQueue。内容生成仍使用既有Codex适配器，未对生成模型做真实调用。

## 任务包要求

工作台job须是 `platform=wechat`、`content_type=article`、绑定真实账号、`state=checked`；四项审核及artifact_digest必须对应当前产物。不是模板brief。

生成的 `artifacts/result.json`：

```json
{
  "content_type": "article",
  "deliverable_status": "text_draft",
  "payload": {
    "title": "实际已审核标题",
    "body": "实际已审核纯文本正文，100至20000字",
    "browser_assets": [
      {"path":"cover.png","sha256":"实际文件SHA256","role":"cover"},
      {"path":"body-1.jpg","sha256":"实际文件SHA256","role":"inline"}
    ]
  }
}
```

browser_assets必须在审核之前放入任务产物；修改后须重新生成审核版本，不能手改数据库伪造审核。首版必须一张封面，0至19张正文图片；图片PNG/JPEG，每张不超过10MiB。路径相对 `--assets-root`，禁止越界及内容哈希变化。标题上限64字是本执行器内部限制，不代表已核实平台最新规则。正文图片按清单顺序附在正文末尾，尚不支持图文穿插位置、HTML排版、摘要/作者/原创声明等扩展字段或多篇图文；有这些要求的任务暂不应入队。

账号external_id与binding.account_unique_id须使用官方页面可核对的唯一标识，不能仅用昵称；既有identity_verified_at不是本次会话的身份凭据，每个UI写入步骤前重新核对实际页面ID。

## CLI接口

以下是开发接口说明，**不是当前云端已可执行的公众号操作**。缺少真实选择器/登录会话时停止，不创建虚假成功记录。

```sh
python3 -m workbench --data-dir data wechat-browser-enqueue \
  --job JOB_ID --binding binding.json --assets-root assets \
  --key REVIEWED_VERSION_KEY --authorize-draft

python3 -m workbench --data-dir data wechat-browser-run \
  --assets-root assets --config verified-ui.json --profiles-root local-private-profiles

python3 -m workbench --data-dir data wechat-browser-reconcile \
  --assets-root assets --config verified-ui.json --profiles-root local-private-profiles \
  --task DISPATCH_TASK_ID --worker-stopped
```

binding沿用现有validate_binding字段，channel_id为wechat-official-draft、route为browser、profile_ref为专用本机会话名称。

UI配置是本机受信任开发配置，不由网页或任务正文提供；字段仅profile_ref、ui_verified_at、selectors。selectors须完整包含：identity、new_article、title、body、save、draft_list、draft_rows、row_title、row_open、draft_id、cover_input、cover_confirm、cover_image、inline_input、inline_images。不得把“发布/群发”控件配置为保存控件。驱动另外校验保存按钮文字。draft_id、draft_rows与素材元素当前要求具有稳定data-id；实际页面若不满足，必须修改并测试驱动，不能编造ID。**ui_verified_at仅为操作者配置记录，不是本轮已验收凭证。**

## 状态、恢复与证据

普通dispatch-enqueue草稿仍blocked；只有专用worker检查已审核产物和草稿授权后可入队。执行前持久化账号+文章内容指纹，覆盖不同任务key的重复提交。保存超时或断线不会自动重试；即使取消队列任务，创建意图仍保留，防止盲目重建。

有草稿ID：记录后只读重新打开核对；失败进入unknown，保留资源隔离。恢复要求操作者确认旧进程已停止，重新验证审核版本/账号/素材，仅回读，不再填写或保存。保存后尚未记录ID即崩溃：必须人工查后台，不提供自动再次创建。

SQLite browser_draft_attempts保存指纹、草稿ID、素材ID映射及核对摘要；dispatch_events保存时间与状态。回读核对标题、规范化正文、封面及正文素材ID、草稿列表重新打开标志。没有复制token URL或保存整页HTML。未取得真实草稿ID、截图或后台记录，本轮真实证据为空。

隔离端口完成为test_verified，draft_saved=false、backend_record_verified=false。只有实际官方浏览器端口完成回读才可draft_saved；所有路径publishing_verified=false。此端口由本机受信任代码加载，不是安全隔离的第三方插件沙箱。

## 实际测试结果

命令：`python3 -m unittest discover -v`

发现94项，94通过，0跳过：既有工作台/媒体/队列/安卓72项 + 新增公众号22项。新增覆盖跨租户/串号、审核与素材变更、路径越界、重复key、不同key相同内容、会话与账号双锁、过期隔离、保存结果不明、损坏回读、已知ID只读恢复、缺配置及禁止发布。

这不是189项旧集成测试的全量复跑；正式技能、短剧和视频套件未改动，未在本轮复跑。没有将之前的测试数量加进本轮通过数。CLI帮助与Python语法加载通过。Playwright实浏览器驱动未执行；不存在真实UI自动化成功证据。

## 尚未通过的验收关卡

1. 在政策允许访问且已授权的环境中观察当前公众号页面；核实唯一账号标识、编辑器/草稿列表/素材ID，配置或修订真实DOM驱动。当前云端访问被拒绝，不要求用户提供密码、Cookie或token。
2. 安装并验证可选浏览器运行时；在专用本机会话由用户完成官方扫码。现驱动遇到登录墙直接停止，尚未提供专用profile首次登录向导。
3. 提供一篇真实审核文章及封面/图片，完成实际填写、保存、草稿列表重新打开与内容素材核对，保存可追溯的草稿ID及脱敏核对证据。
4. 实际验证保存中断、会话失效、账号切换、图片上传异步完成及后台DOM变化等故障路径。

上述关卡通过前保持草稿PR，不合并为生产可用声明。未请求或执行正式文章发布。
