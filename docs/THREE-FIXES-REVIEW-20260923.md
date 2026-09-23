# 三项整改独立审查 · 2026-09-23

## 快照与范围

- 最终 candidateId：`7cfc8a61e40aa537a55de0bd8b2d69c54f3948b6ffe968b6e003bbe7a0cda08f`。
- 初始 candidateId：`87f6004fd7c627bbbcad8716b6fededdd4acf0cfbf851c6608555e3cb715347e`。审查期间主 Agent 修改 `hengxin-smart-image/backend/tests/test_cli_intervention_recovery.py:45`，增加退出凭据有/无两组断言；已重新读取差异并独立执行该文件。结论针对最终候选，不沿用旧快照批准。
- 范围：当前 Git diff 与新增文件中的 CLI 重连最终交付、显式失败补收、专用 Worker 排空重启与 needrestart 配置、API 五任务/五十图片调度，以及相关测试和已授权研发规则。依据 `Product-Spec.md:3`、`DEV-PLAN.md:3`、`docs/API-IMAGE-TASK-CONCURRENCY-20260923.md:3`。
- 方法：读取 code-review skill、源文档、全部相关实现与测试；独立运行专项测试及后端编译。仅创建本报告，没有修改业务代码、提交、登记批准或写 clean。

## Stage 1 · Spec Compliance：PASS

### 完整实现

以下代码路径中，`app/`、`tests/` 均相对于 `hengxin-smart-image/backend/`。

