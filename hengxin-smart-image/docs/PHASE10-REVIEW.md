# Phase 10 独立审查报告

- 初始 candidateId：`68c164c270b4f29c6abccd46150ff0c4370014e592e3a345ac987cf0a8e1c62f`。
- 范围：Phase10 返工 API、任务资格与结果发布、CLI 材料/部分结果收集、Worker 分流、前端返工状态与详情、对应测试及验收脚本。Phase9 已批准基线作为前置，不将全部工作区 diff 当作本期新增。
- 依据：Product-Spec REQ-005、9.1–9.2、AC-006/007/010/015/016/021；DEV-PLAN Phase10；Design-Brief；docs/PHASE10-PLAN.md。
- 结论：**Stage 1 FAIL；Stage 2 未执行。禁止据此批准快照。**

## Stage 1：Spec Compliance

### HIGH：不完整整套会被误标为待查看

Spec 要求“部分失败可预览已成功图片”（DEV-PLAN.md:322），且不得把残缺结果标为完整套图（Product-Spec.md:134）。初次生成部分失败后，用户只返工其中一个位置：`backend/app/modules/tasks/results.py:16` 仅选择本轮 targets，`:35` 按这些 targets 全成功结束本轮；`backend/app/modules/tasks/queries.py:45` 则仅以当前轮次状态生成整个任务的 state/progress。当另一位置仍缺失结果或保留失败标记时，任务被返回“待查看”和 100%。列表统计同样在 `queries.py:92` 只判断当前轮次 succeeded。此问题由主 Agent 在审查期间提出，reviewer 独立对照代码确认。

修复验收：保持单轮状态含义，任务状态汇总全部 slot；初次 partial 后单图成功、其他位置仍缺图/有 error 时，任务仍为部分失败。列表筛选、ready 统计、详情一致；补可达生产输入的回归测试。修改后重新 review-prepare 并从 Stage 1 复核。

### 已核对实现

| 条目 | 代码证据与验证 |
|---|---|
| REQ-005 / AC-006 整套、单图意见及历史 | `frontend/src/views/hengxin/components/TaskDetail.vue:8`、`:21`、`:22`、`:90`；`backend/app/modules/tasks/queries.py:66` 输出版本与操作者历史。真实浏览器验收尚未完成，视觉不标通过。 |
| 指定 Skill、素材、范围、当前图输入 | `backend/app/execution/materials.py:23` 冻结素材与目标；`:44` 添加 currentPath/currentVersion；`:59` 校验原 Skill checksum；`workspace.py:72` 输入当前图与本轮意见。独立 `test_revision_execution.py` 通过。 |
| AC-007 单slot及失败保旧版本 | `backend/app/modules/tasks/results.py:16` 仅处理目标；`:20` 的 None 保留 currentVersion；`:32` 成功才切换。`test_revisions.py:42`、`test_partial_results.py:49` 覆盖旧版本。整套聚合仍有上述 HIGH。 |
| AC-010 重放及异内容冲突 | `backend/app/modules/tasks/service.py:72` 先 authorize，再 replay；任务行锁后再次 replay；请求、轮次、Outbox 同事务。`test_revisions.py:42` 和 PostgreSQL HTTP 并发测试覆盖。 |
| AC-021 跨用户互斥及真实操作者 | `backend/app/modules/revisions/service.py:13` 拒绝全部 ACTIVE；`tasks/service.py:82` 按任务加锁，不按用户分锁；`:27` 保存 operator_id。四角色及禁用身份回放测试独立通过。 |
| 失败重试范围与安全首次初始化 | `tasks/service.py:94` 验证当前失败轮次 sourceRoundId、note、target；`revisions/service.py:9` 要求所有历史尝试 finished 且无 PID；`execution/codex_runner.py:88` 对缺失会话 ID 再次校验。独立回归通过。 |
| 9.1 / AC-015 同会话 | `execution/codex_runner.py:113` 拒绝原材料缺失；`:133` 指定原 ID resume；`:44` 拒绝完成事件替换已有 ID。受控 CLI 回归验证续接参数和材料；真实 Skill 效果按 Phase14 验收，不宣称已完成。 |
| 9.2 失效执行不能发布 | `tasks/results.py:12` 复用 locked_execution/valid；`tasks/claims.py:73` 校验删除、当前轮次、取消、token、租约。部分失败沿用同一道发布屏障。 |
| partial 固定位置及原生结果来源 | `execution/output_collector.py:82` 验证完整slot清单、file/error互斥；`:130` 拒绝未映射额外图片；`codex_runner.py:145` 对所有成功图继续 verify_provenance；`worker/reconcile.py:130` 同样收集 partial。 |
| AC-016 异步受理、离页继续 | `modules/revisions/router.py:11` 返回202；`tasks/service.py:112` 持久化轮次及待发消息。真实集成已看到单slot及整套执行完成，但最终全脚本尚待修后重跑。 |
| 草稿、不确定重放、401身份边界 | `frontend/src/views/hengxin/revision-session.ts:12` 按身份和任务存内存会话；`:43` 捕获原session；`:46` 拒绝unknown期间换内容；`:67` 重放原快照；`TaskDetail.vue:82` 防止迟到回执污染新身份/任务。本轮前端独立重跑受环境问题影响，不能仅凭测试文件声明验证通过。 |
| 202 后详情失败不再POST | `revision-session.ts:44` 返回缓存回执；`:30` 必须 observe 结束后显式 begin 才清除回执；`TaskDetail.vue:86` 将详情刷新留给 load。 |
| 不新增审批、四角色共享 | `modules/revisions/router.py:12` SharedUser；`tasks/service.py:74` authorize；`backend/tests/test_revisions.py:112` 覆盖全部四角色跨owner返工与操作者记录。 |

### 审查期间快照变化

1. `scripts/phase10/revisions.js:45`：模拟409从 detail 改为标准 code/message；已读取并确认符合真实 HTTP 错误契约。
2. `scripts/phase10/revision_checks.py:93`：Outbox连接从不存在的 o.job_id 改为实际 o.id；已读取修正。原集成输出确实报列不存在，不能视为先前已通过。
3. 主 Agent 通知将修任务聚合逻辑；该代码变化不属于上述 candidate 的有效旧结论。新快照须重新审查。

## 验证原始输出与边界

Reviewer 独立执行 backend 的 test_revisions.py、test_revision_execution.py（指定 output/phase10-review-tests 与 no:cacheprovider），退出码0：

```text
...................................                                      [100%]
35 passed, 6 warnings in 5.95s
```

警告为 FastAPI/httpx 弃用、AnyIO别名弃用以及匿名身份测试产生的 SQLAlchemy NULL 主键警告。Linux全套日志曾读取到 `286 passed, 6 warnings in 17.55s`；整套最终集成随后在错误验收SQL处中止，主 Agent 正重跑。该日志后来覆盖，不用旧成功片段冒充新快照验收完成。

Reviewer 尝试独立前端测试时的原始环境错误：

```text
SystemError [ERR_SYSTEM_ERROR]: A system error occurred: uv_os_get_passwd returned ENOMEM (not enough memory)
Node.js v24.18.1
```

编译完整原始日志及最终真实浏览器截图尚未取得，不给编译或视觉 PASS。由于 Stage1 HIGH，Stage2 代码质量、安全与视觉最终审查不执行；修复由主 Agent 处理，本报告未修改业务代码、未登记批准凭据。
