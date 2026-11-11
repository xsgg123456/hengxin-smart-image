# 内网独立发布审查 · 第一轮

- candidateId：`aeec7ed5713da98fe1dcc8b3f1b1e714c2ed1af32dd05445910c00672b1726e2`
- 审查范围：`git diff` 及本轮所有未跟踪前端/release Python 文件；需求依据 `docs/INTRANET-INDEPENDENT-RELEASE-20261111.md:5` 至 `:11` 的七项合同与验收、Product-Spec / DEV-PLAN 同日追加。
- 审查方式：使用 `.agents/skills/code-review/SKILL.md`；独立读代码、复现、执行本地测试，并核对主 Agent 提供的 Linux/前端原始日志。
- 快照：审查结束前 `harness.py review-status` 的 `currentId` 仍为上述 candidateId；本轮未修改实现、未提交、未批准。
- **Stage 1：FAIL（1 个 HIGH、1 个 MEDIUM）；Stage 2：未执行。禁止按本报告批准或部署此候选。**

## HIGH-1：真实后端差异使交错独立发布被拒绝

合同要求“单侧发布和回退不改变另一侧版本”和“日常命令支持国内/国外完整发布”，并明确验收“国内→国外→国内交错发布”。当前只能在后端内容始终相同的测试前提下走通该流程。

证据：

- `scripts/release/intranet/package_release.py:188` 的 `write_package` 将该 Git 提交的全部 backend 文件原样纳入包；`:234` 的打包入口不按已部署侧基线合成 backend。
- `scripts/release/intranet/scope_release.py:21` 对比的是当前目标组 backend 与完整候选包。
- `scripts/release/intranet/scope_changes.py:157` 要求每个差异文件的 old/new owner 并集严格等于当前 scope。即使差异只属于另一侧、当前 scope 完全不可达，也会拒绝。
- `scripts/release/intranet/scope_changes.py:143` 先调用 `snapshot.compatible`；`scripts/release/intranet/snapshot.py:47` 及 `scope_changes.py:149` 又使 frontend 模式遇到另一侧 backend 差异直接失败。因此本问题也影响一侧完整发布后的另一侧纯前端发布。
- 现有交错测试 `scripts/release/intranet/test_scope_flow.py:154` 的 full 参数没有真实后端版本变化：其 fixture `:50` 在每个包内固定写入 `b'unchanged backend\n'`。所以测试通过不能证明生产要求中的后端交错发布。

独立最小复现：生成具有全部真实 entrypoint 名称、完整 source_files provenance 的临时 Python 源码树。基线所有 entrypoint 为 VALUE=1；国内包只把 `app/main.py` 改为 VALUE=2；随后海外 Git 包保留该国内提交，并把 `app/overseas/main.py` 改为 VALUE=2。直接调用真实 `scope_changes.check`，原始输出：

```text
first domestic full: ['backend/app/main.py']
next overseas full REFUSED: Single-scope backend change refused; shared/joint upgrade plan required: backend/app/main.py [domestic]
next overseas frontend REFUSED: Frontend-only release contains backend changes
```

修复标准：允许已证明在 old/new 两个图中均不被目标业务引用的其它业务独占 Python 差异保留于完整 Git 包；不能放行目标可达的跨业务共享改动、未知归属资源或依赖/schema/runtime 变化。frontend 模式仍不得启用目标 backend 差异。补真实源码差异的国内 A→海外 X→国内 C→国内回退及前端交错用例，验证另一侧状态不变。修复后重新固定 candidate 并重新从 Stage 1 审查。

## MEDIUM-2：旧静态兼容资源递归进入每个新版本

主 Agent 在收尾时补充的发现，经已读代码核对成立：`scripts/release/intranet/operations.py:17` 虽登记 `frontend_current_files`，但 `:19` 到 `:37` 复制 previous 下全部 assets，未用该清单排除上一轮 compatibility_files。因此 A→B→C 时，B 从 A 带入的资源再次进入 C，删除 A 目录也无法回收已复制的 A 资源。合同第 6 项“每组各保留最近两次”的资源保留范围仍有缺口。修复应只保留上一个成功版本自身的 assets，补 A/B/C 不递归复制与当前/上一页面资源可用的回归；不能以目录数量减为二代替净资源回收验证。该项为功能/保留口径核对，不代表已执行 Stage 2。

## 七项合同逐项核对

