# 内网独立发布审查 · 第二轮

- candidateId：`9644157ce0545ae1745ec28ddba875eb6dbe1751706b9efd4f75212263e7a179`。
- 范围：本轮 `git diff` 和未跟踪实现、测试文件，包含 frontend 独立入口及 release-scope 配置、intranet release/engine adapter/snapshot/catalog/GC/package/stage/首次迁移。需求依据为 `docs/INTRANET-INDEPENDENT-RELEASE-20261111.md:5` 起七项合同与执行验收，`Product-Spec.md:1486`、`DEV-PLAN.md:1706`。
- 使用 `.agents/skills/code-review/SKILL.md`。审查者未修改实现、未提交、未批准，第一轮报告保留。报告前再次运行 review-status，currentId 与上述候选一致。
- **Stage 1：FAIL，新增 1 个 MEDIUM；原 HIGH 和 MEDIUM 均修复。Stage 2：不签发 PASS，Stage 1 仍有未满足合同项；已做的补充质量检查和视觉证据单列如下，不能替代通过凭据。当前候选不能据此批准部署。**

## MEDIUM-1：独立回退后，回退前已打开页面的独有资源失效

合同第 3 项要求“已打开旧页面的资源受保护”；第 7 项要求独立回退。目前正向发布保留上一版本 assets，但回退没有提供相反方向的资源兼容。

证据：

- `scripts/release/intranet/scope_release.py:41` 从 previous.frontend 准备回退；`scripts/release/intranet/release.py:85` 在 rollback_target 存在时跳过 keep_assets。
- `scripts/release/intranet/scope_engine.py:29` 至 `:32` 将目标静态服务唯一内容挂载改为 previous.frontend。没有当前版本资源的额外只读挂载或回源路径。
- `scripts/release/intranet/operations.py:19` 至 `:42` 在 A→B→C 后使 B 含 A+B，C 含 B+C；因此 C→B 回退后 C 独有 hash 文件在服务根目录不存在。
- `scripts/release/intranet/split_config.py:13` 至 `:15` 的单一 try_files 会把缺失资源回退到 index.html，动态 import 得不到 C 的 JavaScript。
- `scripts/release/intranet/test_scope_flow.py:186` 验证回退的源码、compose 与台账，但不请求回退前版本的静态资源；`scripts/release/intranet/test_release.py:208` 只验证正向三次发布不递归累积。当前通过测试无法证明回退后的旧 tab 仍可懒加载。

独立复现直接调用真实 operations.keep_assets，以临时目录构造每版独有资源。原始输出：

```text
before rollback C assets: ['B.js', 'C.js']
rollback mount B assets: ['A.js', 'B.js']
open C lazy asset after rollback exists: False
```

修复验收：A→B→C→回退 B 后，C 独有 hash 仍返回原字节；缺失 assets 应返回 404，不能返回 SPA HTML；保持 B/C 历史完整包与清单不变，只有目标 UI 发生变化。若通过只读 previous 挂载 fallback 实现，还须校验挂载来源及只读属性、GC 保护实时挂载；下一次发布更新 fallback，不永久保留更早版本。主 Agent 已认可此缺口并提出该修复方向，本报告不提前批准尚未实现的新快照。

## 第一轮缺陷复核

| 问题 | 结论 | 证据 |
| --- | --- | --- |
| 真实后端差异使交错发布拒绝 | 已修复 | `scope_changes.py:145` 使用 full dependency/schema 检查，`:155` 至 `:179` 分别检查 old/new 所有权，允许两图中均不属于目标的另一业务独占差异；目标 frontend backend 差异仍拒绝。`test_scope_flow.py:186` 实际构造国内2→国内2海外2→国内3海外2→国内回退2；`:212` 覆盖另一侧 backend 推进后的 frontend 发布。`test_scope_changes.py:105` 起覆盖独占、共享、未知及两图归属边界。 |
| 兼容 assets 逐代无限复制 | 已修复正向路径 | `operations.py:19`、`:28` 仅复制 previous.frontend_current_files（旧格式排除 compatibility_files）；`test_release.py:208` 断言 C 只有 B+C，兼容清单只有 B、自身清单只有 C。回退方向遗漏另见本轮 MEDIUM-1。 |

## Stage 1 七项合同逐项核对

