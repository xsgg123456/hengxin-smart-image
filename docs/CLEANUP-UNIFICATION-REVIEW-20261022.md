# 自动清理统一修复 · 独立审查（首轮阻塞）

- candidateId：`4cb36e072a7d79d65b94c05f4838cd0b21d9fecd1ad8a94cd16eefc832e01f28`。
- **Stage 1：FAIL，2 项 HIGH。Stage 2：未执行。不得为此候选登记两阶段 PASS。**
- 使用 `.agents/skills/code-review/SKILL.md`，读取 AGENTS、快照协议、Product-Spec/DEV-PLAN 本轮原文和 `docs/CLEANUP-UNIFICATION-20261022.md` 全部合同。
- 范围：本次 13 个增量代码/测试文件；下文 `backend/` 均相对仓库内 `hengxin-smart-image/`。此前 records、预览、发布准备等继承候选 `e40dcd0f8dd9823e4cbb5752a2a4ed376c19f61c6a2365f7ec39b7e42537be5d`，依据 `docs/RECORDS-SCOPE-REVIEW-20261022.md:1`，不当作本轮新增功能。
- 审查开始、阻塞复现和报告初稿时只读 `review-status` 的 currentId 均为本报告候选，changedFiles 恰好为本次 13 文件；未发现继承代码漂移。报告收尾时主 Agent 已开始修复，currentId 变为 `73dc4372ac72aff435e77dd37160a2b155dcc8f328f067ed03bd93166d7ec84d`、新增 test_cleanup_mounts.py；本报告代码行号和结论只对应原候选，不批准修复中的新内容。reviewer 未改业务代码、未启动生产操作、未提交、未部署、未写 clean。

## Stage 1 · 阻塞问题

### HIGH-1：同设备 bind mount 穿过安全预检，实际删除根外文件

合同第 2 条（`docs/CLEANUP-UNIFICATION-20261022.md:12`）要求“仅允许配置执行根内明确 UUID 的私有会话目录”“挂载跳转等继续失败关闭”；第 3 条要求外部程序、其他会话和共享资料不得改动。

`backend/app/execution/cleanup_paths.py:44`、`:67` 仅用 `st_dev` 识别跨设备边界。Linux 同设备 bind mount 的目标仍是普通目录且 `st_dev` 相同，因此 `_open_child`、`inspect_fd` 都会接受。`:142` 的 rmtree 随后进入挂载目标，先删除外部文件，最终删除挂载点才抛 `EBUSY`；返回失败不能挽回已经删除的数据。两个业务 wrapper 均接到该共享实现（`backend/app/retention/paths.py:5`，`backend/app/modules/api_image_edits/deletion_paths.py:8`）。

独立审查提出该场景后，Linux 验证 agent 在独立 mount namespace、临时目录内构造真实同设备 bind mount。reviewer 已读取实际脚本 `output/cleanup-unification-20261022/linux-bind-red.py:6` 和原始输出 `linux-bind-red.log:1`：UUID 目标、cache、nested 三种位置全部 `same_device=true`，全部抛 OSError/errno 16，全部 `sentinel_exists_after=false`、`sentinel_intact=false`。这是真实删除临时 sentinel 的失败证据，不是模拟 st_dev 或仅理论推断。

原始输出节选（三种位置结果相同）：

```json
{
  "location": "target",
  "same_device": true,
  "sentinel_before": "external same-device sentinel",
  "exception": "OSError",
  "code": null,
  "errno": 16,
  "sentinel_exists_after": false,
  "sentinel_intact": false
}
```

