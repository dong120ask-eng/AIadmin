# PR #9 / #15 兼容性核查与安全合并说明

核查日期：2026-10-23（北京时间）。所有经营数据均为临时合成数据，无真实店铺运营验收。

## 结论与合并顺序

推荐先完成 PR #9 的审核并合并，再等待 PR #15 的 Windows 11 实机和运营人员试用验收，最后审核合并 PR #15。此次不合并 main，不转换 PR #15 的草稿状态，不创建或覆盖任何 GitHub Release。

两种原始合并顺序均有确定的 README 冲突；完整保留双方内容后，所得文件树完全一致，未发现代码、安装器或离线测试的不兼容。为了提前验证组合状态，在 PR #15 开发分支纳入 PR #9 的提交并解决冲突。因此 PR #15 现在具有对 PR #9 的显式提交依赖；PR #9 未进入 main 前，PR #15 的总差异会包含 PR #9 的文件，不能误判为新增重复功能。

## 核查基准

| 对象 | SHA / 状态 |
|---|---|
| main | `c5ff4480d2e392a078c839da6c9bd989aa1c3573` |
| PR #9 原始 head | `03e4cdd18e66edc3946b50a2197ee04ec84f870a`，open，非草稿 |
| PR #15 原始 head | `5968cc75996010ed3c82f133e5c982cc384346e6`，open，草稿 |

核查使用完整 git 历史、实际源码差异、工作流 YAML，以及 GitHub Actions 作业状态和 Windows 日志；未仅凭 mergeable=true 判断兼容。

## 隔离合并模拟

分别从上述 main 创建独立 worktree，采用 `git merge --no-ff`，不更改远程 main。

| 顺序 | 第一步 | 第二步 | 保留双方文档后 |
|---|---|---|---|
| main → #9 → #15 | 成功 | README 内容冲突 | 全部本地检查通过 |
| main → #15 → #9 | 成功 | README 内容冲突 | 全部本地检查通过 |

唯一冲突文件为 `ecommerce-suite/README.md`。保留安装器使用说明的更新，并将“独立 CI 与可重复发行”“员工离线试用入口”两个章节同时保留。两个模拟的解决后树均为 `cabebf3f22dc20553d2fe52adce16993ddfc098b`；两个构建产物逐字节一致，SHA256 均为 `6c6371c0ada7b575698178541b453cb2d258b44bfb28a406defcb542810c3ab0`。

每个模拟均实际运行：84 项工作台测试、36 项经营计算/自动化门控/质量回归、14 项安装/隔离/ZIP 安全回归，全部通过且无跳过；另通过历史包检查、6.1.0 构建与源码校验、独立进程 CLI/HTTP 验收。测试不代表真实平台接通。

## 确定问题与修复

1. README 冲突：如上保留全部功能文档，补充“技能套件发行包不包含运营壳”的边界，避免用户从技能 ZIP 查找不存在的根目录启动器。
2. 重复回归：原 pilot 矩阵重复执行 suite CI 已覆盖的 36 项离线回归；删除 pilot 的重复步骤，原 36 项测试文件和 suite 步骤完整保留。
3. 触发遗漏：补齐运营壳打包脚本、独立包验证脚本、中文 CMD 启动器的路径触发。
4. 过宽触发：仅安装器、技能、门控或发行变更不再触发 pilot；共享 `ecom_tools.py` / `data_quality.py` 的变更仍同时运行套件回归与 HTTP 集成验收。
5. 事件重复：suite 的 push 改为仅 main，开发分支通过 PR 事件验证，避免同一开发提交同时产生 push 和 PR 两轮 suite CI。保留合并后的 main 验证；这是对最终 main 状态的必要检查。
6. pilot 增加 main push 验证和独立 concurrency 分组；两套工作流的分组互不取消。checkout 不保留凭据，统一 checkout/setup-python 至 suite 已用版本。
7. 新增 `scripts/verify-ecommerce-package.py`，在中文/空格临时路径实际打包、核验每个文件的 SHA256 与 ZIP CRC、解压运行原有 12 项运营壳测试，并启动独立 CLI/HTTP 进程回读导出的合成报告。CI 四组环境均执行；原 12 项测试未修改。

安装器、安全测试、发行构建器和运营壳分析代码均与原 PR 内容逐字节一致；此次主要修复整合文档与 CI 兼容性，没有删减安装安全或运营功能。

## CI 职责边界

