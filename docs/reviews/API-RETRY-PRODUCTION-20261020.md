# 国内 API 重试生产候选独立审查（最终）

- 最终 candidateId：`1ee4be48411bf1a532d0f4f649cbe7fc238d697745af58eb2fc96ae78bd6e04f`。
- 分支：`codex/api-image-retry-protection`；基线：`3a33cebc`。
- **Stage 1：PASS；Stage 2：PASS。未关闭的 HIGH / MEDIUM 问题：0。**
- 范围：相对基线的本轮 API 生图后端及0031迁移、相关新旧测试、前端类型/接口/新建/详情/停止状态及0.2.44、基础配置、版本化打包/发布入口与浏览器验收脚本。52个Python/TS/Vue/mjs文件纳入质量扫描，配置文件另行核对；普通文档作为需求与证据输入。
- 依据：`Product-Spec.md:1`、`DEV-PLAN.md:1`、`docs/API-RETRY-PLAN-20261020.md:5`、`docs/API-RETRY-RELEASE-NOTES-20261020.md:15`；执行 `.agents/skills/code-review/SKILL.md` 两阶段流程。
- 本报告批准的是源码候选的审查结论，不代表已提交、已生成最终发布包、已执行生产迁移/安装或已完成正式页面验收。主 Agent 应对同一candidate使用 `review-approve`；reviewer未写clean、未提交、未部署。

## 快照变化与问题关闭

首轮候选 `856a4be55eb87ca5658e5ddc4e24508094be61d6589a3e77ee9316c5cb7af204` 因回归前提及页面文字问题未通过；首轮原始报告保存在 `API-RETRY-PRODUCTION-20261020-INITIAL.md`，不得用于批准新快照。中间候选 `f50405ee...`、`3c410048...` 也未获批准。最终候选按下列差异重新从Stage 1核对，随后完成Stage 2，并未用旧结论覆盖新代码。

| 原问题 | 最终处置与证据 |
|---|---|
| HIGH：旧回归测试阻断安装pytest | `backend/tests/test_api_task_deletion_recovery.py:32` 新增真实发送→unknown→拒删/拒重发→管理员确认→拒绝旧结果→允许删除；`test_api_usage_facts.py:34` 改成三次临时失败加一次明确永久失败，保留actor及审计断言；`test_capacity_admission.py:109` 先领取发送许可再模拟租约失联并断言unknown保留token；`test_domestic_retirement.py:86` 反射0029旧schema写入，仍检查0030迁移原字段保留。独立重跑四文件32 passed。生产安全保护没有被放松。 |
| MEDIUM：unknown被描述成整个通道阻塞 | `frontend/src/views/hengxin/api-image-edits/RealTaskDetail.vue:10` 改成保留发送名额、其他图片按余量和通道排队，与 `limiter.py:10` 一致。 |
| MEDIUM：新建页仍承诺3次/1、2、4秒 | `frontend/src/views/hengxin/api-image-edits/RealCreate.vue:16`、`:19` 改成按序分批、每轮20次含首次、首次发送起45分钟、随机5–60秒及冷却可能更久；`scripts/api-retry/browser.mjs:119` 在真实dist断言新规则、无旧3次提示。reviewer实际查看最新create-policy截图。 |
| MEDIUM：新发布脚本305行超过skill上限 | `scripts/release/api-retry-deploy.py:286` 用清晰actions字典分派3个操作并精简注释；最终300行。`:212` 仍逐服务核对真实镜像与安装测试镜像ID。独立发布相关14 passed，无语义门禁删除。 |

本节中 `backend/`、`frontend/` 相对 `hengxin-smart-image/`。首轮报告将旧schema泛称0030；精确前提是0029数据上验证0030迁移，最终以反射后的真实表结构为准。

## Stage 1：逐项合同核对（PASS）

下表路径中的 `backend/`、`frontend/`、`infra/` 均相对 `hengxin-smart-image/`。功能“完整实现”是对已读代码与所列验证的结论；实际生产部署、包审计不在本次代码审查完成声明内。

