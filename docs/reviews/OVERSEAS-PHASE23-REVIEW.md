# Phase23 独立两阶段审查

审查范围：相对 Phase22 `cc32713` 的海外 generation/pictures/archives、0008 迁移及注册、正式图片/标注/成品库前端、Shell 窄屏修复、测试与离线联调脚本。排除主 Agent 列出的既存用户改动、模拟预览文件及 Phase24/25 规划。下文 backend/frontend/infra 路径均相对 `hengxin-smart-image/`。

快照历程：初始 `81b4176fb55a29dd7143656bb1b9512b8c06932eefc01ebbd99c83d0d9051756`；主 Agent 收尾前端后为 `ee66e6248a9a50153b012143c2ef6d60f090063ebf68306d4cc9da42bbdebbb3`；返工原图校验修复后为 `51ad3b09fa4c2cf5889aca8bfaa319cac29f0559738c5c68fd904fef3cbee957`。旧快照结论不批准新版本。

最终 candidateId：`2475f62359e31fbad2d390a9ec45a0c98142f171853db46325d8b7d7d5e00040`。已通过 review-status 独立核对 currentId 一致。新增差异为原图checksum校验及回归测试、0008离线回填SQL和PG执行测试、timing并发测试连接修正、生成typings恢复；已从Stage1重新复核。

最终审查结论：**Stage1 PASS，Stage2 PASS**。未关闭 HIGH/MEDIUM 问题为0。主Agent仍须等待其正在执行的全量重跑与最终HTTP联调结束，才登记批准并提交；本报告不将尚未结束的运行计为通过。

## Stage1：Spec compliance

逐项依据 `docs/OVERSEAS-PHASE23-CONTRACT.md:5`、`DEV-PLAN.md:154`、`Product-Spec.md:956`。

