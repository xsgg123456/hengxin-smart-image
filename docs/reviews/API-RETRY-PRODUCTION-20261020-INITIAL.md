# 国内 API 重试生产候选独立审查（第一轮）

- 送审 candidateId：`856a4be55eb87ca5658e5ddc4e24508094be61d6589a3e77ee9316c5cb7af204`。
- 分支：`codex/api-image-retry-protection`；基线：`3a33cebc`。
- 范围：本轮 API 生图后端、0031 迁移、相关新旧测试、前端重试状态/停止入口及 0.2.44、基础配置、API 重试发布/打包入口与浏览器验收脚本；普通文档为需求/证据输入。
- 依据：`Product-Spec.md:1`、`DEV-PLAN.md:1`、`docs/API-RETRY-PLAN-20261020.md:5`、`docs/API-RETRY-RELEASE-NOTES-20261020.md:15`；使用 `.agents/skills/code-review/SKILL.md`。
- 结论：**Stage 1 FAIL；Stage 2 未执行**。不得用本报告登记两阶段 PASS。
- 审查期间工作区已变化：最后只读 `review-status` 返回 `currentId=25335765a3d898c43e9359fcdc03c985da8bf0776c5836e980c7cb78656726ec`，不等于送审候选。主 Agent 已安排修复四项回归测试；本报告保留原候选问题，不将未复核修改当作已通过。

## Stage 1 问题

### HIGH · 原候选不能完成合同要求的全量回归和发布安装验证

合同要求：`docs/API-RETRY-PLAN-20261020.md:33` 明确后端相关及全量回归、真实产物验证。原候选的全量日志实际为 12 failed / 2018 passed / 281 skipped，不能声明验收完成。前三项失败来自本轮策略变化而旧测试仍使用旧前提：

1. `hengxin-smart-image/backend/tests/test_api_task_deletion_recovery.py:24` 将 uncertain 与 retryable 同分支，要求到期后自动再次执行，与“未知调用不得盲重试”冲突；原始失败位于该文件第 27 行。
2. `hengxin-smart-image/backend/tests/test_api_usage_facts.py:34` 用四次临时失败构造终态，第 44 行要求人工新轮成功；新合同每轮 20 次，此时返回 409 符合运行时合同，但测试未更新。
3. `hengxin-smart-image/backend/tests/test_capacity_admission.py:108` 只领取预处理 lease、未领取发送许可就模拟过期，第 111 行要求不可再 claim；新实现区分未发送和已发送，测试需真实进入发送后再证明未知所有权/容量不释放。
4. `hengxin-smart-image/backend/tests/test_domestic_retirement.py:89` 在旧 schema 0030 的保留验收中用新 ORM 插入含 `last_send_at` 的行，触发 UndefinedColumn。应保留旧 schema 原字段验收，不能修改生产迁移或放松保留断言。

发布 build 实际调用 `scripts/release/api-retry-deploy.py:295` → `scripts/release/overseas-deploy.py:29`；后者第 43–49 行运行安装 pytest 并 `check=True`。前三项不在忽略名单中，旧候选会阻断镜像安装验证，即使发布脚本自身单测通过也不能部署。修复路径是更新真实测试前提并重跑、固定新候选复审；不得把正确的未知保护改回自动重试。

证据：`output/api-retry-20261020/backend-full.log:31` 开始错误详情，第 665–678 行汇总。其余八项涉及 Windows 不提供 `O_NOFOLLOW`/安全目录描述符；主 Agent 报告在 Linux 容器复验对应三文件 21 passed，本报告未独立重跑该容器，不将其计作本 reviewer 通过证据，也不要求削弱生产安全读取。

### MEDIUM · 未知结果提示仍声称整个通道阻塞

`hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/RealTaskDetail.vue:10` 的标题仍为“请求结果需核实，通道保持阻塞”。实际合同允许未知调用占用一个名额，其余容量可用于其它图片：`backend/app/modules/api_image_edits/limiter.py:10` 计算占用，第 25 行只在总量达到上限时阻拦；`backend/tests/test_api_retry_policy.py:103` 明确证明 unknown 不阻断无关图片发送。标题应准确区分“此图待核实/保留占用”和“全通道冷却/满额”。本轮属于面向用户的新状态合同，旧文字不能继续误导。

## Stage 1 逐项合同核对

下表路径中的 `backend/`、`frontend/`、`infra/` 均相对 `hengxin-smart-image/`。功能“完整实现”是对已读代码与所列验证的结论，不替代上面的整体失败结论。

| 合同条目 | 结论 | 代码及验证证据 |
|---|---|---|
| 1. 新轮最多 20 次含首次；人工新轮无限生命周期；幂等与竞争；在途不可重开/修改/删除 | 完整实现 | `backend/app/modules/api_image_edits/retry_policy.py:33` 初始化 0/20；`:56` 耗尽判断；`claims.py:119` 锁内最终许可；`versions.py:152` 失败状态才重开；`service.py:31` 幂等摘要；`versions.py:119` 修改状态检查；`deletion_state.py:38` 状态及 lease 拒删。独立执行 `test_api_retry_policy.py:25` 证明20/21边界、同键复用与不同键冲突，`:77` 证明在途停止后拒删。 |
| 2. equal jitter 范围、抽样持久化、Retry-After 秒/HTTP 日期下限 | 完整实现 | `retry_policy.py:72` 实现5–10/10–20/20–40/30–60；`outcomes.py:34` 用数据库时间修正HTTP日期，`:50` 持久下一时间；`relay.py:33` 与`:50` 解析头。独立执行 `test_api_retry_policy.py:123`、`:140`、`:174`。超长头在 `outcomes.py:56`、`limiter.py:54` 人工暂停并持久无限期冷却，PG独立测试 `test_api_retry_gate_pg.py:217` 证明管理员resume不绕过。 |
| 3. 首次许可起45分钟、到期不再发、保守计次、收图不计次 | 完整实现 | `retry_policy.py:81` 首次许可计时；`claims.py:130` 在许可前检查；`execution.py:172` 先许可再POST，`:184` 结果另行收集；`claims.py:67` 不截断已有结果。独立测试 `test_api_retry_policy.py:54`、`:190` 验证截止与在途晚到结果。 |
| 4. 300s请求/60s下载/600s租约、续约、等待立即停、在途保留结果 | 完整实现 | `config.py:20`、`:25`、`:49`；`heartbeat.py:11`；`retry_stop.py:14` 与最终许可共用 channel 行锁，`:23` 区分已发送/未发送；`outcomes.py:64` 保留晚到成功。独立PG竞争测试 `test_api_retry_gate_pg.py:161`，同步测试 `test_api_retry_policy.py:77`。配置 `infra/compose.api-image.yaml:8`；发布停机与可见性在 `scripts/release/api-retry-deploy.py:130`、`:227`。 |
| 5. 全进程每5秒一个许可、10在途含未知、不积累突发；序列化后最后许可；覆盖所有入口 | 完整实现 | `state.py:16` 单 channel 行锁；`limiter.py:17`、`:38` 持久发送时间/容量；`execution.py:156`–`:175` 素材→序列化→许可→网络；`service.py:59`、`versions.py:76` 接入相同轮次。独立PG多进程测试 `test_api_retry_gate_pg.py:64`、`:83` 及序列化测试 `test_api_retry_policy.py:160`。 |
| 6. 连续5临时失败冷却60s、单探测、逐步恢复、旧代次fencing、不影响收图、resume不绕过 | 完整实现 | `limiter.py:46` 冷却代次递增；`:62` 只有同代成功可清除冷却，单探测后低并发逐步恢复；`claims.py:80` 人工暂停仍允许已有结果收集；`control.py:12` resume不清除自动冷却字段。独立PG `test_api_retry_gate_pg.py:109` 覆盖旧unknown、旧成功、新探测、探测unknown与并发逐步恢复。 |
| 7. 临时HTTP自动重试；账号/参数停止；超时/断连/解析失败unknown；保留所有权、管理员确认、request ID安全保留 | 完整实现 | `relay.py:147` 明确连接未建立才重试，`:149`–`:155` 断连未知，`:161` 错误分类，`:207` 无法解析成功结果未知；`claims.py:17`、`outcomes.py:41` 不释放unknown lease；`control.py:20` 要求确认；`relay.py:46` request ID约束，`outcomes.py:37` 保留但 `presentation.py:64` 不输出。独立测试 `test_api_retry_policy.py:103`、`:174` 与PG容量/晚到路径。 |
| 8. 纯等待让出5任务名额；每任务10图/批序；公平；收图/成功图/冻结输入保留 | 完整实现（部分验证沿用主 Agent 证据） | `scheduling.py:5`、`:17`、`:21`、`:27` 活动任务/批序及最近发送排序；`claims.py:73`–`:84` 仅有效lease/unknown占任务名额；`versions.py:28` 保留冻结snapshot；`versions.py:76` 有结果走收图，不开生图轮。相关测试入口 `test_api_image_task_slots.py:16`、`test_api_image_task_slots_pg.py:35`；本 reviewer 未单独重跑这两个文件，不额外宣称实测。 |
| 9. 持久轮次/共享时钟；旧终态不重开；遗留轮次保守4次；97历史unknown审计不占活跃容量 | 完整实现 | `models.py` 新增持久列；`retry_policy.py:26` PostgreSQL clock_timestamp在锁后取时；`:40` legacy保守计数；`migrations/versions/0031_api_retry_policy.py:31` 增量加列及保守计数，不改状态；`presentation.py:67` 无轮次不伪造retry；`limiter.py:10` 仅当前unknown item/真实running attempt占位。独立PG `test_api_retry_migration_pg.py:19`、`test_api_retry_gate_pg.py:83`、`:188`。 |
| 10. 真实次数/倒计时/冷却/名额/未知/停止原因、单图停止、防重复、刷新恢复、倒计时不调度 | 部分实现：上述MEDIUM文字偏差 | `frontend/src/views/hengxin/api-image-edits/ItemRetryStatus.vue:3`–`:32`；`retry-status.ts:3`–`:23`；`use-retry-clock.ts:3` 仅更新时间；`item-command.ts:9` 持久原key与结果未知状态；`ChannelNotice.vue:5` 区分人工暂停与自动冷却。实际查看宽/窄截图，卡片按钮和文字可见；浏览器脚本/HTTP联调记录见下文。 |
| 接口合同：retry可选字段、Channel扩展、stop鉴权/幂等/共享权限 | 完整实现 | `backend/app/modules/api_image_edits/retry_policy.py:90` 所有retry字段；`router.py:25` 权限、`:31` channel、`:148` stop；`retry_stop.py:15` 幂等及target保护；`frontend/src/types/api-image-edits.ts:16`、`frontend/src/api/api-image-edits-validate.ts:23`、`frontend/src/api/api-image-edits.ts:20`。 |
| 发布步骤、排空、备份隔离恢复、0031原字段保留、仅三服务、六原生进程/海外保留、失败关闭、不自动旧代码回退 | 发布运行路径已实现；安装验证未达标 | `scripts/release/api-retry-deploy.py:17` 服务白名单；`:48` 固定native PID/cwd/argv/env摘要；`:67` 未变服务核对；`:88` prepare；`:111` 队列与业务排空；`:130` 不强杀；`:171` 完整dump+隔离restore；`:201` 旧列指纹；`:234` 切换主路径；`:278` 失败关闭且不回滚。构建阻断见HIGH。生产实际执行未发生，不算已部署。 |
| 打包版本/源码与资产hash/隐私白名单/审查快照一致 | 路径已实现；真实交付包仍待提交后生成 | `scripts/release/package-api-retry.py:11` 必需迁移/helper，`:33` 0.2.44/0031；复用 `scripts/release/package-overseas.py:180` 已提交、已审快照、白名单与构建核对；`scripts/release/api-retry-deploy.py:31` 服务器包manifest及hash验证。未生成最终包，不宣称包已验收。 |