| 合同条目 | 结论 | 代码及验证证据 |
|---|---|---|
| 1. 新轮最多 20 次含首次；人工新轮无限生命周期；幂等与竞争；在途不可重开/修改/删除 | 完整实现 | `backend/app/modules/api_image_edits/retry_policy.py:33` 初始化 0/20；`:56` 耗尽判断；`claims.py:119` 锁内最终许可；`versions.py:152` 失败状态才重开；`service.py:31` 幂等摘要；`versions.py:119` 修改状态检查；`deletion_state.py:38` 状态及 lease 拒删。独立执行 `test_api_retry_policy.py:25` 证明20/21边界、同键复用与不同键冲突，`:77` 证明在途停止后拒删。 |
| 2. equal jitter 范围、抽样持久化、Retry-After 秒/HTTP 日期下限 | 完整实现 | `retry_policy.py:72` 实现5–10/10–20/20–40/30–60；`outcomes.py:34` 用数据库时间修正HTTP日期，`:50` 持久下一时间；`relay.py:33` 与`:50` 解析头。独立执行 `test_api_retry_policy.py:123`、`:140`、`:174`。超长头在 `outcomes.py:56`、`limiter.py:54` 人工暂停并持久无限期冷却，PG独立测试 `test_api_retry_gate_pg.py:217` 证明管理员resume不绕过。 |
| 3. 首次许可起45分钟、到期不再发、保守计次、收图不计次 | 完整实现 | `retry_policy.py:81` 首次许可计时；`claims.py:130` 在许可前检查；`execution.py:172` 先许可再POST，`:184` 结果另行收集；`claims.py:67` 不截断已有结果。独立测试 `test_api_retry_policy.py:54`、`:190` 验证截止与在途晚到结果。 |
| 4. 300s请求/60s下载/600s租约、续约、等待立即停、在途保留结果 | 完整实现 | `config.py:20`、`:25`、`:49`；`heartbeat.py:11`；`retry_stop.py:14` 与最终许可共用 channel 行锁，`:23` 区分已发送/未发送；`outcomes.py:64` 保留晚到成功。独立PG竞争测试 `test_api_retry_gate_pg.py:161`，同步测试 `test_api_retry_policy.py:77`。配置 `infra/compose.api-image.yaml:8`；发布停机与可见性在 `scripts/release/api-retry-deploy.py:130`、`:224`。 |
| 5. 全进程每5秒一个许可、10在途含未知、不积累突发；序列化后最后许可；覆盖所有入口 | 完整实现 | `state.py:16` 单 channel 行锁；`limiter.py:17`、`:38` 持久发送时间/容量；`execution.py:156`–`:175` 素材→序列化→许可→网络；`service.py:59`、`versions.py:76` 接入相同轮次。独立PG多进程测试 `test_api_retry_gate_pg.py:64`、`:83` 及序列化测试 `test_api_retry_policy.py:160`。 |
| 6. 连续5临时失败冷却60s、单探测、逐步恢复、旧代次fencing、不影响收图、resume不绕过 | 完整实现 | `limiter.py:46` 冷却代次递增；`:62` 只有同代成功可清除冷却，单探测后低并发逐步恢复；`claims.py:80` 人工暂停仍允许已有结果收集；`control.py:12` resume不清除自动冷却字段。独立PG `test_api_retry_gate_pg.py:109` 覆盖旧unknown、旧成功、新探测、探测unknown与并发逐步恢复。 |
| 7. 临时HTTP自动重试；账号/参数停止；超时/断连/解析失败unknown；保留所有权、管理员确认、request ID安全保留 | 完整实现 | `relay.py:147` 明确连接未建立才重试，`:149`–`:155` 断连未知，`:161` 错误分类，`:207` 无法解析成功结果未知；`claims.py:17`、`outcomes.py:41` 不释放unknown lease；`control.py:20` 要求确认；`relay.py:46` request ID约束，`outcomes.py:37` 保留但 `presentation.py:64` 不输出。独立测试 `test_api_retry_policy.py:103`、`:174` 与PG容量/晚到路径。 |
| 8. 纯等待让出5任务名额；每任务10图/批序；公平；收图/成功图/冻结输入保留 | 完整实现 | `scheduling.py:5`、`:17`、`:21`、`:27` 活动任务/批序及最近发送排序；`claims.py:73`–`:84` 仅有效lease/unknown占任务名额；`versions.py:28` 保留冻结snapshot；`versions.py:76` 有结果走收图，不开生图轮。相关测试入口 `test_api_image_task_slots.py:16`、`test_api_image_task_slots_pg.py:35`；本 reviewer 另用 output/api-retry-20261020/test_review_actual_wait.py:10 实际领取发送许可、注入503并证明第6任务获得名额，1 passed；Linux全量覆盖既有相关测试。 |
| 9. 持久轮次/共享时钟；旧终态不重开；遗留轮次保守4次；97历史unknown审计不占活跃容量 | 完整实现 | `models.py:44`、`:71`、`:102`、`:126` 新增持久列；`retry_policy.py:26` PostgreSQL clock_timestamp在锁后取时；`:40` legacy保守计数；`migrations/versions/0031_api_retry_policy.py:31` 增量加列及保守计数，不改状态；`presentation.py:67` 无轮次不伪造retry；`limiter.py:10` 仅当前unknown item/真实running attempt占位。独立PG `test_api_retry_migration_pg.py:19`、`test_api_retry_gate_pg.py:83`、`:188`。 |
| 10. 真实次数/倒计时/冷却/名额/未知/停止原因、单图停止、防重复、刷新恢复、倒计时不调度 | 完整实现，旧文字已纠正 | `frontend/src/views/hengxin/api-image-edits/ItemRetryStatus.vue:3`–`:32`；`retry-status.ts:3`–`:23`；`use-retry-clock.ts:3` 仅更新时间；`item-command.ts:9` 持久原key与结果未知状态；`ChannelNotice.vue:5` 区分人工暂停与自动冷却。RealTaskDetail.vue:10 与 RealCreate.vue:16、:19 已同步真实未知占用与新轮策略；本 reviewer 独立复跑7组实际dist浏览器检查，详见下文。 |
| 接口合同：retry可选字段、Channel扩展、stop鉴权/幂等/共享权限 | 完整实现 | `backend/app/modules/api_image_edits/retry_policy.py:90` 所有retry字段；`router.py:25` 权限、`:31` channel、`:148` stop；`retry_stop.py:15` 幂等及target保护；`frontend/src/types/api-image-edits.ts:16`、`frontend/src/api/api-image-edits-validate.ts:23`、`frontend/src/api/api-image-edits.ts:20`。 |
| 发布步骤、排空、备份隔离恢复、0031原字段保留、仅三服务、六原生进程/海外保留、失败关闭、不自动旧代码回退 | 发布运行路径与本地测试通过；生产实际安装待执行 | `scripts/release/api-retry-deploy.py:17` 服务白名单；`:48` 固定native PID/cwd/argv/env摘要；`:67` 未变服务核对；`:88` prepare；`:111` 队列与业务排空；`:130` 不强杀；`:169` 完整dump+隔离restore；`:199` 旧列指纹；`:231` 切换主路径；`:275` 失败关闭且不回滚。原测试前提阻断已修复，完整Linux回归及布局补验通过；生产实际镜像安装仍由发布入口强制执行，不算已部署。 |
| 打包版本/源码与资产hash/隐私白名单/审查快照一致 | 路径已实现；真实交付包仍待提交后生成 | `scripts/release/package-api-retry.py:11` 必需迁移/helper，`:33` 0.2.44/0031；复用 `scripts/release/package-overseas.py:180` 已提交、已审快照、白名单与构建核对；`scripts/release/api-retry-deploy.py:31` 服务器包manifest及hash验证。未生成最终包，不宣称包已验收。 |