| Spec 条目 | 结论与证据 | 验证方式 |
|---|---|---|
| 仅豁免明确可恢复 WebSocket 重连 | 完整实现。`app/execution/events.py:9` 使用全字符串匹配并校验重试序号；`:85` 仅在完成前接受，未随后完成仍返回错误。`app/execution/final_delivery.py:73` 拒绝终止失败与其他错误。 | `tests/test_reconnect_delivery.py:25`、`:42` 覆盖成功、未完成、终止错误、配额错误、完成后错误、相似错误、会话错配与损坏事件；独立运行通过。 |
| 正常完成、exit 0、明确最终回复及有效产物共同成立 | 完整实现。正常执行 `app/execution/codex_runner.py:165` 检查退出及事件，`:176` 收图；`app/execution/final_delivery.py:88` 要求最终事件对，`:216` 校验图片数量、路径、内容与基线。 | `tests/test_final_delivery.py:44`、`:118`、`:142`、`:148`；`tests/test_final_delivery_roundtrip.py:71` 贯通整套/单张/返工。 |
| 恢复器不以文件存在代替成功退出证明 | 完整实现。`app/worker/reconcile.py:138` 验证 final-reply-v1，`:141` 要求严格整数 exit 0 且无 reason；无凭据保留 uncertain。旧协议分支保留原约定。 | `tests/test_execution_reconcile.py:241`、`:247`、`:254`；`tests/test_cli_intervention_recovery.py:45` 检查第二进程凭据、不重放与合并用量。 |
| 已失败当前轮显式补收，不调用模型 | 完整实现。`app/worker/repair_delivery.py:17` 仅接受指定 attempt；`:26` 校验当前轮、失败状态、claim、节点与取消/删除；`:33` 确认原进程停止；`:37` 校验控制目录；`:42` 校验退出；`:47` 校验会话；`:53` 拒绝已有发布；`:57` 验证最终文件后转 uncertain。函数无模型调用入口。 | `tests/test_repair_delivery.py:26` 实际 prepare→reconcile→发布，重复补收拒绝；`:42` 拒绝取消、仍运行、无退出凭据、非零退出及真实错误。 |
| 补收防重并保留失败审计 | 完整实现。`app/worker/repair_delivery.py:61` 保存 previousFailure/previousError/previousFinishedAt；`app/worker/reconcile.py:28` 复用锁与 CAS 轮换令牌，`:72` 成功后清除当前失败展示，保留 recollection。 | `tests/test_repair_delivery.py:26` 检查一份版本、成功状态与原始失败审计；`tests/test_execution_reconcile.py:138`、`:199` 检查重复恢复及陈旧扫描。 |
| needrestart 只排除专用 CLI Worker | 完整实现。`hengxin-smart-image/infra/needrestart/99-hengxin-worker.conf:2` 仅锚定 `hengxin-vps-codex-worker.service`，值为 0；未停用系统更新。 | 配置文本审查。线上安装与真实 needrestart 执行不在本次独立验证中。 |
| 停消费，Celery 与数据库都空闲才重启 | 完整实现。`app/worker/maintenance.py:28` 读取队列，`:38` 取消消费并要求确认，`:43` 检查已无消费队列，`:45` 检查 active/reserved/scheduled，`:22` 查询 running/collecting/cancelling/uncertain Job；全部空闲才调用 restart。 | `tests/test_worker_maintenance.py:28` 验证忙碌、DB 忙碌、检查失联、取消无确认均不重启；`:40` 验证空闲重启与重启异常恢复消费。 |
| 排空/重启异常恢复消费 | 完整实现。`app/worker/maintenance.py:37` 发送取消前记录队列，`:53` finally 重新添加消费；成功重启后依赖服务配置重新建立消费。 | 上述 maintenance 测试通过。实际 Redis/Celery/systemd 联动由发布步骤核验，本报告未声称线上重启成功。 |
| 全站最多五任务，第六排队，按创建顺序准入 | 完整实现。`app/modules/api_image_edits/claims.py:38` 持有通道行锁，`:42` 按任务 created_at/id 排序；`scheduling.py:14` 优先保留已准入任务，`:20` 填充剩余名额。 | `tests/test_api_image_task_slots.py:16`；真实隔离 PostgreSQL `tests/test_api_image_task_slots_pg.py:37` 竞争领取 70 次，只取得前五任务的 50 个唯一图片。 |
| 每任务十图并行、严格分批、全站最多五十图 | 完整实现。`app/modules/api_image_edits/scheduling.py:4` 定义 5/10；`:24` 限制各任务租约，`:28` 锁定当前批次；`claims.py:55` 总量限制 50；`execution.py:95` 每执行批次十线程。 | `tests/test_api_image_task_slots_pg.py:54` 五执行器实际 mock 调用峰值 50，第二批等待；`tests/test_api_image_parallel_pg.py:43`、`:63` 验证十图及第十一张边界。未调用收费模型。 |
| 退避、收图、批次切换保留名额，终态释放 | 完整实现。`app/modules/api_image_edits/state.py:33` 活跃项保留已运行任务状态，仅全部终态后结束；`scheduling.py:14` 按任务状态保留名额。 | `tests/test_api_image_task_slots.py:16` 检查退避不释放、确定失败释放；`:62` 检查成功释放和已删队列任务；`test_api_image_task_slots_pg.py:54` 检查第二批保留名额。 |
| 旧任务修改/重试重新排队，在途修改不另占名额 | 完整实现。`app/modules/api_image_edits/service.py:76` 失败重试置 queued；`versions.py:54` 只将终态任务重新置 queued；`state.py:39` 不以历史 started_at 冒充已准入。 | `tests/test_api_image_task_slots.py:37` 五任务满员时旧成功任务修改、失败任务重试均排队；`tests/test_api_image_parallel_pg.py:94` 验证在途追加修改不打断当前批次。 |
| 暂停、不确定阻断与安全收图保留 | 完整实现。`app/modules/api_image_edits/claims.py:50` 暂停时停止领取，`:57` 检测 uncertain；`scheduling.py:30` 阻断期间仅提供已有结果的 collecting 项，仍服从任务和图片容量。 | 静态逐分支核查；既有 `tests/test_api_image_collection_block.py:28`、`:64` 覆盖该合同，主 Agent 宽专项包含相关测试。本审查独立专项未重新执行此文件。 |
| 部署池五进程、CLI 调度不变 | 完整实现。`hengxin-smart-image/infra/compose.api-image.yaml:42` 设置 API Worker `--concurrency=5`；调度修改仅位于 api_image_edits。 | Git diff 与配置审查；生产进程池需发布后检查。 |
| 四条已授权研发规则 | 完整实现。`AGENTS.md:36` 明确授权实查；`:96`、`:109`、`:173` 归并进化生命周期；`.agents/skills/dev-builder/SKILL.md:56` 明确终态联合判据；`.agents/skills/release-builder/SKILL.md:26` 明确在途排空。 | 对照派发授权与规则 diff，没有新增未授权业务。 |

