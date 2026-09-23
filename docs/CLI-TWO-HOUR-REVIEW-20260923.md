# CLI 两小时额度独立审查

- 日期：2026-09-23；基线：`627588d`。
- candidateId：`0d022306567a537d110c03e55298f2785d7890aa6f6c340d5537b5d56387549a`。
- 范围：相对基线的 10 个代码、测试和部署配置文件，以及 Product-Spec、变更记录和 DEV-PLAN 的本轮增补；不重审此前全部产品功能。
- 使用 `.agents/skills/code-review/SKILL.md`。独立复验后 `review-status` 的 currentId 仍与候选一致，审查期间未发现受控代码变化。批准登记由主 Agent 执行。
- **Stage 1：PASS；Stage 2：PASS（仅当前实现快照）。生产切换及生产最终值尚待主 Agent 发布验收，本报告不表示已上线。**

以下代码路径均相对于 `hengxin-smart-image/`。

## Stage 1：逐条 Spec 对照

依据根目录 `Product-Spec.md:3`、`DEV-PLAN.md:3`。

| 要求 | 结论和证据 |
|---|---|
| 生产 CLI 整轮 7200 秒 | 完整实现配置支持：`backend/app/core/config.py:21` 上限 7200；`infra/compose.yaml:23`、`infra/.env.vps.example:24` 生产默认 7200。Python 本地默认仍为 3600，符合本轮交接约定。 |
| 首次与最多一次干预共享额度 | 完整实现：`backend/app/execution/codex_runner.py:110` 读取冻结值，`:140` 建立 deadline，`:142` 限两次调用，`:155` 第二次只获剩余额度；`backend/tests/test_cli_intervention_recovery.py:125` 实测参数 7200 的两次预算为 7200、7080。 |
| 队列可见性 7800 秒 | 完整实现：`infra/compose.yaml:32`、`infra/.env.vps.example:25`；`backend/app/core/config.py:61` 保留 600 秒裕量约束；`backend/tests/test_codex_runner.py:188` 接受 7200/7800，拒绝 7200/7799 和超上限 7201。 |
| 管理保存、返回容量、前端校验同步 | 完整实现：`backend/app/contracts/management.py:213`、`backend/app/modules/management/settings.py:46`、`frontend/src/api/hengxin/validate-management.ts:43` 均支持 7200；保存仍受部署实际容量约束（settings.py:102）。 |
| 新轮冻结新值，已提交/运行轮保持旧值 | 完整实现：`backend/app/modules/tasks/service.py:31` 按入队时配置冻结；执行器读取 round 配置而非当前环境。`backend/tests/test_management_settings.py:48` 通过真实提交/保存接口验证旧轮 3600、新轮 7200，7201 返回 422。未新增历史轮写入操作。 |
| 失败轮不自动重跑 | 符合：`backend/app/modules/tasks/claims.py:59` 仅 queued 轮可认领；本轮无任务状态迁移或失败重排操作；`backend/tests/test_cli_intervention_recovery.py:18` 覆盖手动重试/单张/整套返工不额外自动干预。 |
| 生产管理生效值为 7200 | 代码支持：`backend/app/modules/management/settings.py:20` 无数据库 timeoutSeconds 覆盖时使用环境值；主 Agent 提供的生产数据库只保存 concurrency，故无需改库。实际生产值须在切换后实查，本审查未直接连接生产。 |
| 排空后切换，不中断在途 | 发布验收项：`DEV-PLAN.md:6` 要求排空。主 Agent 正在处理在途任务，本报告不将待执行发布步骤判为已验证。应同步更新 API、原生 CLI Worker 及 CLI outbox 的代码与 7200/7800 环境；旧 outbox schema 无法接收 7200。 |
| API 换图请求超时及并发保留 | 符合当前差异：未改 API 换图模块或其专用环境；`backend/app/modules/api_image_edits/config.py:16` 使用独立 API_IMAGE_ 前缀，`:20` 请求时限独立。生产发布仍需确认专用 Worker 环境无变化。 |

UI 引导：`frontend/src/views/hengxin/admin/settings.vue:10` 输入上限、`:12` 提示文案均随 timeoutCapacity 动态变化，不存在固定 3600 的死引导；`settings-editor.ts:53` 保存范围随容量变化。无新增页面、组件、接口或表，无 Spec 漂移。无部分实现或未实现的代码要求。

## Stage 2：质量、安全和测试真实性

- PASS：增量为有界整数契约与配置上限调整，沿用既有配置源；未新增 any、复制业务逻辑或吞错。8 个变更 Python/TypeScript 文件均少于 300 行，最大 `frontend/tests/settings-monitor.test.ts:1` 为 276 行。
- PASS：新增测试通过真实 Settings 构造、管理 HTTP 接口、RoundRecord 持久化和模拟 CLI 调用预算验证行为；不是只断言常量。续跑测试模拟 monotonic 经过 120 秒，两个参数覆盖旧/新额度。未实际执行耗时两小时的收费模型任务，不能据此承诺生成效果或生产端到端耗时。
- PASS：增量安全扫描未发现 eval、innerHTML、dangerouslySetInnerHTML、前端暴露密钥或硬编码真实凭据；代码差异未增加 SQL、命令拼接、权限入口。`infra/.env.vps.example:24` 的增量只有两个数值。
- 视觉比较不适用：本轮前端唯一业务差异是 guard 上限（`frontend/src/api/hengxin/validate-management.ts:43`），没有模板、样式、布局及组件改动，没有新页面可与邻居页面比较；未把静态代码检查写作实际浏览器视觉验证。
- LOW 非阻断：`Product-Spec-CHANGELOG.md:417` 多一个文件尾空行，`git diff --check` 报告 `new blank line at EOF`。无业务影响。

## 独立执行的验证原始输出

后端命令（backend 目录）：

```text
.\.venv\Scripts\python.exe -m pytest tests/test_management_settings.py tests/test_codex_runner.py tests/test_cli_intervention.py tests/test_cli_intervention_recovery.py -q
..............................................................           [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa
.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
62 passed, 2 warnings in 12.13s
```

编译：

```text
.\.venv\Scripts\python.exe -m compileall -q app
stdout: （空）
stderr: （空）
exit_code: 0
```

前端命令及原始汇总：

```text
node node_modules/tsx/dist/cli.mjs --test tests/settings-monitor.test.ts
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 483.2493
```

沙箱首次无法创建 Python 进程，Node 首次报 `uv_os_get_passwd returned ENOMEM`；经审批在本机正常环境执行获得上述结果，未将环境错误判为产品缺陷。前端类型检查及生产构建由主 Agent 执行，报告未独立重复构建。主 Agent 后续提供：生产构建 exit0、50.48s，新镜像构建完成，服务端隔离安装产物专项 62 passed、20.31s；这些为交接结果，最终发布记录应附原始输出。