| 条目 | 结论与证据 |
|---|---|
| 确认方案按 SKU 生图、数量/顺序/尺寸一致 | 完整实现。`backend/app/overseas/plans/service.py:115` 创建冻结作业与槽位；`generation/delivery.py:41` 精确校验位置集合、数量和尺寸。协议专项真实 Linux 运行 17 PASS。 |
| 拒绝链接/越界/重复/损坏交付 | 完整实现。`generation/delivery.py:54` 路径限制，复用 `backend/app/execution/diagnostics.py:79` 安全描述符读取，`backend/tests/test_overseas_pictures_protocol.py:32` 覆盖缺失、软硬链接、重复位置和损坏第二张不存第一张。 |
| 原图不能冒充返工产物 | 原 HIGH 已关闭。初始独立复现 `ACCEPTED_UNCHANGED_ORIGINAL True stored 1`；修后 `generation/delivery.py:64` 在存储前拒绝相同 checksum，`test_overseas_pictures_protocol.py:83` 断言拒绝且存储为空。 |
| 私有存储、checksum、宽高、方案/作业追溯 | 完整实现。`generation/delivery.py:75`、`pictures/models.py:8`/`:22`；`pictures/files.py:12` 按大小/hash/格式/尺寸验证读取。HTTP 用例比较原始字节、损坏/缺失返回503。 |
| 部分失败只重试失败 SKU | 完整实现。`generation/service.py:18` 要求所有槽位无版本、同一个失败/取消 generation 作业；成功 SKU 无法重试；80字符 SKU 使用有界 hash 请求目标。`test_overseas_pictures.py:73`、`test_overseas_pictures_postgres.py:106`。 |
| 历史与当前版本审核绑定 | 完整实现。`pictures/review.py:36`、`generation/delivery.py:90`、`pictures/queries.py:41`；历史包含版本、意见、独立鉴权 URL。 |
| 负责人/设计主管处理，超管必须兼任 | 完整实现。`pictures/review.py:12` 和 `plans/service.py:67` 共用 `lock_actor` / `task.design` / 单任务范围检查。`test_overseas_pictures.py:158` 覆盖单独超管拒绝。 |
| 返工仅影响目标图；意见、底图冻结 | 完整实现。`pictures/revisions.py:23` 冻结 original 元数据/baseVersion/note/marks，只更新该 picture.job_id 和审核状态；`test_overseas_pictures.py:73` 验证 A 审核保留而 B 新版待审。 |
| 未知/在途禁重试，旧版本409，幂等 | 完整实现。`pictures/review.py:20`、`generation/service.py:30`、`execution/claims.py:103`；PG竞争测试 `test_overseas_pictures_postgres.py:41`/`:67` 验证一次提交/竞争409，取消迟到发布拒绝。 |
| 失败返工保留旧图并可重试 | 完整实现。`pictures/revisions.py:28`、`pictures/queries.py:28`；`test_overseas_pictures.py:132` 保留原 bytes，uncertain拒绝，明确failed后允许重试，失败图不能审批。 |
| 共享画布、原像素、意见/点数上限 | 完整实现。`frontend/src/views/overseas/OverseasPictureAnnotation.vue:13`/`:106` 复用 AnnotationCanvas 并核实自然尺寸；`backend/app/overseas/pictures/schemas.py:11`、`revisions.py:10` 校验有限数、原图边界、100条/2000单笔/10000总点。 |
| 标注定位说明不叠入正式图 | 完整实现协议。`generation/delivery.py:27` 加载私有原图并明确文字/几何仅定位说明；冻结输入由 `execution/materials.py:7` 写入。离线流程不等同真实收费模型画质验收。 |
| 真实图片/历史/无图/局部失败/错误可见 | 完整实现。`OverseasPictureResults.vue:3`–`:24`；独立重跑真实浏览器通过历史私有图片、只读、筛选下载和390宽屏；故障脚本 `frontend/tests/overseas-pictures.browser.mjs:47` 覆盖网络未知与完整意见保留。 |
| 全部当前版审核通过、无在途/未知才归档 | 完整实现。`archives/service.py:19` 同事务任务锁+gate，检查全部槽位和所有非终态作业；冻结 PictureVersion ID；`test_overseas_pictures.py:110` 验证提前归档409。 |
| 归档后禁止图/方案变化 | 完整实现。`pictures/review.py:23`、`generation/service.py:26`、`generation/delivery.py:86`、`plans/service.py:96`/`:110`；正式UI `OverseasPictureResults.vue:15` 隐藏修改。 |
| 品名/品牌/SKU检索分页、准确ZIP | 完整实现。`archives/service.py:37`/`:61`、`archives/router.py:18`；按冻结版本、任务关联校验、合法SKU/序号命名。HTTP比对ZIP红/绿目标字节；真实浏览器下载通过。 |
| 跨业务/跨任务/改派后历史权限 | 完整实现。`pictures/queries.py:14`、`archives/service.py:65` 每次以当前任务负责人授权；`test_overseas_pictures.py:126` 与 `infra/identity-test/phase23_checks.py` 验证权限拒绝、国内数据/对象不变。 |
| 资源上限与不自动清理 | 完整实现。`generation/delivery.py:62`/`:68` 为10MiB/256MiB；`archives/service.py:67`/`:79` 为8MiB内存临时流、1GiB原件总量。图片与归档模块无删除原件或成品路径。 |
| 0008 既有确认作业回填 | 完整实现；`backend/migrations/overseas/versions/0008_pictures.py:69`，`test_overseas_pictures_migration.py:55` 验证已有槽位回填、重复执行不重复。离线回填由`:13`/`:59`输出等价PG SQL，新增真实PG测试`:80`执行两次、重建2个槽位且不重复。 |

部分实现/未实现业务条目：无。Spec 漂移：无新增范围外正式业务能力；Phase24/25未实现能力不作本阶段缺陷。

## Stage2：Code quality