依据：[Python 官方挂载判断说明](https://docs.python.org/3.12/library/os.path.html#os.path.ismount)明确说明设备号式判断不能可靠发现同一文件系统的 bind mount，不能用 `Path.is_mount()` 简单替换即宣称解决。

修复验收：配置根内 UUID 及其后代需验证挂载身份，而不只是设备号；缺少验证能力时失败关闭。三类真实同设备 bind mount 均须在任何 unlink/rmtree 前拒绝，外部 sentinel 字节不变；保留现有跨设备、链接、合法工具链接及缓存范围回归。改代码后重新固定快照审查。

### HIGH-2：一次性扫描仍输出含 SQL/凭据的原始异常

合同第 5 条（`docs/CLEANUP-UNIFICATION-20261022.md:15`）要求扫描异常日志不得包含凭据、私有路径或原始异常消息。

`backend/app/retention/worker.py:131` 调用安全 report 后，`:132` 的 `args.once` 分支仍在 `:133` 裸 `raise`。模块入口 `:141` 调用 main，未将此异常转换成安全非零退出。于是 `--once` 扫描失败的 stderr 又输出完整 traceback、SQL 和参数。`cleanup_diagnostics.py:69` 的脱敏注释只约束结构化日志，不能消除后续未捕获异常。

reviewer 使用本地后端 Python、纯合成 OperationalError 替换 `worker.run_once`，调用 `worker.execute_loop(SimpleNamespace(once=True, deletions_only=False))`；没有连接数据库或执行清理。实际 exit 1，原始输出：

```text
cleanup_deferred {"event":"cleanup_deferred","stage":"worker_loop","resourceId":"unknown","code":"CLEANUP_DATABASE_FAILED","errorType":"OperationalError","locations":[{"module":"retention/worker.py","line":129}]}
Traceback (most recent call last):
  File "<stdin>", line 8, in <module>
  File "D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\app\retention\worker.py", line 129, in execute_loop
    result = run_once()
             ^^^^^^^^^^
  File "<stdin>", line 6, in fail
sqlalchemy.exc.OperationalError: (builtins.RuntimeError) synthetic_private_DSN
[SQL: SELECT synthetic_private_SQL]
[parameters: {'token': 'synthetic_secret_token'}]
(Background on this error at: https://sqlalche.me/e/20/e3q8)
```

此裸 raise 为继承行为，但它不满足本轮新增的“扫描异常脱敏”合同，不能因 report 本身测试通过而放行。此证据只证明一次性入口，不声称持续 loop 的 catch 分支也会输出原异常。

修复验收：一次性命令失败保持非零退出，只输出安全诊断；补真实子进程 stdout/stderr 断言，确认原始 SQL/参数/DSN/异常链均不出现。保持循环扫描失败可继续及已存在的错误码语义。

## Stage 1 · 合同逐项对照

| 合同 | 实现情况、代码证据和验证 |
| --- | --- |
| 1. 自动缓存/历史与显式删除共享组件，参数和业务职责独立，海外不变 | 完整实现接线。`backend/app/retention/paths.py:5` 透传 cache_only；`backend/app/modules/api_image_edits/deletion_paths.py:8` 保持 api-edits 前缀。`backend/app/retention/api.py:120` 和 `deletion.py:127` 保持不同业务入口。相对已审快照 13 文件无海外代码。两入口专项见 `test_retention_paths.py:9`、`test_api_task_deletion_paths.py:66` 及 linux-target.log。 |
| 2. UUID、FD/no-follow、祖先和目标身份、链接、类型、硬链接、挂载边界 | **部分实现，不通过。** `cleanup_paths.py:221` UUID 规范化，`:48` no-follow 打开及身份校验，`:135` 复核祖先，`:26` 精确工具白名单，`:82` 类型及单硬链接检查。`test_cleanup_paths.py:30/:53/:102/:126/:153` 和真实 Linux 专项通过，Windows `:189` 三处 junction 拒绝通过；但 HIGH-1 同设备 bind mount 外部 sentinel 实际被删。 |
| 3. 24h cache/plugins、72h 整会话，保留原图、素材、成品、采用版本、归档、用量及外部资料 | **业务保留已实现，整体安全合同不通过。** `retention/state.py:7`、`:8` 时间阈值；`cleanup_paths.py:119` 缓存只列 cache/plugins；`retention/api.py:61` 先 preserve 汇总，仅擦会话/turn/job/outbox；`retention/objects.py:24` 按任务、item、version、turn及冻结 JSON 引用保留。`test_cleanup_retention_safety.py:42` 对缓存→历史过程逐次比较全部对象原始字节和元数据集合，`:98` 检查目录删后 DB 回滚；`test_api_retention.py:64`、`test_api_usage_facts.py:87` 与完整回归提供采用/统计证据。普通路径下已验证的保留结果不能覆盖 HIGH-1 外部资料误删。 |
| 4. running/uncertain、锁/屏障、每小时重试、25条、两阶段、pending恢复、幂等不刷新活动 | 完整实现且本轮保持。`retention/api.py:20/:39/:104/:106` 父锁、busy保护及持久 pending；`:130` 失败转 retry；`retention/worker.py:80` 上限25、`:83` 按 next_cleanup_at 扫描；`retention/objects.py:85` 独立对象回收与每小时重试。`test_cleanup_retry_pg.py:21` 实际 PG 定时扫描验证59分钟不重试、1小时恢复、last_activity不变、回执/对象仅计一次；`test_retention_concurrency.py:66/:87/:103/:122/:140/:188/:222/:241` 双清理、submit/claim/采用竞争及未知状态专项通过。 |
| 5. 结构化稳定错误码/脱敏位置，保留API通用文案，不迁移 | **部分实现，不通过。** `cleanup_diagnostics.py:26/:45/:57` 安全错误码、应用内位置、UUID和阶段白名单；`retention/api.py:131`、`objects.py:107`、`worker.py:71/:94/:131`、`deletion.py:135` 接线。`test_cleanup_diagnostics.py:14/:40/:49` 13个脱敏分类用例通过，`test_cleanup_retention_safety.py:66/:98` 故障调用层验证通过。原 `api.py:135`、`deletion.py:139` 页面文案保持，无迁移；但 HIGH-2 一次性入口仍泄漏原始异常。 |
| 执行边界：验证审查后停，不提交/部署/生产写；原records工作保留 | 匹配本轮审查操作。`Product-Spec.md:1`、`DEV-PLAN.md:1` 和合同 `:3` 明确边界；原候选 review-status 继承快照只差13文件。`docs/CLEANUP-UNIFICATION-20261022.md:29` 已明确未来需覆盖原生消费者，未将旧 records 发布脚本当作有效发布。当前失败候选不能宣称完成。 |
| UI、引导真实性与 Spec 漂移 | 本次没有新增页面/API/表/前端文案，已有通用文案保持（上述 api.py:135、deletion.py:139）。前端及旧发布准备与继承已审快照一致，因此本次无新 UI 数值/邻居页面比较对象；不重新宣称旧 UI 验收。共享模块、诊断模块及测试均在合同范围，无新增未授权功能。 |

未实现的必需行为：同设备挂载拒绝、一次性扫描终端输出全链路脱敏。无其他单列新增功能缺失；这不构成 Stage 2 质量或安全扫描通过结论。

## 实际验证证据与限制

reviewer 已读取 `output/cleanup-unification-20261022/` 中原始日志，而非只采用主 Agent 汇总：

```text
# linux-target.log
151 passed, 3 skipped, 2 warnings in 34.43s
# windows-target.log
57 passed, 26 skipped, 2 warnings in 8.70s
# linux-full.log（修复 bind 前；另保存 linux-full-pre-bind-fix.log）
2436 passed, 27 skipped, 10 warnings in 378.78s (0:06:18)
# frontend-tests.log
ℹ tests 355
ℹ pass 355
ℹ fail 0
ℹ skipped 0
# frontend-typecheck.log
> vue-tsc --noEmit
# frontend-build.log
✓ built in 40.60s
```

reviewer 独立编译命令和原始结果：

```text
cwd: D:/Work_Project/hengxin-smart-image/hengxin-smart-image/backend
.venv/Scripts/python.exe -m compileall -q app
exit_code: 0
output: （空）
```

reviewer 独立 `git diff --check` exit 0，仅 CRLF→LF 提示。前端 typecheck/build 的退出成功由主 Agent 执行记录提供，日志本身没有错误；没有将前端构建与本次后端两个安全缺口混为一谈。

- Linux专项3 skip为Windows junction，Windows已实跑；Windows26 skip为POSIX真实链接/FD/UID专项，Linux专项有相应实测。全后端27 skip = 22项缺独立Redis、1项既有non-root WSL环境、3项本次Windows junction、1项既有工作台Windows junction。最后一项既有Windows用例不在本轮Windows专项内，不标成本轮已验证。
- Linux为Python3.12.13、PostgreSQL18.6 UTC、隔离网络/临时Unix socket；不是生产PG16.15安装包测试。已知范围外Asia/Shanghai极端Retry-After溢出保留在上一轮验收文档，未被本轮修复。
- `linux-mount-proof.log:1` 证明两个入口 `/opt/codex/sentinel` SHA256保留、三处跨设备tmpfs拒绝；它没有覆盖同设备bind。新增 `linux-bind-red.log:1` 正好证明该盲区是真实缺陷。
- 全套通过只覆盖现有用例；本报告两个新增失败场景在现有全套中未被拦住。未执行生产重试、生产删除或发布，不能声明线上失败记录已恢复。

## Stage 2

**未执行**：Stage 1 有 HIGH，依 skill 停止。主 Agent 应先修复两个阻塞、补回归、重新 review-prepare，再从 Stage 1 派发独立新审查。此报告不得覆盖后续变化代码或用于批准新快照。
