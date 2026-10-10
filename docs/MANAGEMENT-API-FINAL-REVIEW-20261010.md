# 管理中心 API 实际业务统计：独立审查

- candidateId：`6c82fdf12215faebab2237b229b400b768f05a6bcfffb091d0f1d7b72e3467d3`
- 审查日期：2026-10-10。
- Stage 1：**FAIL**（1 HIGH、1 MEDIUM）。
- Stage 2：**未执行**；按 code-review skill，Stage 1 有 HIGH 时停止，不登记两阶段 PASS。
- 范围：`docs/MANAGEMENT-API-IMPLEMENTATION-20261010.md` 全部统一实施口径及交付要求；对应已修改/未跟踪的 API 事实、采集、聚合、监控、配置、迁移、前端真实管理页及隔离预览。参考验证材料：`docs/MANAGEMENT-API-VALIDATION-20261010.md`。
- 排除：预存已审的 `.agents/skills/dev-builder/SKILL.md` 改动；已完成的 `872b9a6` 自动清理功能本体。仅核查本轮新增清理前事实保全。
- 审查初始及报告完成后 `review-status` 的 currentId 均与上述 candidateId 一致，审查期间没有代码快照变化。没有修改业务代码、提交、执行生产写入或调用收费模型。

## 阻断项

### HIGH-1：来源无法证明的历史正式版本，被确定地计入“正式生成版本”

需求原文：历史生成正式版本、CLI 候选、手动采用、恢复版本分别计数；历史 kind 无法证明时为 legacy_unknown；缺失历史不造数。

证据链（路径均相对仓库根目录）：

1. `hengxin-smart-image/backend/app/modules/management/api_stats/projection.py:47` 根据尚存 turn 或持久 adopt key 识别采用；`:53` 对其余所有版本生成 `version_published`，其中空 kind / image_edit 会成为 `channel=unknown, kind=legacy_unknown`。
2. `hengxin-smart-image/backend/app/modules/management/api_usage_summary.py:13` 把全部 `version_published` 无条件加到 `generatedVersions`；未使用上述未知标识限制计数。
3. `hengxin-smart-image/frontend/src/views/hengxin/admin/ApiUsage.vue:21`、`:26`、`:58` 以“正式生成版本”在说明、日报和 KPI 展示此计数；`frontend/src/api/api-management-usage-validate.ts:9` 也将事件确定命名为正式生成版本。

可达场景：历史 `ApiVersion.kind=image_edit` 存在，但 CLI turn / adopt 证据已缺失。版本存在只证明已发布正式版本，不能证明它属于 API 生成还是 CLI 手动采用。当前实现虽然在明细标注未知渠道，却在汇总中确定归入生成，违反独立口径。空 kind 同理。

独立最小复现直接调用真实 `historical_facts()` 和 `summarize()`，提供一个历史 image_edit 版本、无 turn / adopt key；只替代只读查询返回值，没有改库。原始输出：

```text
[('task_created', 'api', 'task_created'), ('version_published', 'unknown', 'legacy_unknown')]
{'generatedVersions': 1, 'adoptions': 0}
```

修复验收：保留源键幂等，只有可证明生成的版本进入 generatedVersions；未知来源正式版本单列且 UI 明示。分类不得依靠猜测补为采用。覆盖空 kind、image_edit、已知生成、已知采用及回填/清理前后不重复、不缩水。若沿用 version_published 事件类别，事件标签应描述“正式版本发布记录”，不能直接等同生成。

### MEDIUM-1：持久事实覆盖历史投影后，部分 CLI 明细状态永久过期

证据：

- `backend/app/modules/management/api_stats/projection.py:67` 无条件以 durable 整行覆盖实时历史投影。
- `backend/app/modules/management/api_stats/backfill.py:12` 只执行不覆盖已有键的 put。
- `backend/app/modules/management/api_stats/facts.py:70` 的 record_turn 更新 cli_round，但没有更新 cli_submission。
- `backend/app/modules/api_image_edits/conversation.py:200` 采用后将 turn.status 改为 adopted，随后仅 emit/touch/commit，没有调用 record_turn，因此真实启动事实仍保留 candidate。
- `backend/app/modules/management/api_stats/projection.py:26` 历史 cli_submission 的 state 来自 turn.status；若运行期间回填，提交事实被固化为 queued/running，后续 finish 不刷新此类事实。
- `frontend/src/views/hengxin/admin/ApiUsageDetail.vue:12` 直接展示上述事实 state，所以会出现已采用轮次仍显示“已产出候选”、历史已结束提交仍显示“进行中”。当前总成功数不会因此改变，但明细状态不匹配真实业务。