- 安全扫描：新增业务文件未发现 eval、innerHTML、危险HTML注入、前端秘密或硬编码生产凭据。`archives/service.py:40` 参数化/自动转义筛选；`pictures/router.py:25` 所有写请求有共享浏览器来源保护；`pictures/files.py:39` 与 `archives/service.py:92` 禁缓存。
- 资源释放：`pictures/files.py:25` 无论读取成功或损坏均 close/release_conn；`archives/service.py:82` 构建异常关闭临时流，正常stream finally关闭。存储部分写失败保留不可访问对象而不发布，`test_overseas_pictures_protocol.py:70` 有实际异常验证。
- 结构：新增业务模块按协议/查询/写事务/内容传输拆分，单个新增业务文件不足300行；新增 TypeScript 使用 unknown 校验服务端数据，`frontend/src/api/overseas/pictures.ts:13` 限定同任务同源版本URL，未发现新增 any。
- 测试真实性：HTTP校验真实bytes，PG竞争有Barrier，协议安全测试使用真实文件链接；真实浏览器脚本无route mock。mock故障脚本明确只用于交互故障。真实模型画质与生产部署未验，不能由32×32 fixture推断。
- 视觉比较：独立打开真实任务邻居页与成品页，截图 `output/playwright/phase23/review-neighbor.png`、`review-archive.png`；两者h1均28px、rgb(56,56,83)，白卡片/蓝按钮/Art shell一致。独立查看 `archive-mobile-designer.png`，390×844筛选与下载无横溢出；共享画布与窄屏弹窗约束见 `OverseasPictureAnnotation.vue:144`。本阶段未重新设计视觉。
- **MEDIUM 已关闭：离线迁移SQL生成失败。** 初始0008对MockConnection执行inspect；修后 `0008_pictures.py:13`/`:59` 输出真实 INSERT SELECT、jsonb数组位置展开与ON CONFLICT，保留既有任务回填语义。定向18PASS中offline SQL通过，新增PG回填实际执行1PASS，未用跳过回填掩盖错误。
- **回归已关闭：** `backend/tests/test_http_timing.py:18` 改为临时文件SQLite独立连接，避免StaticPool单连接被并发使用；仍保留asyncio.gather多请求与独立SQL计数断言。定向18PASS包含原失败测试，不改生产timing逻辑。

## 编译与验证原始输出

独立 Linux 协议复验：

```text
.................                                                        [100%]
17 passed, 2 warnings in 2.99s
```

独立真实浏览器复验：

```text
PASS real pictures browser: real images/history, immutable approval, archive filtering/download, narrow viewport and no page errors
```

读取主 Agent 保存的实际日志 `output/phase23-frontend-test.log` 与 `phase23-frontend-build.log`：

```text
ℹ pass 278
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 7606.3019
✓ built in 35.73s
```

完整后端第一次运行 `output/phase23-backend-final.log:404`：

```text
FAILED tests/test_http_timing.py::test_request_queries_include_threadpool_and_remain_isolated
FAILED tests/test_overseas_database.py::test_offline_sql_contains_only_overseas_version_table
2 failed, 2011 passed, 17 skipped, 15 warnings in 345.38s (0:05:45)
```

上述首轮输出不代表全量通过。原图修复后的协议+HTTP专项 `output/phase23-original-fixed.log` 原始结尾：

```text
20 passed, 2 warnings in 6.50s
```

迁移与timing专项 `output/phase23-regression-fixes.log` 最初输出18通过、新增PG测试fixture缺失1error；补入共享pg_factory后 `output/phase23-offline-backfill-final.log` 对该新测试真实运行：

```text
18 passed, 2 warnings, 1 error in 48.73s
1 passed, 2 warnings in 4.20s
```

已查阅失败原因及修复内容，定向覆盖关闭已知回归。`output/phase23-backend-rerun.log` 与 `output/phase23-http-final.log` 在本报告签发时仍运行，主Agent负责读取终态；若再失败或代码再变化，需要重新送审受影响差异。由主Agent登记review-approve，本报告不写clean。
