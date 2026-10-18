# AIadmin 五个PR集成与合并验收（2026-10-18）

## 结论
PR #1、#2、#3、#4已依次以合并提交进入main；PR #5保持开放草稿，未合并。不是五个模块全部生产验收完成。
本轮代码合并后的main：`066bd5ac42ebe1cb0a795c5cbe9901583f4cb328`。

| PR | 原始head | 结果 | 合并提交 |
|---|---|---|---|
| [#1](https://github.com/dong120ask-eng/AIadmin/pull/1) | fc16c314bf1091a789ca916443e5a293fac4acd1 | 已合并 | 23b3192cf8a08ab7b704e162b2168ccd9b866f49 |
| [#2](https://github.com/dong120ask-eng/AIadmin/pull/2) | ebb2157d04355a7811ba75f7c45355821321873a | base改为main、退出草稿后合并 | 767062740847af48a5d208346986bb364ab69718 |
| [#3](https://github.com/dong120ask-eng/AIadmin/pull/3) | f67c0bd616c872da1fd14bfb94d5ebaaad0a6fe3 | base改为main、退出草稿后合并 | 0b5eb9a06f7203a9a2e08a410227f1db2348eac2 |
| [#4](https://github.com/dong120ask-eng/AIadmin/pull/4) | 3bf337e90404b94dabce5e2eb4a588d85fcb97f3 | 退出草稿后合并 | 066bd5ac42ebe1cb0a795c5cbe9901583f4cb328 |
| [#5](https://github.com/dong120ask-eng/AIadmin/pull/5) | f911806cbecd8b9a1e37bb289809ee73acc4b49c | 保持开放草稿 | 无 |

## 最新基线及保护
开始读取main为2d17ddd，工作期间陆续新增53a69e8及后续安全审计提交，最终按a3381169792ce1047d9ffbaf928c9fe9e5cec827核对安全增量后合并。
新增审计记录说明四个旧Release ZIP已实际扫描，不能再沿用“全部未扫描”的旧结论；许可证、业务资料再分发权及隐私检查仍有阻塞。以现有OPEN_SOURCE_AUDIT.md及audit/RELEASE_ASSET_REVIEW.json为准。
本轮未改变仓库可见性、旧Release、标签、资产、发布流水线或安全检查。
GitHub比较a338116→066bd5a：ahead 13、behind 0，286个变化路径精确等于PR #1—#4路径并集；没有额外路径或缺失路径。yijian-jineng/、.github/、audit/、OPEN_SOURCE_AUDIT.md、tools/audit_release_assets.py均没有被本轮合并修改。

## 依赖与冲突处理
1. #1基于初始main；#2基于#1；#3基于#2。顺序采用#1→#2→#3。
2. #1合并后将#2目标改为main，#2合并后将#3目标改为main，避免只合入旧开发分支。使用merge保留祖先关系，没有squash、rebase或强推。
3. #4仅增加video-reference-suite/，与工作台和已有技能路径不重叠。
4. #5仅增加integration/及work/dev-team-status.md；目录共存测试通过，但仍使用外部workbench-root和固定专家仓库，不会自动成为工作台网页入口。
5. 本地Git无法匿名克隆私有仓库。通过已连接账号按固定commit读取文件，建立隔离内容快照；原始合并基线只有README。对#1—#3做合成快照三方合并，对#4/#5做新增路径共存演练。这不是完整原始Git对象历史复刻。随后GitHub实际执行四个PR合并，并复核最终路径差异。
6. 演练和远程实际合并均未遇到需要人工编辑的文本冲突，没有“选择ours/theirs”覆盖。
7. #2改向main后GitHub短暂返回mergeable=false。自动审批据此拒绝一次合并；随后多次重新读取为true，补跑当前main+#2的34项工作台和68项正式技能回归后再次执行，成功。未绕过保护或强行解决冲突。

## 本轮实际复跑
| 测试组 | 发现数量 | 通过 | 跳过 | 说明 |
|---|---:|---:|---:|---|
| 工作台、媒体、队列、安卓适配 | 72 | 72 | 0 | 模型/SDK有受控替身，不是平台实操 |
| 原正式技能回归 | 68 | 65 | 3 | 3项需要Windows PowerShell |
| 原短剧套件 | 49 | 49 | 0 | core 29、bundle 20 |
| 专家集成协议（#5） | 22 | 22 | 0 | 注入角色输出，宿主测试实际运行 |
| 合计 | 211 | 208 | 3 | 不重复累加补跑次数 |

其中已进入main的测试组共189项：186通过、3跳过；未合并#5的22项独立列出。
另完成：54项正式技能静态校验；43项开发技能依赖闭包检查；四客户端指令组合172份；六个视频技能两套布局及ZIP完整性检查；隔离项目安装六个视频技能、重复安装拒绝且原文件保持；app.js/dispatch.js/media.js语法检查。最新发行包审计脚本完成语法检查，没有再次下载发行包。
原专家仓库安装器“14项通过”是上轮记录，本轮未复跑，未计入211。
没有Actions运行或commit status记录的PR，不被当作“CI绿色”；本次主要证据是隔离环境实际命令和输出。

复跑命令：
```sh
python3 -m unittest discover -v
python3 -m unittest discover -s yijian-jineng/tests -v
python3 short-drama-skills-suite/verification/run_checks.py
python3 yijian-jineng/tools/check_release.py
python3 video-reference-suite/tools/package.py
node --check workbench/static/app.js
node --check workbench/static/dispatch.js
node --check workbench/static/media.js
# 仅#5开发分支或隔离共存快照：
AIADMIN_WORKBENCH_ROOT=/path/to/workbench EXPERT_TEAMS_ROOT=/path/to/pinned-experts python3 -m unittest discover -s integration -p 'test_*.py' -v
```

## 真实可执行状态
| 模块 | 本轮确认 | 尚未验收 |
|---|---|---|
| 工作台 | 本机HTTP、SQLite、项目隔离、八类任务包、审核、ZIP导出及失败处理测试通过 | Windows实机、真实浏览器视觉、真实CLI内容生成 |
| 43项开发技能 | 源码、闭包、四客户端指令组合可用 | 用户各客户端实际导入及调用 |
| 54项正式技能 | 原目录保留，静态校验与Linux可运行回归通过 | 3项Windows检查、真实账号各平台验收 |
| 媒体与队列 | 登记、持久化、设备排他锁、幂等、异常隔离、人工恢复；发布未接通时阻塞 | 用户USB手机/模拟器、真实SDK与账号切换 |
| 安卓适配 | Appium只读检查及可选SDK接口、设备身份拒绝路径 | 真实设备页面检查、草稿、对外发布 |
| 视频六技能 | 流程手册、结构、打包、隔离安装与保护检查 | WorkBuddy真实导入、视频生成、配音口型、剪映导出 |
| 专家集成#5 | 协议、证据门禁、幂等与失败路径测试通过 | AIadmin→真实Codex CLI→三个角色的端到端任务 |

skills/与yijian-jineng/仍是两套独立清单、安装器和台账，不把43+54宣称为97项已统一接入能力。视频套件也是独立交付目录。合并源码不等于已经统一账号、费用和执行器。

## #5保留草稿的具体原因及下一步
- 当前环境找不到Codex CLI；真实模型链路未验收。不得以22项模拟协议测试放行生产能力。
- 固定依赖codex-expert-teams@f4e869df86d11b2606883a2d3dd2aa1302b46476；仍须独立检出、指定experts-root。合并工作台后可指定同仓库根目录作为workbench-root，但必须重新记录依赖版本。
- 生成Python代码的宿主测试在当前用户权限运行；阶段目录和哈希不是操作系统沙箱。进入实际自动执行前需要一次性受限执行环境。
- 没有网页入口、分布式租约和认证型多租户隔离。
- 下一轮在受限环境安装/授权CLI，先最小READY检查，再一个标准库小任务，核对三个角色产物、独立QA、真实宿主测试数量、结果哈希、失败恢复及费用证据。通过后再决定退出草稿。

## 本次交付边界
已完成四个PR安全顺序合并和跨模块回归，未把内容系统、安卓发布或专家执行平台宣布为完整生产系统。没有使用真实客户素材、发布作品、修改账号或调用付费生成服务。
