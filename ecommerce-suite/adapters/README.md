# 首个平台只读适配器：淘宝／天猫 TOP

2026-10-18；基线 main c5ff448。不是平台接通报告。

## 已实现与证据

- 官方 HTTPS TOP 请求、MD5 签名、15秒超时、拒绝重定向、响应大小限制。
- 先调用 taobao.shop.seller.get 核对平台实际 sid，再读取 taobao.items.onsale.get。
- 只支持 product_read，target_id=onsale；返回在售商品 ID、标题、价格、数量与状态。不是 SKU 完整档案，不含仓库商品。
- 每页40条，最多5页；超限 complete=false。目录可能在读取期间变化，snapshot_atomic=false；总数变化或重复商品直接失败，无法保证静态快照。
- 回传原有门控六个身份字段，复用 tasks_v6/events_v6、停止开关、授权校验和内容哈希。
- evidence 保存实际方法、无凭据业务参数、响应哈希与时间。未保存响应全文或签名。平台错误消息不回显；当前错误码与请求ID尚未采集，需真实授权阶段补充安全字段。
- metrics_read、ad_report_read、campaign_detect 与所有写操作均拒绝。不把商品数量当成交额、流量、利润或活动资格。

测试命令：

```sh
python -m unittest discover -s ecommerce-suite/adapters -v
python -m unittest discover -s ecommerce-suite/示例与验收
```

本轮8项适配器隔离测试、36项原回归通过。身份、分页、门控测试使用合成响应；签名对照官方文档示例。未发真实商家API请求，无平台回执、无后台对账、无真实业务验收。

## 接入条件比较（2026-10-18查阅）

|平台|官方入口与条件|本轮结论|
|---|---|---|
|京东|https://jos.jd.com/doc/channel.htm?id=994 公告指向 https://open.jd.com ，商家应用需对应权限与授权；迁移范围和新接口契约需控制台复核|暂不基于旧JOS接口开发|
|淘宝／天猫|https://developer.alibaba.com/docs/doc.htm?articleId=101564&docType=1 自研应用、应用权限、商家session；自研不可直接用于他人店铺，同集团需报备|文档足以实现首版只读，但未发现当前环境有可用店铺授权|
|拼多多|https://open.yangkeduo.com/application/home 提供商家自研管理系统接入|公开入口可核实；具体商品、经营和活动权限及接口字段未完成核实，不能宣称可用|
|抖音电商|https://op.jinritemai.com/docs/guide-docs/127 自用型和工具型；https://op.jinritemai.com/docs/api/84/7277 商品列表V2|可作为下一候选；需核对应用类型、商品权限与店铺授权，不使用生活服务接口替代抖店接口|

选择TOP是文档明确且协议可独立验证的工程默认，不表示用户已有淘宝授权，也不表示其审批最容易。如果其他平台先具备真实授权，应调整优先级。

协议来源：
- 店铺身份：https://developer.alibaba.com/docs/api.htm?apiId=42908
- 商品列表：https://open.alitrip.com/doc2/apiDetail.htm?apiId=18
- 签名：https://developer.alibaba.com/docs/doc.htm?articleId=101617&docType=1

## 运行与授权

只从宿主安全环境读取 app_key、app_secret、session，不要把真实值提交、写进配置或聊天。每家店使用独立环境变量名。绑定文件仅放引用和身份：

```json
{"tenant_id":"企业内部ID","platform":"taobao","store_id":"内部店铺ID","shop_sid":"真实平台店铺sid","credential_env":{"app_key":"SHOP_A_APP_KEY","app_secret":"SHOP_A_APP_SECRET","session":"SHOP_A_SESSION"}}
```

门控 stores 使用相同 tenant_id/platform/store_id；authorization 须覆盖该 store、product_read、onsale、有效期及 bindings（结构见现有automation-contract）。adapters[store_id] 配置绝对路径 argv：

```json
["python","/absolute/repo/ecommerce-suite/adapters/top_readonly.py","--binding","/private/shop-binding.json","--data-output","/private/new-snapshot.json"]
```

业务快照独占创建且Unix权限0600，含商品及证据；门控数据库只落哈希。每次运行使用新快照路径；Windows须另设目录ACL。该文件不是新增授权入口；生产调用必须经过门控，禁止把适配器暴露给不可信调用者。快照写出后仍需核对门控最终read_verified，不能仅凭文件存在判断验收。

## 真实验收待办

1. 店铺负责人确认主体、真实sid、应用类型及三项凭据安全注入；在平台控制台核对shop.seller.get和items.onsale.get权限。未获授权不请求。
2. 只授权product_read/onsale、短有效期，运行门控并保留状态回执与受控快照。
3. 与相同店铺、相近时间后台在售列表对照总数，抽查至少3个商品ID、标题、价格和数量；超过200条只验收局部覆盖，不宣称全店完成。记录双方时间、后台截图引用、差异及负责人结论。
4. 权限失败、令牌过期、限流和超时保留阻塞，不自动重试；补充平台安全错误码和request_id采集后再验收故障诊断。
5. 经营数据与活动检测须单独确认真实官方接口、权限、口径和后台对照，当前阻塞。

## 多店条件

自研应用不能作为跨主体代运营通行证。需要合适ISV应用及各店独立授权、租户和sid绑定、凭据隔离、过期刷新/撤销流程、平台频控及增量分页、独立快照留存和对账。现有门控为单机串行；跨主机需另实现全局任务占用与租户权限边界。多店压测与真实店铺验收尚未进行。
