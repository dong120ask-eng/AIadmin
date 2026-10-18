# 工具数据契约

所有工具使用Python 3标准库，不需要模型API。只处理本地JSON，不抓取店铺，不登录，不执行远程变更。输入根对象含source_label、rows；rows不得为空；金额为人民币元、同期间，计数为非负整数。数值用十进制运算；金额输出两位。输出必须使用新路径，已有文件拒绝覆盖。

## 字段

- profit：record_id唯一；sku；net_revenue是已扣退款及商家折扣的净收入；merchant_subsidy为实际补贴；goods_cost是退货可回收成本调整后的净商品成本；platform_fees、ad_spend、fulfillment_cost、after_sales_net_loss、other_variable_cost均不得重复计入退款。售后净损失指未在其他字段计入的损失。所有金额必填，未知不能填0冒充。
- promotion：scenario_id；unit_price、quantity；merchant_subsidy；total_variable_cost含该情景广告履约等变动成本；unit_price_floor。operations为实际允许的按序优惠列表：multiply含factor(0到1)；subtract含threshold、amount、threshold_basis(initial或current)。不支持的玩法拒绝计算，手工建独立情景并核平台预览。不会自动发现可叠加规则；每次乘法按分四舍五入，与平台舍入差异须复核。
- inventory：每个物理sku仅一行，on_hand、reserved、safety均整数；requests按明确业务优先级排列，每项store_id和requested，不允许同店重复。输出配额提案，不是实时锁库存。组合SKU应先在库存源换算为物理扣料，工具本身不做BOM展开。
- funnel：channel、impressions、clicks、visitors、cart_users、buyers为同窗口兼容计数，买家和加购人数不大于访客、点击不大于曝光。零分母输出null；不能对跨渠道访客去重，不推断因果。
- after_sales：case_id唯一、sku、reason、refund_amount。统计工单数而非订单退款率；多工单同订单需先按业务目的整理。

## 平台导出映射

保留原始文件只读；记录平台、店铺、导出时间、期间、原始字段→标准字段、币种、税费、退款、广告归因窗口和去重规则。由人工或AI核映射后另存JSON。先抽样对照后台合计，差异未解释时停止经营结论。不得把平台报表空白默认为0。
