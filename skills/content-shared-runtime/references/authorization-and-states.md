# 授权、状态和发布证据

## 状态
planned → researched → script_ready → assets_ready → rendered → quality_checked → awaiting_approval → approved → submitting → submitted → under_review → published。

文字任务可以script_ready → quality_checked；其他形式未生成成品时也可以审核脚本，但不能把脚本上传成视频或音乐。保存草稿用draft_saved，平台定时队列用scheduled。失败、阻塞和结果未知分别用failed/blocked/unknown，不能一律改成成功。

## 质量和批准
quality_checked必须存在真实产物及对应digest，审核项facts/originality/rights/media_quality/platform_rules/ai_and_commercial_labels/account_and_scope全部通过或说明不适用。审核method可以manual/automated/mixed；不能伪造专业人员审核。

approved必须有实际批准或配置中的auto_publish授权；scope与当前job匹配。draft_only不能走公开发布。审核和批准digest必须与实际文件一致，修改文件或目标账号后不能继续沿用。

## 防重复和未知结果
平台账号内容版本构成唯一任务；同键同负载复用，负载冲突报错。提交中先原子占用，不对同账号并发提交。点击后超时改unknown，先读作品列表／平台回执；未确认之前不重新点击。确实查无记录且经允许再由执行器安排新尝试，不让本地记账脚本擅自重发。

## 证据
提交回执记录identity_verified、platform_id、account_external_id、job_id、artifact_digest、source_mode(browser/api/manual)、observed_at、platform_status、post_id、public_url。字段要来自实际页面或接口，不能靠用户一句“已发”就编造回执。published需平台最终发布状态、真实作品ID、账号匹配，以及能取得时的公开链接；只有上传或审核中不够。

脚本的验证是结构和一致性检查，证据真实性仍由执行器读取真实系统并核验。不要使用脚本手工填假证据来演示发布成功。含个人信息的页面截图只作内部核验，按宿主政策保护，不自动向外发送。

## 终止与恢复
流程中断保留原状态及最后事件；不自动重跑submitting/unknown。可以继续没有依赖的其他账号。需要撤回／删除或重签协议时走明确授权，不借恢复任务扩大权限。
