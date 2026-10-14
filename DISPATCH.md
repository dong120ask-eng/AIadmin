# 多账号执行队列

2026-10-14。本轮实现本机SQLite持久化队列及安卓页面检查工作进程。真实浏览器、草稿保存和平台发布执行器仍未接入，不把队列完成状态等同已发布。

## 实际功能

- 任务按入队时间执行；同一时间按数据库入队顺序执行。
- 幂等键在本机资料分区内唯一；相同任务重复请求返回原任务，内容或绑定变化报冲突。
- 以浏览器profile_ref或安卓device_udid标识排他资源。当前浏览器任务保持blocked；安卓inspect_only任务可由本机Appium检查工作进程执行。
- 不同账号若指向同一设备也互斥，不同资料分区也不能同时占用同一物理资源；不同设备允许分别取得任务。
- 随机执行租约和到期时间限制旧进程更新。过期租约或执行异常标记unknown并保留资源隔离，不自动重试、不自动释放锁。
- 页面文件必须在当前任务专属目录；记录文件哈希，完成检查前复核实际文件，随后释放设备。
- 页面XML和数据库仅留本机，不进入源码库；普通队列读取不显示执行租约。

以上是本机单操作者工具，不是多用户身份认证系统。资料分区只用于整理。资源ID必须来自实际设备，尚未处理多种ADB别名指向同一设备的情况。设备ID匹配也不等于平台账号已核验。

## 任务入队

准备自己的binding.json和request.json，按ANDROID-SETUP.md填真实设备、包名及账号唯一ID。以下命令在本机终端执行：

```powershell
python -m workbench --data-dir data dispatch-enqueue --binding binding.json --request request.json --key inspection-001 --action inspect_only
python -m workbench --data-dir data dispatch-list
python -m workbench --data-dir data dispatch-run-inspection --worker local-inspector --server http://127.0.0.1:4723
```

每次dispatch-run-inspection取一个任务，连接指定安卓设备，读取当前页面结构，关闭Appium会话，保存data/device-inspections/<任务ID>/source.xml。不点击界面，不登录、不填写、不上传、不提交发布。没有可取任务时返回idle。执行工作进程不经网页启动。

使用--action draft或publish登记的任务当前保持blocked。已有publish-plan的形式、身份及接口检查仍保留，队列不把它升级为自动发布权限。

## 重启与核查

没有常驻守护进程或后台调度器。租约到期时由下次取任务或以下恢复命令检测；网页刷新不会自动执行或恢复任务。

```powershell
python -m workbench --data-dir data dispatch-recover
```

标为unknown后，先在电脑上停止旧检查进程、确认Appium会话与设备实际状态，再记录核查结论：

```powershell
python -m workbench --data-dir data dispatch-resolve --task REAL_TASK_ID --reason "已停止旧进程，核查页面检查结果" --worker-stopped
```

worker-stopped是本机操作者的明确确认，程序不能独立证明旧进程已停止。确认缺失则不释放设备。核查后原任务变为cancelled，不自动重新执行。确需新检查时用新幂等键建任务；未来真实发布结果不明时还必须查作品记录，不能仅取消任务后重发。

## 队列页面

启动工作台后打开http://127.0.0.1:8765/dispatch.html，查看账号、动作、阻塞和设备隔离状态。页面只读；发布任务不显示成功证据。

## 验证

66个Python测试通过，包括并发领取、跨账号／跨资料分区的同设备互斥、重启恢复、过期进程拒绝、幂等冲突、文件变化拒绝和本机协议检查工作进程。队列页面6项、媒体页面7项、原工作台8项JSDOM检查通过。CLI入队、持久化读取及过期恢复检查通过。没有真实设备、真实平台、真实账号或真实发布测试。

## 媒体核查增量

媒体登记中的专项渠道由12条增至18条：补充快手视频、抖音、小红书、B站以及头条文章和微头条。快手官方帮助提供电脑视频上传说明；头条官方帮助提供文章／微头条相关说明。其他入口或形式证据不足时保留pending，不因公众知道某平台能发布就冒充当前账号入口验证。

官方来源：
- https://www.kuaishou.com/help/feedback/4000?categoryId=hot
- https://creator.douyin.com/
- https://member.bilibili.com/platform/home
- https://creator.xiaohongshu.com/ （本次访问超时）
- https://mp.toutiao.com/docs/baike/2789/20594/
- https://baike.toutiao.com/

26个一级分类、250个榜单应用及10个指定补查项的原始范围没有扩大为全量应用。85个已观察二级菜单项仍需补采子榜单。真实平台执行器开发和验收持续待完成。
