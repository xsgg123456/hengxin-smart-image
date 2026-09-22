# 已有结果收取阻塞修复：独立审查

- 日期：2026-09-22。
- candidateId：`36e5f1b449395499b167ac8bdd1f62736aadcaa6351ad465523721d0949ccb86`。
- HEAD：`9c9655d53530d2dc4c88ce3e85532d7e1886c076`。
- 范围：`hengxin-smart-image/backend/app/modules/api_image_edits/claims.py` 与新增 `hengxin-smart-image/backend/tests/test_api_image_collection_block.py`；核对 Product-Spec.md:645、修复计划 docs/API-IMAGE-COLLECTION-FIX.md:6-8 及其状态机依赖。不是全产品重新验收，不包含生产部署验收。
- 使用 `.agents/skills/code-review/SKILL.md`；审查期间未修改业务代码。review-status 确认当前代码候选与主 Agent 提供编号一致。修复计划追加测试记录属于 Markdown 证据更新，不改变代码候选。

以下代码路径相对 `hengxin-smart-image/backend/`。

## Stage 1 — Spec Compliance：PASS

| 范围内要求 | 结论与证据 |
| --- | --- |
| 手动重试已有结果遇到其他待核实项仍能收图 | 完整实现。`claims.py:58-62` 在阻塞时只选有 URL 或字节的 collecting。`tests/test_api_image_collection_block.py:15-41` 通过实际 retry 路由、execute_next、下载回调、结果版本断言覆盖该路径；独立运行通过。旧实现 `git diff` 显示在任何 uncertain 时直接返回，无法到达该分支。 |
| 不自动重放待核实项，不调用生成 | 完整实现。`claims.py:60-61,77` 只领取已有结果且返回 collecting；`app/modules/api_image_edits/execution.py:102-130` collecting 跳过 generate 分支。新测试 :37-41、:61 断言 uncertain/queued 保留、生成次数为零且后续领取为空。 |
| 保留暂停和全局 10 租约上限 | 完整实现。`claims.py:50-55` 在安全收图筛选之前执行两项限制；测试 :64-83 验证暂停保护，:86-97 验证 12 项中只领取 10 个不同项。 |
| 无结果、有效租约、退避到期前不领取 | 完整实现。`claims.py:60-61,71-74`；测试 :64-83 覆盖无结果、有效及过期租约，:44-61 覆盖 next_attempt_at。 |
| 收图失败 1/2/4 秒退避后耗尽 | 完整实现。`app/modules/api_image_edits/outcomes.py:53-68` 保持既有逻辑；测试 :51-61 验证四次下载、三次退避、最终 failed 且生成零次。 |
| 成功保存版本且整单仍待核实 | 完整实现。`claims.py:79-81` 调用 refresh_task；`app/modules/api_image_edits/state.py:33-48` uncertain 优先；`execution.py:70-81` 保留租约校验与版本发布。测试 :37-40 验证成功版本和整单 uncertain。 |
| 发布范围、不自动确认第 11 张 | 代码范围符合。唯一生产代码差异为 claims.py；没有改管理员确认、前端、CLI、数据库结构或发布脚本。实际发布及生产图片验收由主 Agent 继续执行，不能由本报告推定完成（修复计划 :8）。 |

部分实现/未实现：在本次代码修复范围内未发现。Spec 漂移：未发现新增 API、表、UI 或生成行为。UI 一致性、引导真实性：本候选无 UI 变化，不适用；未执行页面视觉对比。

## Stage 2 — Code Quality：PASS

- 结构：`claims.py:33-84` 延续原有短事务领取逻辑；文件 108 行，新测试 97 行，均低于 300 行。命名和导入与现有代码一致，无新增 any 或外部依赖。
- 并发保护：`app/modules/api_image_edits/state.py:16-26` 通道行锁仍覆盖 `claims.py:37-83` 的查询、计数和领取写入；全局限制位于分支之前。新增顺序领取测试证明数量上限与唯一性，不冒充 PostgreSQL 多进程竞争验证。
- 测试真实性：`tests/files_helpers.py:65-88` 使用 FastAPI TestClient、SQLite 和 MemoryStore；新增用例确实经过路由、状态机、图像解码和结果版本保存，生成客户端是计数替身（`tests/test_api_image_execution.py:18-28`），下载也是替身。故可证明业务分支，不证明生产网络、MinIO、真实上游和 PostgreSQL 竞争行为。测试将“结果下载失败”及“租约到期”注入为可达状态，没有绕过待审 claim。
- 安全扫描：对两个变更 Python 文件搜索 eval、innerHTML、dangerouslySetInnerHTML、前端密钥变量、常见密钥前缀、密码赋值和用户绝对路径，无匹配。`claims.py:42-44` 继续使用 SQLAlchemy 表达式；新结果收取依然进入既有下载及解码链，不新增外部地址执行入口。
- HIGH/MEDIUM/LOW 问题：未发现需阻断本候选的问题。证据限制：本审查没有执行 PostgreSQL 竞争测试或生产收图；主 Agent 提供的全 API 65 passed/8 skipped 记录属于补充证据，本报告独立执行结果如下。

## 独立验证原始输出

工作目录：`hengxin-smart-image/backend`。

命令：`.venv/Scripts/python.exe -m pytest tests/test_api_image_collection_block.py tests/test_api_image_execution.py tests/test_api_image_parallel.py tests/test_api_image_revision_guards.py tests/test_api_image_revision_execution.py tests/test_api_image_versions.py -q`

```text
.............................                                            [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
29 passed, 2 warnings in 4.81s
```

命令：`.venv/Scripts/python.exe -m compileall -f app/modules/api_image_edits/claims.py tests/test_api_image_collection_block.py`，退出码 0。

```text
Compiling 'app/modules/api_image_edits/claims.py'...
Compiling 'tests/test_api_image_collection_block.py'...
```

两阶段 PASS 仅对应上述 candidateId；由主 Agent 使用 review-approve 登记同一候选，本报告不替代生产发布后验证。