## Stage 2：代码质量与安全（PASS）

| 维度 | 结论与证据 |
|---|---|
| 命名、职责、类型、文件大小 | 轮次策略 `backend/app/modules/api_image_edits/retry_policy.py:33`、共享门禁 `limiter.py:17`、停止 `retry_stop.py:12` 分离；网络调用前后的事务在 `execution.py:156`、`:172`、`:175` 清晰隔离。新增TS接口 `frontend/src/types/api-image-edits.ts:16` 与验证器 `frontend/src/api/api-image-edits-validate.ts:23` 对齐，新增代码无TS any。对52个变更源码文件计数，无超过300行文件；最长 `scripts/release/api-retry-deploy.py:300`。diff空白检查通过。 |
| 测试真实性 | `backend/tests/test_api_retry_gate_pg.py:32` 使用独立子进程和真实PostgreSQL行锁，不用SQLite假装跨进程安全；`:161` 用并发barrier竞争停止与最终许可；`test_api_retry_policy.py:25` 真走20次执行并证明第21次不发送；`:160` 验证序列化前后许可；`test_api_retry_migration_pg.py:19` 实际去掉新增列、重复运行迁移并保留历史审计。新的4项旧回归修复使用可达前提，未改生产保障来迎合旧断言。reviewer另加临时外部测试证明真实发送后等待释放任务槽。 |
| 交互故障覆盖 | `scripts/api-retry/browser.mjs:76`–`:123` 在生产dist中实际点击、刷新、断开停止响应、验证同一幂等键、失败恢复/在途晚到/冷却与新建页；`frontend/tests/api-image-retry.test.ts:54` 保留未知请求原key；`:79` 双击仅一次。浏览器并非只测纯函数，reviewer独立执行7组通过、0页面错误。外部上游为假服务，不宣称验证收费模型效果。 |
| 安全扫描 | 对本轮源码扫描 `eval`、`dangerouslySetInnerHTML`、`innerHTML`、前端KEY/SECRET/TOKEN、常见真实密钥前缀、绝对用户路径和TS any，未发现新增危险执行或硬编码真实凭据。`relay.py:46` request ID字符/长度约束；`:65` 错误体仅本地分类；`outcomes.py:31` UI仅安全码；`presentation.py:64` 不输出上游URL/凭据/request ID；`router.py:25`、`:148` stop继承共享权限。发布SQL仅静态语句或 `api-retry-deploy.py:146` 校验后的数据库标识符，subprocess复用参数数组；`package-overseas.py:129`、`:180` 保留资产白名单、隐私及审查快照门禁。 |
| 视觉邻居实际对比 | reviewer打开真实dist记录列表及新建页，截图 `output/playwright/api-retry/review-neighbor-records.png`、`review-neighbor-create.png`，与最终 `wide-states.png`、`narrow-waiting.png`、`create-policy.png` 实际view_image对比。沿用白卡、细边框、圆角、蓝色主操作、橙色警示及现有footnote；新停止按钮不越界。390px一列卡片保持文字/按钮完整；`RealTaskDetail.vue:153` 与 `ItemRetryStatus.vue:35` 对应渲染。邻居旧create截图用于基准，最终create-policy才是已修正文案的产物。 |
| Spec漂移 | 新stop接口、持久轮次/共享门禁列、状态组件与版本化发布入口均映射Stage 1合同；没有新增产品页面。生产更新服务限定 `scripts/release/api-retry-deploy.py:17`，原生进程、海外及身份镜像/容器保护在`:48`、`:67`。未擅自扩大为海外重试或CLI执行协议改动。 |

