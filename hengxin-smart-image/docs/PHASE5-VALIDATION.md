# Phase 5 验证记录

2026-09-09；范围：DEV-PLAN Phase 5 后端基础、契约和通用队列。真实业务/AI 接入未验收，前端仍用显式 mock 预览。

## 构建与环境

- `docker compose --env-file hengxin-smart-image/infra/.env -f hengxin-smart-image/infra/compose.yaml build api`：exit 0，首次干净容器内 `uv sync --locked --no-install-project`，55 项锁记录，安装 53 包（平台条件差异）。最终镜像基于固定 Python/uv digest。
- PostgreSQL `16.15`，MinIO `RELEASE.2025-09-07T16-13-09Z`：本机缓存镜像实际版本命令核实；Compose 固定全部第三方镜像 digest。
- 本机 API 已启动，GET `http://127.0.0.1:8008/api/v1/health/ready` → 200 `{"status":"ready","checks":{"postgresql":"up","redis":"up","minio":"up"}}`。
- Windows 55433 被系统保留，本机 `.env` 使用 55431；未修改系统端口保留，不终止其他进程。

## 真实故障与契约测试

执行 `python hengxin-smart-image/infra/verify_phase5.py`（第三轮：修正错误响应契约后重新构建并完整重跑），exit 0，输出：

```text
PASS PG/Redis/MinIO ready
PASS repeat migration
PASS accepted job survives API/outbox restart without Worker
PASS real Celery execution
PASS duplicate messages preserve single completion
PASS Redis outage durable recovery
PASS Worker received delayed job
PASS Worker crash rollback and recovery
16 passed, 2 warnings in 2.47s
PASS only three isolated test volumes mounted
PHASE5 INTEGRATION PASS
```

上述 16 项包含：统一错误及请求标识、生产禁止测试入口、默认关闭、就绪故障、Worker guard、OpenAPI 方法/分页/字段与 TS 对齐、可省略与 nullable 区分、默认 Skill 三个键、PG 并发幂等、同键异载荷冲突、发布失败回滚/丢消息重派、并发重复消费与计算失败回滚。真实容器额外执行 Redis 停机及 Worker SIGKILL。测试项目使用随机 `hx-phase5-test-*`，仅 3 个测试卷，结束执行该项目 `down --volumes`；开发库无测试作业。

上游 Starlette/httpx、anyio 存在 2 项弃用警告，当前没有测试失败。首次审查指出 optional/null 与 Record 键约束差异后已修复，新增测试能复现旧错误。

## 前端回归

- `npx --yes pnpm@10.33.4 test`：最终代码版本再次执行，37 tests，37 pass，0 fail，0 skipped（1553.7707ms）。
- `npx --yes pnpm@10.33.4 build`：最终代码版本再次执行，exit 0，vue-tsc 零错误，Vite `built in 31.99s`；既有分包提示保留，无前端业务改动。
- 独立 Playwright 会话 `hx-phase5`：`scripts/phase3/create-flow.js` PASS，三入口创建/SKU 检索/壁纸商品 8 张文字 2 张/整套返工，pageerror=0。
- `scripts/phase3/version-flow.js` PASS，单图失败保留旧结果/重试原位置/其余 7 槽不变/历史版本查看下载/ZIP/归档幂等/删除确认/旧新归档保留，pageerror=0。
- 原型 `http://127.0.0.1:3007` HTTP 200，正式前端预览 3008 可访问。独立浏览器会话收尾关闭。

独立 fresh code-reviewer 最终结论：Stage 1 PASS、Stage 2 PASS，见 PHASE5-REVIEW.md。旧三项契约差异均复核关闭，独立 HTTP/OpenAPI/安全扫描与两页视觉抽查通过；浏览器标签已关闭。Phase 5 开发与技术验证完成，待用户验收后进入 Phase 6。