| 工作流 | 必要职责 | 矩阵 |
|---|---|---|
| Ecommerce Suite CI | 26 技能结构与脚本一致性、历史包校验、36 项离线回归、14 项安装/回滚/隔离/ZIP 安全回归、确定性构建与源码对照 | Windows/Ubuntu × Python 3.12/3.13 |
| suite reproducibility | 下载四个环境的发行产物，逐字节核验源码并比较 SHA256 | Ubuntu，依赖四组 suite 全通过 |
| Ecommerce read-only pilot | 84 项工作台/运营壳回归、完整源码 HTTP、独立解压包 12 项测试与 HTTP、Windows PS5.1/7 启动检查 | Windows/Ubuntu × Python 3.12/3.13 |

源码与解压包重复执行 12 项运营壳测试是刻意保留的交付验证：前者不能证明打包内容完整。共享分析工具变更同时运行两套 CI 也有独立目的；不是重复执行相同 36 项测试。

路径配置已做静态 YAML 场景检查，覆盖安装器、安全测试、共享工具、门控、UI、打包、启动器和 README。此静态检查不等于真实 GitHub 事件执行；组合提交需要实际云端 CI 证据。

## 实际证据

原 PR #9：[运行 39138203913](https://github.com/dong120ask-eng/AIadmin/actions/runs/39138203913)，四组矩阵及跨环境重现性共五个作业成功；已读取 Windows 3.12 作业日志。

原 PR #15：[运行 39814536608](https://github.com/dong120ask-eng/AIadmin/actions/runs/39814536608)，四组作业成功；两个 Windows 作业 PS5.1/7 步骤成功。原 PR 描述中的“仍排队”已落后于实际运行状态。

修复版本地环境为 Linux / Python 3.12.14：84 + 36 + 14 项均通过，无跳过；独立 HTTP 验收通过；解压包 12 项测试及独立 HTTP 验收通过。新发行 ZIP 的构建与源码核验成功。其摘要与原 PR #9 不同，因为 README 已合并且补充发行边界；版本、源码提交与 Actions artifact 应共同识别产物，不能沿用旧提交的摘要。

组合修复提交：[`c3680c1988407ee7b116ec76b01a9e8c9cccbe26`](https://github.com/dong120ask-eng/AIadmin/commit/c3680c1988407ee7b116ec76b01a9e8c9cccbe26)。实际测试合并提交为 `9a34061f425f187233b52e094fead9fc171bb41b`，其树与本地受测树完全一致：`c3fd0c443d3de5a9dfaab8f91e03accf79400d8c`。

| 组合提交的实际 CI | 结果 |
|---|---|
| [Suite 39904141476](https://github.com/dong120ask-eng/AIadmin/actions/runs/39904141476) | 四环境各 36 + 14 项测试、安装与构建校验通过；第五项跨环境重现性通过，共五个作业成功 |
| [Pilot 39904141579](https://github.com/dong120ask-eng/AIadmin/actions/runs/39904141579) | 四环境各 84 项源码测试、完整源码 HTTP、解压包 12 项测试及 HTTP 通过，共四个作业成功；Windows PS5.1/7 均通过 |

已实际读取组合提交 Windows 3.12 的 suite/pilot 日志，以及重现性作业日志。四环境内层 `ecommerce-suite-6.1.0.zip` 摘要均为 `b78b8abfeb1a07cf225da55b374498e604d7f53e7f59eb10703cad9722fcd981`，与修复版本地构建一致。Actions 外层 artifact 的摘要可以不同，不应混为发行 ZIP 的摘要。

修复推送后再次从 main 模拟 #9 → 更新后 #15，以及更新后 #15 → #9：两种顺序均无冲突，结果树均与上述受测树一致。反向顺序中 #9 已作为 #15 的祖先而不再产生新变更；业务合并仍推荐先 #9，等待 #15 实机与人员验收。

机器可读的合并、测试、实际 CI 和历史资产哈希证据见同目录 `ECOMMERCE-COMPATIBILITY-EVIDENCE-2026-10-23.json`。随后补录这些结果只修改核查文档与 JSON，不改变上述已验证的程序、工作流或发行内容。

## 合并关卡与限制

- #9：审核安装/回滚/锁及发行脚本，确认最终 main 基准与 CI 未变化；按仓库策略启用必要检查。此报告不替代独立代码审核。
- #15：保持草稿，等待用户 Windows 11、中文/空格路径、浏览器视觉交互、真实业务文件、运营人员异常处置试用与验收证据。GitHub Windows runner 不等于用户实机。
- 合并前若 main 或任一 head 发生变化，应重新检查合并结果和受影响测试，不能把本次固定 SHA 结果无限延用。
- 历史 `dist` ZIP 与摘要文件未改动；所有新增构建均在隔离输出目录，CI 只上传 Actions artifacts。没有覆盖历史发行包。
- 演示与测试均是合成数据；未连接店铺、未执行采购/广告/改价/库存写入，没有真实店铺运营成功结论。