修复验收：明确提交事件状态是“提交已接受”还是轮次当前状态并统一新旧记录；可变 state/completed_at 应刷新而不重写 occurred_at、操作者和已核实归属。增加“真实启动→候选→采用”及“运行中回填→结束→再次回填”的断言。仅刷新上述允许变化字段，避免把历史未核实数据升级为 verified。

## Stage 1 逐条对照

以下 backend/frontend 路径前缀为 `hengxin-smart-image/`。通过项表示该条代码和所列证据匹配；不代表整体候选通过。

| 源要求 | 结论 | 证据 |
|---|---|---|
| 统计使用 API 业务，兼容旧接口 | 完整实现 | `backend/app/main.py:50` 同时注册新旧 router；`backend/app/modules/management/api_usage.py:69` 读取 API 事实，`:39` 库存只读 ApiTask/ApiItem；`frontend/src/api/api-management-usage.ts:9` 请求新路径。 |
| 任务/请求/CLI/候选/版本/采用分别按发生时间归北京时间自然日 | 部分实现 | `backend/app/modules/management/api_stats/facts.py:42`、`:47`、`:64`、`:70`、`:89` 分事件采集；`backend/app/modules/management/api_usage.py:90` 上海日期归组；已有跨午夜测试通过。未知版本归类不符合，见 HIGH-1。 |
| 库存只按创建人、不受日期和类型影响，并显著说明 | 完整实现 | `backend/app/modules/management/api_usage.py:39`、`:108` 独立库存查询；`frontend/src/views/hengxin/admin/ApiUsage.vue:19` 显著说明。相关筛选/分页测试通过。 |
| API 尝试含失败重试，预检不计；CLI 提交与真实启动分开 | 完整实现 | `backend/app/modules/api_image_edits/claims.py:110` start_attempt 写事实；`conversation.py:139` 写 submission；`conversation_runner.py:145` 进程 started 回调写 round；`api_stats/projection.py:28` 历史证据不足 quantity=0。真实业务测试覆盖 spawn 失败和回填后启动升级。 |
| CLI 澄清不算失败、候选不等于采用 | 完整实现 | `backend/app/modules/management/api_usage_summary.py:5` waiting_user 纳入 CLI 成功；`conversation.py:195` 用户采用独立事实。`:200` 后明细状态刷新有 MEDIUM-1，不改变独立采用数量。 |
| 请求成功率排除未知/在途；当前交付按最新图片状态；旧结果另列 | 完整实现 | `backend/app/modules/management/api_usage_summary.py:25`、`:48`；`api_usage.py:46`；`frontend/src/views/hengxin/admin/ApiUsage.vue:19`、`:20`。独立测试验证 3 次请求中成功/失败/未知各 1 时成功率 0.5，当前修改失败保留旧结果仍单列。 |
| 正式生成、候选、手动采用、恢复独立；Token/费用无证据不估算 | 部分实现 | 恢复在 `backend/app/modules/api_image_edits/versions.py:185` 独立写事实；`backend/app/contracts/api_usage.py:44` Token/费用默认 None；未知版本计数有 HIGH-1。 |
| 重试冻结真实操作者、不改历史；历史归属/类型未知不猜 | 部分实现 | `backend/app/modules/api_image_edits/service.py:76`、`versions.py:158` 冻结；`claims.py:111` 采用冻结操作者；`api_stats/facts.py:50` 保留原事实归属。跨人员真实重试测试通过；未知类型有标记但生成汇总仍有 HIGH-1。 |
| 事实同事务、键幂等、无过程外键/正文；GET 不写；清理前保全 | 部分实现 | `backend/app/modules/management/api_stats/models.py:10` 无 FK/正文；`facts.py:24` conflict handling；`projection.py:63` no_autoflush；`backend/app/retention/api.py:55` 清理前 preserve。测试证明 GET 仅 SELECT、重复回填 0 新增、清理后事实一致；可变状态覆盖存在 MEDIUM-1。 |
| API/CLI 真实独立心跳，过期未知；业务队列与服务健康分开 | 完整实现 | `backend/app/modules/api_image_edits/worker_health.py:25` 检查 API app identity，`:35` 独立 pulse；`management/api_monitor.py:26` 分模型读取，`:132` 采集失败使用 None；`frontend/src/views/hengxin/admin/monitor.vue:8`、`:19`、`:20` 分别提示心跳/容量/跨阶段不能相加。缺失/过期/未来心跳、独立心跳、队列失败测试通过。 |
| 配置来自实际配置/常量，API 只读、CLI 可保存；保留 Skill/钉钉/审计 | 完整实现 | `backend/app/modules/management/execution_settings.py:17` 从配置及常量读取；`settings_router.py:12`、`:22` 保留 manage_system 保存校验；`frontend/src/views/hengxin/admin/settings.vue:12`、`:14`、`:17`、`:19` 表单/审计保留，`:40` 保存后刷新配置卡片。配置权限及实际值测试通过。 |
| 清理策略只读且不宣称服务在线 | 完整实现 | `backend/app/modules/management/execution_settings.py:10`、`:27` 引用 CACHE_AGE/HISTORY_AGE 和开关；`frontend/src/views/hengxin/admin/ExecutionSettingsCards.vue` 只读卡片，无写入清理操作；本次 23 项中的配置测试断言 1/7 天与开关。 |
| 普通角色无管理入口、个人统计后端受限；新详情跳转、删除不误跳 | 完整实现 | `frontend/src/router/modules/index.ts:3`、`:32` 父路由角色；`backend/app/modules/management/api_usage.py:75`、`:82` 个人范围与未知操作者校验；`frontend/src/views/hengxin/admin/ApiUsageDetail.vue:8`、`:38` 删除无按钮、正常跳 API 详情。权限及软删除测试通过。 |
| 正式页面无模拟回退，加载/空态/错误/分页 | 完整实现 | `frontend/src/router/management-preview.ts:6` 仅 mock 模式且显式查询参数启用预览；`admin/usage.vue:5` 非 mock 加载真实 ApiUsage；`ApiUsage.vue:15`、`:16`、`:30` 加载/错误/分页；请求失败无伪造报告回退。查看 `output/playwright/management-real/usage-execution.png`，230 次请求/220 成功/10 未知及 100% 已知成功率与口径匹配。 |