上表 `backend/`、`frontend/` 相对 `hengxin-smart-image/`。没有剩余部分实现或未实现的本轮源码条目。安全扫描结论仅限本轮源码；既有依赖audit的High/Moderate不是“全部依赖无漏洞”，本轮未变依赖和锁文件。见 `docs/API-RETRY-VALIDATION-20261020.md:27` 与原始audit日志。

## reviewer独立执行与原始输出

本地隔离PostgreSQL及假上游，不触生产，不发送收费模型调用：

```text
pytest tests/test_api_retry_policy.py tests/test_api_retry_gate_pg.py tests/test_api_retry_migration_pg.py -q --disable-warnings
17 passed, 2 warnings in 18.74s

pytest tests/test_api_task_deletion_recovery.py tests/test_api_usage_facts.py tests/test_capacity_admission.py tests/test_domestic_retirement.py -q --disable-warnings
32 passed, 2 warnings in 21.10s

pytest output/api-retry-20261020/test_review_actual_wait.py -q --disable-warnings
1 passed, 2 warnings in 1.70s

pytest scripts/release/test_api_retry_deploy.py scripts/release/test_package_api_retry.py -q --disable-warnings
14 passed in 0.20s
```

临时补测第一次从仓库根启动时未加载后端测试环境，收集时报缺少DATABASE_URL等配置；加载已有 `tests/conftest.py` 的明确假环境后重跑通过。这是reviewer测试启动前提修正，不修改产品代码或弱化测试断言。