### 部分实现、未实现、Spec 漂移、UI

- 本次代码范围没有部分实现或未实现条目；部署、两筆历史生产补收属于主 Agent 后续发布验收，尚不据本报告认定完成（`DEV-PLAN.md:8`）。
- 未发现新增页面、API、表或未授权功能；新增内部工具对应三项整改（`app/worker/repair_delivery.py:17`、`app/worker/maintenance.py:59`）。性能扩展和恢复轮自动干预不在 diff 中。
- UI 一致性、文案引导、邻居页面视觉对比不适用：本候选无前端或设计稿变更，范围文件为上述后端、配置及研发规则；未伪造截图或视觉验收。

## Stage 2 · Code Quality：PASS

- 命名与结构：新增调度集中于 `app/modules/api_image_edits/scheduling.py:1`；排空与补收分别集中于 `app/worker/maintenance.py:1`、`repair_delivery.py:1`，职责分离。11 个变更业务 Python 文件为 35–253 行，均未超过 skill 的 300 行限制；最长为 `app/execution/final_delivery.py:253`。无新增 Any 类型。
- 错误与并发：`app/modules/api_image_edits/state.py:17` 通道锁覆盖调度与现有变更入口；`app/worker/reconcile.py:45` CAS 防重复发布；`maintenance.py:15` 检查失联拒绝重启。未发现 HIGH/MEDIUM 质量问题。
- 测试真实性：`tests/test_api_image_task_slots_pg.py:54` 使用 Barrier(50) 和实际数据库事务，断言网络替身峰值及数据库状态，非仅计算常量；`tests/test_repair_delivery.py:26` 走真实发布链；`tests/test_cli_intervention_recovery.py:45` 新断言确实区分退出证据。维护测试使用控制端替身，不能代替线上服务验收。
- 安全扫描：新增与变更实现未发现硬编码密钥、eval、动态 shell 或拼接 SQL。`app/worker/maintenance.py:73` 使用固定参数列表调用 systemctl；`:12` 固定目标服务。`repair_delivery.py:37` 保留根目录与链接边界；`final_delivery.py:216` 保留文件校验。未新增对外补收接口。
- 视觉对比：不适用，理由见 Stage 1；没有声称已打开页面。

## 独立验证原始输出

执行目录：`hengxin-smart-image/backend`；解释器：`.venv/Scripts/python.exe`。PostgreSQL 使用主 Agent 提供的本地隔离库，fixture 每例创建随机 schema 并回收。首次沙箱内运行因底层 Python 不可访问失败，升级后成功运行。

专项命令：

```text
python -m pytest -q tests/test_reconnect_delivery.py tests/test_final_delivery.py tests/test_final_delivery_roundtrip.py tests/test_execution_reconcile.py tests/test_repair_delivery.py tests/test_worker_maintenance.py tests/test_api_image_task_slots.py tests/test_api_image_task_slots_pg.py tests/test_api_image_parallel_pg.py tests/test_cli_intervention_recovery.py
```

原始终端输出摘录（省略进度点）：

```text
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
126 passed, 1 skipped, 2 warnings in 29.19s
```

说明：唯一 skip 对应 Windows 主机不可建立符号链接的 `tests/test_final_delivery.py:254`。两个 warning 来自现有依赖，不是测试失败。

编译命令及原始输出（退出码 0）：

```text
python -m compileall -q app
compileall exit=0
```

## 交接

两阶段 PASS 仅覆盖指定最终候选的代码与配置；不代表生产部署、真实收费生成或线上两笔补收完成。主 Agent 按 `docs/HARNESS-REVIEW.md:9` 对同一 candidateId 登记本报告，再执行剩余发布验证。发生任何受控文件变化应重新固定快照并复核差异。