## 验证与原始输出

Reviewer 独立运行（本地专用 PostgreSQL，测试fixture独立schema，假上游，不触生产）：

```text
./.venv/Scripts/python.exe -m pytest tests/test_api_retry_policy.py tests/test_api_retry_gate_pg.py tests/test_api_retry_migration_pg.py -q --disable-warnings
.................                                                        [100%]
17 passed, 2 warnings in 18.74s
```

检查了主 Agent 的原始构建日志，末行原文（`output/api-retry-20261020/frontend-build.log:543`）：

```text
✓ built in 30.21s
```

这只证明该次前端生产构建；本 reviewer 没有重新执行完整前端构建，不将主 Agent 报告的317测试计作独立执行。后端全量原始输出（`output/api-retry-20261020/backend-full.log:665`）：

```text
FAILED tests/test_api_task_deletion_recovery.py::test_known_completed_attempts_allow_idle_deletion[uncertain]
FAILED tests/test_api_usage_facts.py::test_retry_freezes_actor_and_preserves_prior_attempt
FAILED tests/test_capacity_admission.py::test_delete_request_retains_capacity_until_actual_cleanup_and_expired_lease_never_releases
FAILED tests/test_domestic_retirement.py::test_populated_api_and_shared_rows_preserved_exactly
FAILED tests/test_overseas_management_freeze.py::test_confirmation_uses_new_binding_retry_keeps_old_revision_uses_current
FAILED tests/test_overseas_pictures.py::test_partial_retry_revision_history_review_archive
FAILED tests/test_overseas_pictures.py::test_revision_failure_keeps_original_and_can_retry
FAILED tests/test_overseas_pictures.py::test_marks_roles_stale_versions_and_storage_integrity
FAILED tests/test_overseas_pictures_protocol.py::test_invalid_second_image_never_stores_first[symlink]
FAILED tests/test_overseas_pictures_protocol.py::test_success_is_json_metadata_not_bytes
FAILED tests/test_overseas_pictures_protocol.py::test_storage_failure_retains_inaccessible_immutable_objects
FAILED tests/test_overseas_pictures_protocol.py::test_revision_copy_of_original_cannot_become_new_version
12 failed, 2018 passed, 281 skipped, 6 warnings in 309.58s (0:05:09)
```