编译/类型原始输出：

```text
python -m compileall -q hengxin-smart-image/backend/app/modules/api_image_edits hengxin-smart-image/backend/migrations/versions/0031_api_retry_policy.py scripts/release/api-retry-deploy.py scripts/release/package-api-retry.py
PYTHON_COMPILE_PASS

> hengxin-smart-image-frontend@0.2.44 typecheck
> vue-tsc --noEmit
[exit_code=0]
```

reviewer对最终dist执行 `node scripts/api-retry/browser.mjs`，输出原文关键字段：

```json
{"checks":["真实次数、动态倒计时、冷却、未知、失败及旧记录，无前端调度请求","390px逐一滚动检查所有卡片提示及按钮均处于卡片和抽屉可见边界内","停止loading/防双击、响应丢失后刷新恢复同一幂等键，确认后显示停止完成","在途停止仅停止后续请求、旧图保留，晚到成功正常呈现","冷却期间合法失败项仍能开启新轮排队，明确停止失败后按钮恢复可重试","恢复探测提示与成功图片保持，未访问生产API或CLI停止","正式新建页展示20次/45分钟及随机错峰规则，无旧3次提示"],"requests":6,"errors":[]}
```

## 完整回归、构建及交付边界

reviewer直接读取主 Agent 的原始日志，明确区分执行者：

- 最新前端构建日志 `output/api-retry-20261020/frontend-build.log:543`：`✓ built in 37.20s`，主 Agent构建退出0。前端317项、API相关193项、发布全量879项及两项Docker专项由主 Agent执行，详见验收文档；没有冒充reviewer独立执行。
- Linux全量 `output/api-retry-20261020/backend-linux-full.log` 原始末行：`1 failed, 2179 passed, 25 skipped, 1 deselected, 6 warnings in 525.38s (0:08:45)`。唯一失败为 `tests/test_domestic_retirement.py:112` 的 `ROOT.parents[1]`：首次容器将backend挂在 `/app`，该仓库级测试需要完整scripts目录布局。
- 保持代码不变，主 Agent用完整 `/repo/hengxin-smart-image/backend` 与 `/repo/scripts` 只读布局复验整个文件，`output/api-retry-20261020/backend-linux-retirement.log:2` 原文：`9 passed in 28.95s`。唯一失败已补验关闭，不能把首轮全量日志篡写成一次全绿；25项skip和1项deselect不计为通过。
- `output/playwright/api-retry-live/evidence.json:2` 为主 Agent实际FastAPI+独立PG+MemoryStore+假上游的4组HTTP证据，未mock业务API；本reviewer核对记录，另独立执行上述dist交互。不是生产模型效果验收。
- 实际生产包需中文提交后生成并审计，实际镜像需继续通过 `scripts/release/overseas-deploy.py:43` 强制安装测试；生产关闭接纳/排空/备份恢复/迁移/正式UI验收由主 Agent执行。它们是后续发布动作，不是本报告已经完成的事项。

最终候选已通过上述两阶段源码审查。报告写入后再次运行 `review-prepare` 核对内容快照；只允许批准本报告顶部的同一candidateId。