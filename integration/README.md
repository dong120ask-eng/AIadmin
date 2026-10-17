# AIadmin × Codex Expert Teams 最小集成

这是开发任务的独立实验入口，不改变内容工作台的八类内容协议，也不合并 PR #1—#4。复用原有 `workbench.runner.invoke/codex_binary`、`Store.connection`，专家仓库的三个角色指令及软件协作工作流。新增 `expert_runs` 表；不把开发结果标为文章草稿。

支持范围：从文字需求制作一个 Python 标准库小程序，产品分析→开发→独立 QA→宿主测试→结果汇总。三个角色是串行独立 CLI 会话，不是 CLI 原生嵌套子代理；不支持任意已有仓库自动合并修改、自动部署或分布式调度。

## 固定依赖版本

| 项目 | commit | 用途 |
|---|---|---|
| AIadmin 主分支 | `761b4b0c15c4ec948941076aa546678b510e3beb` | 集成 PR 基线，无 workbench |
| AIadmin PR #1 | `fc16c314bf1091a789ca916443e5a293fac4acd1` | 可选的基础 workbench |
| AIadmin PR #3 | `f67c0bd616c872da1fd14bfb94d5ebaaad0a6fe3` | 本次运行的 workbench、72 项回归 |
| codex-expert-teams | `f4e869df86d11b2606883a2d3dd2aa1302b46476` | 路由、角色、安装器、工作流 |

将两个依赖分别检出到独立目录。不要 checkout 覆盖正在开发的工作目录。例如在 AIadmin 克隆中使用 `git worktree add --detach ../aiadmin-workbench f67c0bd616c872da1fd14bfb94d5ebaaad0a6fe3`；专家仓库独立克隆后 checkout 上述 commit。需要 Python 3.11+；既有工作台以 Python 3.12 为开发基线。

## 运行

默认只登记任务，不调用模型、不运行生成代码：

```sh
python integration/expert_bridge.py --workbench-root ../aiadmin-workbench --experts-root ../codex-expert-teams --runtime ../expert-trial --key slug-v1 --task "实现纯Python slugify函数：去掉两端空白，英文转小写，连续空格改为单个连字符；提供测试"
```

确认本机 Codex CLI 可用、认证有效，并在一次性开发环境执行；在上述命令追加 `--allow-execution --timeout 180` 才调用模型并运行生成的 Python 测试。此选项允许模型费用及当前用户权限下的代码执行。不要在有生产凭证的环境运行未经检查的生成代码。

适配器直接读取专家源码中的 `roles/*.toml`，替换 `{{SKILLS_DIR}}` 为专家源码 `skills` 路径。只复用 `developer_instructions`；不假称已注册 CLI 原生角色，也不自动继承未来 TOML 的模型/权限字段。

如需验证原安装器，可显式指定隔离目录，不修改全局配置：

```sh
python ../codex-expert-teams/scripts/install.py --skills-dir ../expert-install/skills --agents-dir ../expert-install/agents --include-roles
```

原安装器默认写 `CODEX_HOME/skills` 与 `CODEX_HOME/agents`（未设置则 `~/.codex`），保留已有同名条目，替换时备份；不会修改 `config.toml`。安装成功不证明当前 CLI 支持自定义角色。

## 状态与权限

- 幂等键按 tenant 分区；同键不同任务拒绝。同键终态不自动再执行，修改需求/依赖或人工重试请用新键并保留旧证据。
- 状态为 prepared→running→completed / failed / blocked；中断后保持 running，必须确认旧 worker 和子进程已停止，才能 `--mark-unknown --worker-stopped`。unknown 不会自动重跑。
- 产品、开发、QA 各自独立目录；交接使用校验文件和哈希。QA 不覆盖开发文件，验收固定交付快照。文件校验是检测，不是操作系统访问控制。
- CLI workspace-write 作用于本阶段，禁用嵌套多代理且不自动批准权限提升。角色提示词不授予账户、网络或外部服务权限；实际沙箱支持须在目标 CLI 实测。
- 本机单用户实验，不是多租户安全服务。运行目录、数据库和技能资料应由可信负责人持有；生成代码在宿主用户权限下运行，需容器/独立受限账号才能作为不可信任务执行平台。
- 成功必须有三个阶段的有效产物、独立 QA 测试及宿主测试退出码/数量；角色的“通过”文字不能替代测试。

## 测试

```sh
AIADMIN_WORKBENCH_ROOT=../aiadmin-workbench EXPERT_TEAMS_ROOT=../codex-expert-teams python -m unittest discover -s integration -p 'test_*.py' -v
```

Windows PowerShell 用 `$env:AIADMIN_WORKBENCH_ROOT` 和 `$env:EXPERT_TEAMS_ROOT` 设置相同路径。测试使用注入执行器验证协议与失败路径，不是实际模型生成。真实调用需另行按上面命令运行，查看 SQLite 证据和运行目录。详见 [兼容性与验收报告](verification.md)。
