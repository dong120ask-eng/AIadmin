# 执行命令手册
PY为项目.venv-harness/Scripts/python.exe或已安装依赖的Python。ROOT是工作目录，SUITE为自媒体技能套件。命令参数分别传入，路径使用完整绝对路径。

1. 市场策划：当前助手读product-market-marketing，输出产品事实/人群/策略/来源到outputs。
2. 样本学习：PY SUITE/skills/viral-content-learning/scripts/learn.py --root ROOT --input config/样本.json --output work/frameworks.json。
3. 混合计划：PY SUITE/skills/account-content-factory/scripts/matrix.py --root ROOT --spec config/campaign.json --output work/plan.json。
4. 内容生成：当前宿主模型逐单读取plan中的prompt并输出独立content.json/body.md；API模式用generate.py --root ROOT --plan work/plan.json --profiles config/providers.json --provider 用户指定。默认不调用；apply才产生真实API请求。
5. 电脑制作：PY SUITE/skills/desktop-media-production/scripts/media.py cards|video --root ROOT --spec 对应规格JSON --output outputs/批次/job/cards或video。
6. QA和入队：queue.py enroll --root ROOT --plan work/plan.json --output state/批次映射.json，核对后apply。QA需另有真实报告再ops.py qa。
7. 发布：queue.py next --root ROOT --task TASK；按publish-*与dsh-account-matrix、dsh-android-control读取真实页面，使用锁、实际账号和内容确认。UI/浏览器submit包含一次attempt，不在外层再调用第二次attempt。
8. 结果：实际核验作品状态后complete；未知用uncertain；确认未发才not-published并重新确认。

样例是结构演示，不是真实产品、账号或发布授权。账号、设备、API端点和模型按用户真实环境配置。当前开发交付阶段不进行模型调用或真机发布测试。