未发现本轮额外未声明页面、计费或生产开关写入功能；预览功能受显式 mock 条件限制。普通用户/角色/Skill 的旧业务实现未扩大审查。

## 验证与编译原始证据

独立复跑命令（本地虚拟环境，隔离测试 fixture）：

```text
python -m pytest -q tests/test_api_usage_facts.py tests/test_management_api_usage.py tests/test_management_api_monitor_settings.py --disable-warnings -p no:cacheprovider
.......................                                                  [100%]
23 passed, 2 warnings in 3.94s
```

下列为实际读取的主 Agent 已提供日志原文，并非本 reviewer 重跑全套；通过不能覆盖 HIGH-1/MEDIUM-1 未被断言的情况。

`output/playwright/management-real/backend-tests.log`：

```text
..                                                                       [100%]
1641 passed, 17 skipped, 15 warnings in 280.97s (0:04:40)
```

`output/playwright/management-real/frontend-tests.log`：

```text
ℹ pass 236
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 4612.0608
```

`output/playwright/management-real/typecheck.log`：

```text
> hengxin-smart-image-frontend@0.2.19 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

`output/playwright/management-real/build.log`：

```text
✓ built in 47.34s
```

独立审查未重做 PG 全链迁移/四线程回填，也未将验证文档中的陈述当作此次亲测。17 skipped 不算验证通过。

## 后续

按 Stage 1 失败回实现阶段，修复两个问题及回归后重新 review-prepare，向 fresh reviewer 交付新 candidateId。当前报告不授权 review-approve；Stage 2 的质量、安全扫描、邻居页面实际视觉对照均未执行。
