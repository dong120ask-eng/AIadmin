# 发布执行流程

## 授权与环境
从project.publish_scope确认mode、platforms、account_external_ids、topics、forms、time_window、daily_limit、confirmed_at；缺失不扩权。只管理本人或已授权运营账号。凭证存在执行环境安全位置，项目存credential_ref。每账号独立上下文；只能安全切换时每次重新核验。

## 实际步骤
从官方资料确认入口→选择指定账号上下文→核对唯一ID及名称→查重复作品和队列→打开正确形式编辑器→上传实际成品→填写标题正文封面标签→真实声明→检查平台预览→检查授权与审核digest→保存草稿／批准／提交／定时→查作品列表和回执→记录真实状态和作品ID→最终核验。

不要硬编码未经当前页面验证的按钮坐标或选择器。页面变化时重新读取状态和语义；找不到字段停止相应任务，不连续盲点。平台只能手机客户端投稿时标mobile_required，不能虚构网页入口。

## 账号与失败
同一账号会话不并发提交。唯一键包括企业、项目、平台、账号、内容ID及版本。提交阶段未知时冻结自动重试，先查询后台。上传故障可有限重试，默认最多2次；验证码、风险提示、身份和权限问题不盲重试。

拒审保存实际原因，按合法修正重新检查；不谐音、拆字、改分类或删声明规避审核。不自动删历史作品或误发作品，先暂停相关队列并按明确授权处理。

## 证据
本地evidence.json记录平台、account_external_id、job_id、artifact_digest、source_mode(browser/api/manual)、observed_at、platform_status、post_id、public_url及identity_verified。证据由执行器从真实页面或接口取得；账本脚本只验证字段和状态，不独立证明平台事实。内部截图含个人信息只作内部核验，不自动保存为对外交付。
