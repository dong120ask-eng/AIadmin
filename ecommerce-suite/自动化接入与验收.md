# v6执行器契约（替代v5）

这是单机串行门控原型，无七平台内置适配器。活动报名/修改、广告计划、价格、库存写入固定阻塞，尚未有资金、活动资格及库存专用校验器。

## 配置

- mode：preview或execute，默认preview；stop=true全局暂停；stores[内部唯一店铺键]含tenant_id、platform及可选paused。
- authorization：valid_until含时区、可选revoked、stores、actions、targets_by_store，以及bindings[店铺键]={tenant_id,platform}。读取动作同样需要授权。
- adapters：店铺键→可信本机程序argv，shell=False。程序只能来自用户确认的来源，不从页面指令安装或运行。
- tasks：task_id、store_id、target_id、action；写任务需operation_version、expected_before、desired_value。版本不可用来跳过未决记录。
- max_observation_age_seconds：1至3600整数，默认300；每批最多1000任务，超量需显式分批，不静默丢弃。

读取动作campaign_detect/product_read/metrics_read/ad_report_read；商品写动作product_title_update/product_main_image_update/product_detail_update/product_selling_points_update。平台素材上传审核、商品限制和真实CAS均为适配器职责。

## 适配协议

stdin JSON含op(read/write)、tenant_id、platform、store_id、target_id、action、idempotency_key。所有响应stdout JSON必须逐一回传这六个身份字段，ok=true及observed_at（ISO含时区）。读响应value；可写对象还需revision非空字符串和atomic_compare_and_set=true。写请求附expected_revision/expected_before/desired_value；适配器必须由真实服务执行原子比较及去重。写响应receipt_id非空，不能以假回执通过。

响应体上限检查为接收后检查；subprocess.capture_output仍会占内存，宿主须限制适配器资源与输出。身份回传不是恶意适配器的安全边界，运行前审查并只授最少凭据。

## 状态与日志

SQLite新表tasks_v6和追加events_v6；状态prepared/read_verified/running/submitted/verified/unknown/blocked。already_verified为本轮未重放提示，不能当本轮业务验证。读取结果不直接返回正文，日志只记内容哈希与时间；业务分析需从已授权、受控的数据文件通道取得原数据。

单机锁文件规范化state绝对路径，多个主机/不同数据库不保证全局互斥。进程崩溃需先核平台未决动作再处理残留锁。原始配置运行中不自动重载，不宣称动态热撤销；紧急停止由宿主终止执行并对账。

启动命令：`python scripts/automation.py --config assets/config.example.json --state 新状态库.sqlite --output 新回执.json`。旧配置不自动提升权限，缺字段默认阻塞。示例无平台适配器且授权为空，应该阻塞，不是坏包。

# v6共用执行要求

按租户、平台、店铺、对象核身份和授权；读取与写入均须有效权限。每次调用检查授权有效期/撤销/店铺暂停；授权撤销后不得复用旧任务回执冒称本轮成功。配置是单次运行快照，不是跨进程实时撤销服务；紧急停止须停止宿主工作进程。

业务键包含租户、平台、店铺、对象、动作、前后值和operation_version，展示task_id不参与去重。同一对象有running/submitted/unknown时阻塞任何版本的新写入，不通过换版本绕过。使用一份规范绝对路径状态库及本机锁；不声称分布式排他。

适配器所有响应需回传租户/平台/店铺/对象/动作/幂等键和带时区observed_at，默认300秒时效，禁止过期和明显未来数据。写入前读取值并取得revision；执行时要求适配器明确支持atomic_compare_and_set，携带expected_revision由远端原子校验。本地读后写不能防止人工同时修改；声明CAS也不等于已真实验收。

先检查前值，再次检查授权，持久化running后写入。写入失败/超时/错对象/无回执都视为未知，不自动重放。读回值一致只表示平台存储值确认，审核、前端生效、订单和利润分别验证。报名、预算、价格和库存写入仍因专用校验缺失而阻塞。

日志只保留身份、状态、时间与内容指纹，不落完整买家或适配器返回体；真实回执可保存于用户受控业务系统，日志记录其索引/指纹。引用用户数据时最小化、脱敏。输出文件先独占创建，已有输出不能覆盖；状态库/配置不可作为输出。

旧v5 tasks表保留；存在旧未决写入时v6全局阻塞新写，须平台对账并归档结论后迁移。不得删库解锁。恢复备份后重新核所有可能已执行动作。资产、账号、数据和授权不得跨客户混用。