| 条目 | 结论 | 代码及验证证据 |
| --- | --- | --- |
| 1 分组版本/单侧隔离/公共代码识别 | 部分实现，HIGH-1 阻塞 | `scope_catalog.py:30` 仅推进目标组；`scope_engine.py:12` 基于当前 compose 修改目标服务；`scope_changes.py:137` 检测 owner，但过度拒绝不可达的其它业务差异。 |
| 2 复用现有发布、锁、事务、GC | 完整实现 | `release_cli.py:25` 在原 Store 锁内路由；`scope_release.py:31` 调用原 engine；`scope_engine.py:37` 使用临时适配并 finally 恢复；`full_cleanup.py:11` 复用原三个清理器。`test_scope_engine.py:99` 等用真实 engine journal/apply/recover、模拟外部命令验证作用域。 |
| 3 三组独立前端/同源身份/旧链接/资源 | 已实现，生产验收未执行 | `frontend/release-scope.config.ts:11` 单 module graph 与产物边界；`frontend/src/release/navigation.ts:12` 保留 query/hash 并跳转；`frontend/src/views/auth/IdentityPortal.vue:160` 切换和退出；`operations.py:13` 保留旧 assets；`split_config.py:18` 保留 legacy `/assets/`。三 scope 构建、产物隔离及七个真实构建浏览器场景日志通过（API 使用隔离 fixture）。 |
| 4 首次只增加静态服务、可恢复且不停止任务 | 已实现，生产验收未执行 | `split_config.py:37` 深拷贝并核对所有原服务保持；`migrate_split.py:79` 只 up 三个 UI、写 nginx 并 reload；`:117` 核对原容器/PID 与实际源；`:140` 恢复原 gateway/compose/ledger，只移除三 UI；`split_config.py:63` 保持 bind inode 写入。`test_split_migration.py:193`、`:225` 覆盖实际台账及失败恢复；真实隔离 nginx smoke 日志通过。 |
| 5 单侧排空、失败恢复接入、不碰共享 socket/另一侧队列 | 完整实现，但可达发布路径受 HIGH-1 限制 | `scopes.py:4` 明确应用/原生/worker ownership；`scope_actions.py:27` 只传目标 workers；`:35` 业务 scope 不 gate 账号；`scope_engine.py:47` 拒绝 shared full。`test_scope_engine.py:143` 覆盖排空失败恢复，`:185` 覆盖切换中断，`:234` 拒绝共享 full。 |
| 6 各组两次成功、GC 所有历史及实时引用、失败不推进 | 部分实现，MEDIUM-2 待修 | `scope_catalog.py:30` 只推进目标成功记录；`:51`、`:65` 合并三组 current/previous 源码、事务、镜像引用；`cleanup_refs.py:74` 读全部分组历史并由原 host 扫描器保护进程/挂载；`release.py:162` 清理位于业务恢复块外。`test_scope_flow.py:244`、`:261`、`:276` 覆盖长期未发布侧、POSIX 实删除及实时引用保护；Linux 日志 277 项通过。但 `operations.py:19` 递归复制过期 assets。 |
| 7 回退从当前全站合成，保留初次真实旧版，不回滚 DB | 完整实现的代码路径，真实变更交错覆盖不足见 HIGH-1 | `scope_release.py:41` 用当前状态新 prepare 而非重放历史全站配置；`scope_engine.py:12` 只替换目标挂载；`split_state.py:13` 初次 previous 使用真实 legacy current；`release.py:115` schema/data 不匹配拒绝恢复，没有数据库恢复命令。现有交错流程测试验证 compose/台账隔离，但 backend 全相同，须补真实差异回归。 |

无新增产品页面/API/数据库表；此次前端仍复用已有页面及身份组件，没有发现超出合同的新产品功能。共享后端联合维护明确不在本次范围，`scope_engine.py:47` 的拒绝符合合同，不作为缺失功能。

## 测试与编译证据

审查者独立执行本地 backend venv 的 pytest，原始末尾：

```text
186 passed, 72 skipped, 9 subtests passed in 20.40s
```

72 项 POSIX 路径测试在 Windows 跳过，不能以该结果宣称 Linux 验证。默认 `python -m pytest` 起初因默认解释器无 pytest 失败，后使用项目已安装 venv 成功，没有改依赖。

审查者对当前 intranet 全部 Python 文件执行 `compile` 的原始输出：

```text
PASS Python syntax compilation: 42 files
```

核对主 Agent 提供的 `output/intranet-independent-release/checks-20ae21fa0370fd4f.log:5`，其中执行器 `run_checks.py` 会先核对 tools manifest 和逐文件 compile，之后运行隔离 Linux 测试（包括 unify_release），原始输出：

```text
277 passed, 9 subtests passed in 9.31s
{"status": "PASS", "old_deleted": true, "previous_kept": true, "stopped_container_kept": true, "unknown_kept": true, "released_layer_bytes": 9115, "test_objects_remaining": 0, "production_images": 9, "production_containers": 17}
```

`output/intranet-independent-release/nginx-smoke.log:1` 原始输出：

```text
PASS real isolated nginx: 3 scopes/assets, legacy assets, 4 API paths/query, independent static replacement without gateway restart
PASS isolated smoke resources removed; production gateway identity unchanged
```

前端原始日志 `output/independent-frontend/unit-tests.log`：

```text
ℹ tests 546
ℹ pass 546
ℹ fail 0
ℹ skipped 0
```

三 scope 的 `build-domestic.log` / `build-overseas.log` / `build-shared.log` 原始末尾：

```text
✓ built in 44.61s
✓ built in 41.27s
✓ built in 20.84s
```

`output/independent-frontend/browser.log:1` 至 `:7` 为真实构建加载后的 legacy 深链、跨业务切换、统一退出、会话过期、撤权、503 重试和身份服务 404 不循环；API 为 fixture，不能代替正式身份服务联调。当前仅 inactive tools 安装及隔离测试，生产切换、生产任务/PID/容器前后对比和正式入口验收尚未进行。

## Stage 2

未执行。Stage 1 有 HIGH，按 skill 停止质量、安全扫描与实际邻居视觉对比，不给 Stage 2 PASS；文件长度等质量项留给新候选审查。