| 合同 | 结论 | 实现与验证证据 |
| --- | --- | --- |
| 1 各组版本、单侧隔离、共享识别 | 完整实现 | `scope_catalog.py:30` 仅推进目标组并核对其它组；`scope_changes.py:137` 对比两版实际源码依赖；`scope_engine.py:12` 深拷贝当下 compose，只替换目标挂载。真实差异交错测试 `test_scope_flow.py:186` 通过。 |
| 2 复用原 release、锁、事务、GC | 完整实现 | `release_cli.py:25` 共享 Store 锁；`scope_release.py:31` 路由既有 engine；`scope_engine.py:37` 用 context/finally 恢复适配；`full_cleanup.py:11` 复用原源码/镜像/产物 GC。`test_scope_engine.py:99` 运行真实 engine journal/apply/recover，宿主命令模拟且检查边界。 |
| 3 三组产物、同源身份、旧链接及资源 | **部分实现，MEDIUM-1** | `frontend/release-scope.config.ts:11` 选择 module graph 并检查串入其它业务模块；`frontend/src/release/navigation.ts:12` 保持 query/hash；`IdentityPortal.vue:160` 起处理跨组切换/退出。产物及七个 fixture 浏览器场景日志通过；正向 assets 兼容正确，回退后 C 独有资源不可达。 |
| 4 首次只增加三 UI，可恢复、不停原服务 | 实现完整，正式部署验收待执行 | `split_config.py:37` 逐个核对原服务不变；`migrate_split.py:79` 只 up 三 UI，`:102` 原 inode 写入后 nginx reload；`:117` 复核原容器与 PID、实际源；`:140` 恢复原入口/compose/台账，只删除对应三 UI。`test_split_migration.py:186`、`:220`、`:270` 覆盖成功/恢复/中断；真实 nginx smoke 两行 PASS。 |
| 5 目标侧排空与恢复、不动他侧和共享 socket | 完整实现 | `scopes.py:4` 至 `:25` 显式业务清单；`scope_actions.py:27` 仅向原 drain 传目标 workers，`:35` 不 gate 业务 scope 的共享账号；`scope_engine.py:47` 拒绝 shared full。`test_scope_engine.py:143` 排空失败恢复、`:185` 中断恢复、`:234` shared full 拒绝、`:242` shared frontend 只动 UI。 |
| 6 各组两次成功及所有实时引用保护 | 完整实现，资源可达性缺口见合同3 | `scope_catalog.py:30` 成功后推进目标 current/previous；`:51` 汇总所有组、staged、pending 引用；`:65` 聚合镜像保留。`cleanup_refs.py:65` 遍历所有组历史，复用宿主引用扫描；`release.py:162` 清理在恢复块之外。`test_scope_flow.py:291`、`:308`、`:323` 验证长期未发布侧、POSIX实删、依赖/挂载保护与净释放。 |
| 7 当下全站配置合成单侧回退、不回滚DB、迁移旧记录真实 | 回退版本/进程隔离实现完整；页面资源有缺口 | `scope_release.py:41` 重新 prepare 当下配置，`scope_engine.py:12` 仅目标侧修改；`split_state.py:13` 从实际 old.current 生成迁移 previous，不伪造业务后端发布；`release.py:115` schema/data 漂移拒绝恢复，没有数据库回灌。`test_scope_flow.py:186` 验证国内回退 A 不覆盖海外 X。 |

执行验收核对：完整国内/海外及三组 frontend 的命令入口已具备，shared full 明确拒绝，符合本轮范围（`release_cli.py:9`、`scope_engine.py:47`）。源文档已同步。Linux、前端构建、隔离 nginx/Docker GC 有下列日志。正式生产迁移、17 原容器/7 原生进程前后对照、真实任务只读状态和正式入口联调尚未执行，不属于本报告已验证成果。没有新增业务页面/API/数据库表，未发现合同外产品功能。

## 补充质量检查（不是 Stage 2 PASS）