UI：reviewer 使用 `view_image` 实际查看 `output/playwright/api-retry/wide-states.png` 与 `narrow-waiting.png`。宽屏3列卡片、窄屏单列，轮次/倒计时/停止按钮无裁切；颜色/卡片/圆角复用现有详情页。`output/playwright/api-retry/evidence.json:2` 记录6组交互与0页面错误，`output/playwright/api-retry-live/evidence.json:2` 记录4组真实本地HTTP与0页面错误；这些交互由主 Agent 执行，本 reviewer 核对记录及截图，未独立重启浏览器。Stage 2邻居页面实际渲染比较因HIGH未进入。

## 未实现、漂移与审查边界

- 未实现的核心调度条目：本次代码核对未发现；发布前全量/安装验证尚未达标，生产部署/正式浏览器验收/实际包审计尚未执行，不能计作完成。
- Spec 漂移：新增stop接口、轮次/共享门禁字段、3个前端状态组件/工具与版本化发布入口均对应本轮合同；没有发现新增产品页面或扩大到海外/CLI执行协议的实现。依据见上表相应路径。
- 安全扫描、命名/类型/300行限制、测试真实性全面审查、邻居页面视觉比较：**Stage 2 未执行**，不能据本报告声明没有安全或质量问题。
- 原候选审查中已发生测试修订。必须由主 Agent重新 `review-prepare`，把新candidateId与差异交fresh reviewer；修复不能沿用本报告登记通过。
