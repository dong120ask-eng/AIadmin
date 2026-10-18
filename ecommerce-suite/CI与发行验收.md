# 电商套件独立 CI 与发行流程 6.1.0

基线：main c5ff4480d2e392a078c839da6c9bd989aa1c3573，实际已是 v6 / 26 技能。历史 v5 / v6 ZIP 及其 SHA256 保留，不覆盖。6.1.0 为本轮安装器和构建流程版本，技能内容未改写。

## 持续集成

工作流 `.github/workflows/ecommerce-suite-ci.yml` 在 main 的 push、面向 main 的 PR 中按 `ecommerce-suite/**` 及工作流自身路径触发，支持手动运行；本开发分支也支持 push 触发。只读仓库权限，无商家凭据、API 调用、发布或 Release 写入步骤。

四个矩阵：Ubuntu / Windows × Python 3.12 / 3.13。每个矩阵执行：

1. 清单与目录一致性、名称及 frontmatter、26 个技能和豆包入口、执行脚本与被测试源码一致性。
2. 现有 36 项计算、容量、自动化门控和数据质量回归。
3. 新增 14 项安装/隔离/发行回归；Windows 临时目录实际运行安装器两次，验证保留文件、冲突拒绝、幂等、故障回滚、重试与锁。符号链接测试可能因系统权限跳过，必须查看日志。
4. 历史 ZIP 的 SHA256、CRC、重复/危险路径、嵌套 WorkBuddy ZIP 与对应 Codex 源文件逐字节一致性。
5. 构建并重新验证 6.1.0 发行 ZIP、SHA256；独立任务下载全部四份产物，逐份对照源码，要求四个平台/版本的 ZIP 哈希一致。

Actions 日志提供逐项测试结果；产物包含 ZIP、SHA256、源码提交号、Python 版本、验收边界。失败时不通过 CI；任何一步失败不能视为整个矩阵通过。工作流检查不自动设置 GitHub 分支保护，管理员可将四个矩阵及 reproducibility 配为必需检查。

## 可重复构建

仅需 Python 标准库，仓库根目录执行：

```bash
python -X utf8 ecommerce-suite/tools/release.py check
python -X utf8 -m unittest discover -s ecommerce-suite/示例与验收 -v
python -X utf8 -m unittest discover -s ecommerce-suite/tests -v
python -X utf8 ecommerce-suite/tools/release.py build --output build/ecommerce
python -X utf8 ecommerce-suite/tools/release.py verify --output build/ecommerce
```

版本、技能数和发行文件名由 `release.json` 定义。ZIP 使用排序、固定时间戳、权限及无压缩方式，消除 zlib 和操作系统差异；目录属性规定 LF。产物包含构建和测试脚本，解压后可重复执行。校验同时验证文件摘要和完整源码内容，单独重写摘要不能掩盖篡改。请勿用 `python -O` 运行校验器。

不修改旧发行文件；产物写入独立 build 目录。当前通过 Actions artifact 分发，不创建 GitHub Release。原有 yijian-jineng 工作流不变。

## 安装行为与恢复边界

安装只操作用户指定项目的 `.agents/skills`。全量预检：已有同名技能完全相同则跳过，有修改则拒绝整次写入；其他技能和用户文件保留。先临时暂存全部技能，目标文件用独占创建，复制异常时删除本次新建文件和目录，然后可重试。项目目标/祖先的链接及 Windows junction 拒绝；源技能链接拒绝。项目锁阻止两个本安装器并发写入。

普通复制失败、磁盘错误及可捕获中断会尝试回滚。断电、kill -9、硬件故障不保证自动回滚；锁保留时必须停止其他安装任务、备份项目，检查本次安装目录和暂存目录，对照源文件确认哪些为残留，人工清理确认过的残留及锁后重跑。不得直接删除全部 skills。回滚本身遇到权限/磁盘故障也必须人工处理；不要在安装过程中用其他工具修改同一目录。

## 实机验收仍待完成

- 用户 Windows 电脑：中文路径、空格路径、权限受限目录、磁盘不足、杀进程/重启后的人工恢复；Codex 重开项目实际识别全部 26 技能并执行一个离线工具。
- WorkBuddy：26 个独立 ZIP 在实际客户端逐项导入，检查技能名称、引用路径、脚本运行与重复导入冲突行为。CI 只验证既有 `<技能名>/SKILL.md` 打包约定，不证明客户端支持或成功导入。
- 店铺：授权真实测试店铺、商家适配器、身份回读、单次低风险动作、回执和结果回读、超时后不重放。当前门控回归使用模拟适配器，不构成七平台连接或真实运营验收。
- 分支保护：CI 文件合并进入 main 后，管理员按仓库策略启用必需检查。

## 本地验证记录

本轮开发环境：36 项现有测试 + 14 项新增测试全部通过；技能结构、v5/v6 历史 SHA256/ZIP/WorkBuddy 结构通过。云端结果以 PR 对应提交的 Actions 链接及日志为准，不能由本地通过推断。