- 测试真实性：本轮补齐完整 entrypoints/provenance 和真实 backend 内容差异，`test_scope_flow.py:47`、`:186` 不再以所有后端恒等证明交错发布。真实 engine 用例的外部命令虽模拟，但命令作用域有断言（`test_scope_engine.py:83`）；Linux 实文件删除和真实 Docker smoke 补足平台边界。仍缺回退后旧页面资源请求，见 MEDIUM-1。
- 安全扫描：对全部变更及未跟踪 Python/TS/Vue/MJS 搜索 eval、innerHTML、dangerouslySetInnerHTML、前端密钥、shell=True、硬编码密码；仅命中 `test_package_release.py:40`、`:176`、`:180` 的环境泄漏拒绝测试夹具。`scope_changes.py:30` 校验 provenance、路径、符号链接和文件哈希；`package_release.py:121` 环境允许名单；`migrate_split.py:140` 恢复时校验备份/配置/容器归属。未发现本轮新增的密钥泄漏、动态执行或注入。此结论不是依赖零漏洞声明；父 Agent 提供的依赖审计仍有既有漏洞，锁文件本轮未变。
- 结构：生产新增模块均小于 300 实际行；`test_scope_flow.py:23` 起是共用完整宿主 fixture 和集成用例，整个文件超过 300 行（含空行约 360），偏离技能行数目标但职责集中，未作为阻塞。`scope_actions.py:16` 的 shared_idle 及 shared/full 分支实际被 `scope_engine.py:47` 拦住，属 LOW 冗余，可后续删去，不应把这段不可达代码宣传为共享后端升级能力。
- 视觉：审查者实际启动 Chrome，以同一 1440×1000 fixture 对比 generic 基准与独立 shared/overseas 产物，并查看四张截图。业务选择布局、插画、按钮、海外 shell/无权限提示一致。`output/playwright/review2-visual.log:1` 至 `:4`：共享海外按钮两版均 x=932、y=312.234375、440×64、18px、圆角6px；海外切换按钮两版均 x=1246、y=14、86×32、14px、圆角6px；颜色均一致；`:5` pageerrors=[]。对应源为 `frontend/src/identity-bootstrap.ts:14` 与 `frontend/src/identity-main.ts:1`，原组件/样式复用。截图 `output/playwright/review2-{generic,independent}-{identity,overseas}.png`。国内 generic fixture 入口等待超时，本轮未完成国内截图对比，不据此推断生产故障，也不声称国内视觉已通过；新候选应补齐。浏览器 fixture 不替代生产身份联调。

## 测试与编译原始输出

审查者独立本地执行 backend venv 的 intranet 全套：

```text
199 passed, 72 skipped, 9 subtests passed in 24.47s
```

72 项为 Windows 跳过的 POSIX 检查；不是 72 项已验证。审查者独立语法编译：

```text
PASS Python syntax compilation: 42 files
```

读取本轮 Linux 原始日志 `output/intranet-independent-release/checks-f35ed882fc1cbcb4.log:6`。执行器 `output/intranet-independent-release/run_checks.py:8` 先核对部署工具 manifest、逐文件 compile，再跑 intranet 与原 unify_release 测试及 Docker smoke：

```text
290 passed, 9 subtests passed in 9.93s
{"status": "PASS", "old_deleted": true, "previous_kept": true, "stopped_container_kept": true, "unknown_kept": true, "released_layer_bytes": 9115, "test_objects_remaining": 0, "production_images": 9, "production_containers": 17}
```

`output/intranet-independent-release/nginx-smoke.log:1`：

```text
PASS real isolated nginx: 3 scopes/assets, legacy assets, 4 API paths/query, independent static replacement without gateway restart
PASS isolated smoke resources removed; production gateway identity unchanged
```

前端日志 `output/independent-frontend/unit-tests.log` 原始末尾：

```text
ℹ tests 546
ℹ pass 546
ℹ fail 0
ℹ skipped 0
```

三份 scope build 日志的原始末尾分别为：

```text
✓ built in 44.61s
✓ built in 41.27s
✓ built in 20.84s
```

`output/independent-frontend/artifacts.log:1`：

```text
PASS domestic: 1117 source modules, isolated graph and prefixed assets
PASS overseas: 738 source modules, isolated graph and prefixed assets
PASS shared: 355 source modules, isolated graph and prefixed assets
```

`output/independent-frontend/browser.log:1` 至 `:7` 为旧深链、跨业务切换、统一退出、会话过期、撤权、503 重试、404 不循环的七项 PASS；`generic-entry-css.log:1` 至 `:6` 为六入口 CSS 依赖检查。上述成功不能覆盖本轮复现的回退资源缺陷。修复后应重新 review-prepare 并从 Stage 1 复审，不批准本候选。
