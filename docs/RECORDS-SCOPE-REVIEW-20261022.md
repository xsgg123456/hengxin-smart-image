# 国内换图记录范围筛选 · 独立审查

- candidateId：`e40dcd0f8dd9823e4cbb5752a2a4ed376c19f61c6a2365f7ec39b7e42537be5d`。
- 审查范围：送审时全部 Git 差异和未跟踪文件，包括正式前后端、测试、已批准的 `frontend/preview-records-scope/`、隔离验收工具、5 个 `record-filters` 发布文件、对应源文档。本报告中的 `backend/`、`frontend/` 相对 `hengxin-smart-image/`，`scripts/`、`docs/` 相对仓库根目录。
- 依据：完整读取 `docs/RECORDS-SCOPE-20261022.md:1`、`docs/RECORDS-SCOPE-PREVIEW-REVIEW-20261022.md:1`、预览源文件和 README；读取 `Product-Spec.md:1`、`Design-Brief.md:1`、`DEV-PLAN.md:1` 本轮条目。最新授权为开发验证及审查后停止，不提交 Git、不打包或生产部署。
- **Stage 1：PASS。Stage 2：PASS（限本轮送审范围）。** 本轮变更未发现 HIGH / MEDIUM 问题；另有末节记录的 scope 外既有风险，未修复，不属于“全产品所有环境无缺陷”的结论。
- 审查开始、中途和最终 `review-status` 的 currentId 均等于上述候选；新增纯 Markdown 验收/审查记录未改变受控代码快照。reviewer 未改实现、未执行发布入口、未提交或部署，也未修改 `.needs-review`。主 Agent 可按协议为此同一候选登记两阶段 PASS；用户暂停提交/部署的边界继续有效。

## Stage 1 · Spec Compliance

| 合同条目 | 结论与代码证据 | 验证证据 |
| --- | --- | --- |
| HTTP 默认本人，归属为最初创建人，修改人不转移归属 | 完整实现。`backend/app/modules/api_image_edits/router.py:95` 默认 mine，`:104` 从服务端 user.id 取 owner；`listing.py:18` 过滤 owner_id；既有 `service.py:52` 创建时赋值 owner_id | `backend/tests/test_api_image_records.py:53` 将 owner/operator 交叉，验证默认本人、他人、身份切换、detail creatorId 和内部默认 all；reviewer 独立实跑通过 |
| 全部任务、创建人 UUID、重名按 ID、停用历史人员、仅当前用户或有未删除任务者 | 完整实现。`router.py:99` UUID 与 Literal 校验，`:101` mine+creatorId 拒绝；`listing.py:52` 仅投影 id/name，不按 status 排除停用历史成员；`RealRecords.vue:10` option value 为 id | `test_api_image_records.py:72` 验证重名、停用、有/无/已删除任务人员；浏览器 `records-scope.browser.mjs:59`、`:95` 验证双重名和选中停用成员仅 10 套 |
| 登录及 shared_resources，不扩缩他人查看、修改、下载、重试、删除权限 | 完整实现。`router.py:27` 新列表及创建人共用原 User 依赖；`:113` 之后现有详情/修改/重试/删除/下载入口未变，列表筛选没有写回任务归属 | `test_api_image_records.py:64` 他人详情 200；`:148` 未登录/禁用身份被拒；`test_api_image_domain.py:44`、`test_api_image_versions.py:108` 为既有权限回归。浏览器未执行真实写操作，此行不声称浏览器验证了写入结果 |
| 北京时间自然日、全部默认、今天/7天/30天含今天、完整自定义范围 | 完整实现。`records-filters.ts:3` 使用北京时间 today，减 6/29 天；`listing.py:27` 开始包含当日 0 点、结束不含次日 0 点；`RealRecords.vue:12`、`:17` 真实日期选择，无固定示例日期 | `records-scope.test.ts:7` 北京跨日/跨年及自定义；`test_api_image_records.py:89` 微秒级边界及单边日期；浏览器 `records-scope.browser.mjs:123` 今天与同日自定义 |
| 不完整日期不加条件并提示；倒置/非法日期拒绝 | 完整实现。`records-filters.ts:5` 不完整返回空条件；`RealRecords.vue:17` 提示；`listing.py:15` 倒置 422，`:35` 溢出 422；路由 date 类型校验 | `records-scope.test.ts:14`；浏览器 `records-scope.browser.mjs:125` 不完整提示且全量；`:70` 倒置 422；后端 `test_api_image_records.py:136` 非法输入 |
| 人员/状态/名称或编号/时间联合筛选，筛选和 pageSize 变更回第 1 页 | 完整实现。`use-records.ts:35` 统一 query，`:89` 切 scope 清人员，`:90` 同步重置页码；`listing.py:20` 名称和带/不带连字符编号使用转义参数查询 | `records-pagination.test.ts:38`、`:61`、`:65` 实际 Vue composable 调用；浏览器 `records-scope.browser.mjs:103` 创建人+状态+日期+UUID 得 1 套 |
| 先筛选后分页，20/50/100，最新创建优先且同时间稳定 | 完整实现。`presentation.py:83` 先构造筛选，`:89` created_at desc + id；`RealRecords.vue:28` 页容量 | `test_api_image_records.py:123` 同时间 3 个 UUID 稳定排序；浏览器 `records-scope.browser.mjs:114` 50 条及 100 容量下 51 条 |
| 四卡全量 SQL 汇总：tasks、queued/running/uncertain、succeeded 图片、failed 图片 | 完整实现。`listing.py:40` 对同一个 matched 子查询分别 SQL 聚合任务/图片；`presentation.py:85` total=stats.tasks，分页不影响聚合；`RealRecords.vue:53` 使用服务端 stats | `test_api_image_records.py:102` 两页都是 5/3/10/5，删除排除、越界页仍全量；`:160` 捕获 SQL 证明不读取 prompt/events/history；浏览器 `records-scope.browser.mjs:79`、`:81` 翻页不变 |
| 缺统计显示未知，不用本页补值或伪零 | 完整实现。`api-image-edits-validate.ts:55` stats 可缺但存在时校验整数/total 一致；`RealRecords.vue:53` 四卡缺值为 —；`:18` 数量暂不可用 | `records-scope.test.ts:35` 拒绝损坏 stats，允许旧响应缺 stats；浏览器 `records-scope.browser.mjs:143` 新查询失败四卡未知，截图 `06-new-query-error-no-stale-data.png` |
| 详情关闭/手动刷新/静默轮询保留条件和页码；重置清条件保 scope | 完整实现。`RealRecords.vue:49` 详情仅修改 query.task；`use-records.ts:59` reset 不改 scope；`:69`、`:74` 沿用当前 query | 浏览器 `records-scope.browser.mjs:80` 至 `:92` 第二页详情关闭/刷新/轮询行数据相同；`:110` 重置后仍 all；`records-polling.test.ts:12` 实际轮询状态机回归 |
| 菜单重进/新建返回默认本人；空态有可达入口 | 完整实现。`use-records.ts:25` 初始化 mine；`frontend/src/router/modules/index.ts:9` keepAlive=false；`RealRecords.vue:19` 区分无任务/无匹配，`:27` 清空筛选/新建/全部入口 | 浏览器 `records-scope.browser.mjs:152` 新建返回 mine；`:165` 新身份空态和全部入口；截图 `07-no-match.png`、`10-empty-new-identity.png` |
| 同查询失败保留数据；新查询不冒充旧数据；快速筛选不被过期响应覆盖 | 完整实现。`use-records.ts:37` queryKey 变更清数据，`:42` serial/alive 拒绝旧响应，`:50` 错误文案，`:90` 在 debounce 前立即失效旧请求 | `records-pagination.test.ts:52` 延迟旧响应、`:60` debounce 期间旧响应；浏览器 `records-scope.browser.mjs:135` 同查询保留 50 行，新查询 503 清空、恢复空态；实际查看 `05`/`06` 证据 |
| 账号切换不复用前账号结果 | 完整实现。`frontend/src/api/hengxin/http.ts:12` 每请求捕获身份代次、`:30`/`:44` 验证，`identity.ts:17` advance 取消读取；`use-records.ts:134` 卸载失效，`:22` 每实例身份 | `test_api_image_records.py:68` 服务端切换身份；浏览器 `records-scope.browser.mjs:163` 新 cookie+重新 bootstrap 后只显示新账号 0 套。浏览器该项覆盖重新启动身份，不冒充同页会话变更的全部测试 |
| 采用批准预览，正式页面无示例场景/固定身份日期；保留实际详情和危险操作确认 | 完整实现。`RealRecords.vue:4` 范围 tab、`:7` 四卡、`:9` 筛选、`:18` 范围说明、`:23` 创建人、`:30` 正式详情、`:63` 永久删除确认 | 实际打开截图与批准预览及邻居基准对照，见 Stage 2；正式代码没有导入 preview state；浏览器真实 GET 详情和图片，不拦截成示例响应 |
| 窄屏筛选堆叠、统计两列、表内横向滚动；52px 图片及原框架密度 | 完整实现。`RealRecords.vue:70` 52px，`:74` cell padding 9px，`:95` 640px 下两列/堆叠；ArtTable 承载宽表 | reviewer 实际 view_image 正式 `09-mobile-all.png`：390px 无页面横向溢出、两列卡/纵向筛选；自动脚本 `records-scope.browser.mjs:156` 校验 document 宽度。当前截图不声称已经点击移动端最右侧操作 |
| 版本 0.2.49，国内0032/海外0020，无迁移，不触海外实现 | 完整实现。`frontend/package.json:3`；`scripts/release/package-record-filters.py:30`、`domestic-record-filters-runtime.py:21` 固定版本/schema；deploy 只有 api compose up，无 migrate | Git 差异无 migration、海外实现或依赖变更；发布专项 `test_record_filters_release.py:138` 检查无 compose run/迁移。发布本轮未执行 |

部分实现：无。未实现：无。Spec 漂移：未发现新增生产页面、表或权限；`/creators` 是明确约定的新接口。预览保留独立交互示例、隔离 QA 和发布准备脚本均属于送审范围，不能当作已部署功能。

## Stage 2 · Code Quality

### 代码结构、可靠性与安全

- 结构符合要求：新增 `listing.py:14`/`:40`/`:52` 分离筛选、聚合、创建人；`records-filters.ts:3` 隔离日期计算；`use-records.ts:34` 负责请求与状态。送审代码/测试文件均未超过 300 行，最大新增发布测试 271 行；扫描前端改动没有显式 any。`git diff --check` exit 0，仅行尾转换提示。
- 查询安全：`listing.py:21` 使用 SQLAlchemy 表达式和 `autoescape=True`；`router.py:99` UUID 校验；没有拼入用户文本的 SQL。发布 `domestic-record-filters-verify.py:30` 表名来自系统目录并受正则约束；状态查询只读。
- 隐私：`listing.py:55` 创建人只返回 id/name；`summaries.py:38` 保持列表精简投影；生产 API 仍 `router.py:27` 鉴权。扫描 eval/innerHTML/dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN 和常见密钥前缀未发现泄漏。`scripts/records-scope/live-app.py:22` 的 isolated-test 是本地测试占位值、API key 为空，不是生产凭据。
- 测试内动态执行已经辨明：`records-pagination.test.ts:19`、`records-polling.test.ts:32` 的 new Function 只运行本仓库经过 TypeScript 编译的 composable，便于挂真实 Vue 响应式状态机；不接收外部输入、不进入生产包，不能报告成生产 eval 漏洞。
- 隔离工具：`scripts/records-scope/live-app.py:19` 显式测试环境，`:105` 覆盖真实 API 的数据库/身份/图片依赖，`:113` 拒绝业务写请求，`:138` 只绑定 127.0.0.1；实际数据存于内存 SQLite/MemoryStore。`records-scope.browser.mjs:8` 固定 loopback origin。`cleanup.log:1` 确认进程与端口清理。

### 发布准备代码（仅静态审查，不授权执行）

| 要求 | 代码及测试证据 | 结论 |
| --- | --- | --- |
| 打包版本/schema、依赖闭包、无独立预览或私有资料 | `package-record-filters.py:11` REQUIRED；`:22` validate；`:30` 版本/schema；继承现有打包隐私检查；`test_record_filters_release.py:29`、`:42`、`:51`、`:56` | 匹配。主 Agent 提供专项 34 passed；未据此声称安装包或服务器已验证 |
| 只切国内 HTTP API image，其他服务保留原容器/image；配置、原生 cwd/env/policy 保持 | `domestic-record-filters-runtime.py:45` same_settings 只允许 api image；`:60` overlay 仅 api image；`:70` 对比容器身份/挂载/文件和原生环境；`:113` docker start 原容器；deploy `:46` --no-deps/--no-build/--pull never | 匹配。`test_record_filters_release.py:80` 拒绝环境/build/策略/worker image 漂移，`:190` 拒绝替换原容器 |
| 排空后完整备份及隔离恢复比较，现存数据/schema不迁移 | deploy `:35` 关闭入口、停 api、pause、drain；verify `:26` 每张表全部行/全部列及 schema，`:37` 备份，`:58` 将完整 state 交 restore_check；`:67` 消费者恢复前再次比较；既有 `member-release-backup.py:114` --network none 恢复 | 匹配。发布测试 `:204`、`:237`、`:253` 覆盖列/schema 比较和恢复失败不落 COMPLETE；未运行实际数据库备份/恢复 |
| 故障关闭 gate、暂停 channel、保存恢复现场，禁止不明重放/自动倒库 | deploy `:18` 禁止重放，`:74` BaseException 保存恢复阶段，`:80` 重新关闭 gate，`:84` pause，`:82`/`:86` 二次故障分别留标记 | 匹配。`test_record_filters_release.py:156` 多阶段故障注入，`:174` 不允许重放，`:182` 未验证备份禁止切换。测试不证明真实网络/服务器故障全部可恢复 |

### 测试真实性与边界

- 后端用真实 FastAPI 路由、SQLAlchemy 查询和真实结果断言，`test_api_image_records.py:53`、`:89`、`:102`、`:160` 没有将列表/统计替换为 stub；Windows 小范围 reviewer 实跑 17 passed。PG 适配 `test_api_image_records_pg.py:15` 用真实 PG factory 复用 6 条 HTTP 合同；已读取独立 PostgreSQL 18.6 的 `linux-records-pg-early.log`，6 passed / 2 warnings / 4.26s，不将 SQLite 结果标为 PG 结果。
- 前端 `records-pagination.test.ts:13` 读取实际 use-records 源码，以 Vue renderer mount，控制返回顺序，断言查询/页码/过期响应/统计；并非复制实现后自证。`records-polling.test.ts:12` 覆盖隐藏/恢复授权、详情故障、删除状态、重试幂等、卸载清计时器。
- 浏览器 `records-scope.browser.mjs:1` 配合隔离 live-app 加载生产 dist，真实发 HTTP、选择 Element Plus 控件及抽屉，不用路由拦截伪造业务成功；`browser-evidence.json` 包含 35 个业务 GET、两次预期 503、0 pageerror。51 套数据有不同 owner/operator、停用重名和 1 条显式删除记录，聚合预期按 fixture 独立计算。
- reviewer 额外将实际 `use-records.ts` 编译并挂载 Vue renderer，独立注入创建人加载失败、重试、乱序响应和组件卸载，验证 `use-records.ts:53` 错误提示、loading 复位、最新响应胜出、卸载后不写回；四项断言通过。`RealRecords.vue:16` 错误按钮接线另经代码核对。
- 明确测试盲区（非已发现功能缺陷）：创建人失败重试按钮本轮未在浏览器点击；窄屏最右列操作可达依赖 ArtTable 和预览既有实测，本轮浏览器只验证页面不溢出；浏览器未发业务写操作。上述不扩写成“全部故障和全部操作均实测”。
- Windows 后端全套 8 failed 的初始事实保留；Linux 初次全套实际为 2393 passed / 24 skipped / 1 failed。失败已由当前版本和 HEAD 的双时区对照定位，详见末节；采用实际生产数据库的 UTC 时区后，完整复验 2394 passed / 24 skipped / 0 failed，记录 PG 专项再次 6 passed。跳过项和初次失败均保留，不改写为从未失败。

### 实际视觉对照

reviewer 使用 view_image 实际查看 `output/playwright/records-scope-baseline.png`、`records-scope-mine.png`，以及正式 `01-mine-desktop.png`、`03-creator-filter.png`、`06-new-query-error-no-stale-data.png`、`09-mobile-all.png`、`10-empty-new-identity.png`，不是仅由“复用了组件”推断。

- 正式桌面 1440px 与批准预览 1920px：侧栏宽度和内容左边距相同；标题/浅底/蓝色控件/白卡圆角/表格线与字重一致，四卡按可用宽度缩放。缩略图52px、表格上下9px、tab44px、筛选gap16px的数值分别见正式 `RealRecords.vue:70`、`:74`、`:79`、`:81` 和预览 `Records.vue:53`、`:57`、`:61`、`:63`。
- 正式新增“创建人”只在全部范围显示；正式账号标识替代“交互预览·示例数据”，未显示场景工具。无权限的验收账号没有管理菜单，属于实际身份权限，不是视觉丢失。
- 390px 正式全部范围保持统计两列、筛选纵排、按钮可见；宽表在卡片内部滚动，页面本身无横向溢出。错误页明确显示加载失败和未知统计；新账号空态四卡真实 0、提供新建/全部入口。

## 编译与测试原始输出

reviewer 独立执行（backend cwd）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_api_image_records.py tests/test_list_summaries.py
.................                                                        [100%]
17 passed, 2 warnings in 2.68s
exit_code=0
```

两条 warning 为现有 Starlette TestClient/httpx 和 anyio BlockingPortal 弃用提示，没有隐藏失败。

reviewer 独立内联测试（frontend cwd，Node + tsx 载入真实源码及 Vue renderer，未改工程文件）：

```text
PASS: real useRecords creator failure/retry, latest response wins, unmounted response ignored
exit_code=0
```

reviewer 独立执行（frontend cwd）：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-records-scope/tsconfig.json
stdout/stderr: (empty)
exit_code=0
```

主 Agent 当场复验原始日志 `output/records-scope-formal/frontend-tests.log`、`typecheck.log`、`release-tests.log`：

```text
ℹ tests 355
ℹ pass 355
ℹ fail 0
ℹ skipped 0
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
stdout/stderr: (empty); exit_code=0（主 Agent 执行结果）
..................................                                       [100%]
34 passed in 2.93s
```

正式构建原始日志 `output/records-formal-build.log` 末尾：

```text
dist/assets/echarts-OiDiNeVO.js                                                           756.30 kB │ gzip: 244.76 kB
dist/assets/index.vue_vue_type_style_index_0_lang-Bm3D7EOm.js                             814.14 kB │ gzip: 275.63 kB
dist/assets/index-DLJ7ojxV.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 33.20s
```

本地功能浏览器 `output/records-scope-formal/browser-run.log` 为 PASS / 8 组 / businessRequests 35；完整每个业务请求、响应码及检查名称见同目录 `browser-evidence.json`，截图与执行脚本共同交叉验证。

## 最终回归与快照核对

独立 PostgreSQL 合同已实测，并已读取原始输出：

```text
# output/records-scope-formal/linux-records-pg-early.log
6 passed, 2 warnings in 4.26s
# output/records-scope-formal/linux-records-pg.log
6 passed, 2 warnings in 4.02s
```

Linux 初次全套原始输出 `output/records-scope-formal/linux-full.log`：

```text
FAILED tests/test_api_retry_gate_pg.py::test_oversized_retry_after_survives_postgres_json_and_admin_resume
1 failed, 2393 passed, 24 skipped, 10 warnings in 367.98s (0:06:07)
```

**MEDIUM · scope 外既有风险，未在本轮修复：** `backend/app/modules/api_image_edits/limiter.py:56` 使用 UTC datetime.max 表示超长上游 Retry-After 冷却。PG 会话为 Asia/Shanghai 时，该值显示为公元 10000 年，读取 `ApiChannel` 引发 psycopg DataError，发生于既有 `tests/test_api_retry_gate_pg.py:235`。本轮记录筛选代码未修改该路径；不能把该事实表述为“所有环境均没有问题”。

reviewer 已读取 `linux-retry-{current,head}-{shanghai,utc}.log` 四份原始结果及 `linux-retry-timezone-status.log`：

```text
current shanghai exit_code=1
head shanghai exit_code=1
current utc exit_code=0
head utc exit_code=0
```

该对照证明失败在 HEAD 也存在，UTC 单项通过不等于全套通过。24 项初始跳过为未提供独立身份 Redis 22 项、非 root WSL 1 项、Windows junction 专属 1 项，不记为通过。

对照基线为 HEAD `11069a3aa01eb6cf50b36dc65438e4a38073d2f6`，由 `linux-debug-retry.sh:23` 的 git archive 创建独立副本；没有回退当前实现。实际生产国内数据库经 `database-timezone-readonly.py:7` 的 `BEGIN READ ONLY; SELECT ...; ROLLBACK` 核查，`database-timezone-readonly.log` 成功返回：

```json
{"serverVersion" : "16.15 (Debian 16.15-1.pgdg13+2)", "timezone" : "Etc/UTC"}
```

首次 SSH 超时没有当作成功；以上是之后只读重试的结果。此次仅查询版本/时区，没有修改生产数据库配置或执行发布。隔离 PG 为 18.6，和生产 16.15 的主版本不同；本结论是本地开发回归，不是生产镜像安装验证。

读取 `linux-utc-full.log`、`linux-utc-records-pg.log`、`linux-utc-status.log`、`linux-utc-cleanup.log` 后确认原始结果：

```text
2394 passed, 24 skipped, 10 warnings in 356.50s (0:05:56)
6 passed, 2 warnings in 3.47s
full_exit_code=0
records_pg_exit_code=0
cleanup_started exit_code=0
waiting for server to shut down.... done
server stopped
temporary_postmaster_stopped=true
temporary_runtime_and_baseline_removed=true
```

10 条 warnings 为现有依赖弃用提示及测试运行身份警告，未被当作生产运行配置；24 项跳过边界见前文。本轮 PG 筛选合同及 Linux/POSIX 分支有真实执行证据，Windows 初始的宿主限制没有用 skip 冒充通过。

最终 `review-status` 原始关键字段：

```json
{"currentId":"e40dcd0f8dd9823e4cbb5752a2a4ed376c19f61c6a2365f7ec39b7e42537be5d","reviewedId":"988ae6ca74d386a5b7102a8c4881be90ff79295d9237aaf8a3e896a17f9961cf","approved":false}
```

`approved:false` 是主 Agent 尚未登记本次新凭据，不是 reviewer 擅自批准。报告结论绑定 currentId，不能用于后续代码变更。至此本轮两阶段均 PASS；旧东八区超大 Retry-After 问题已定位但未修复，生产未部署、生产安装镜像未验收，用户要求的停止边界不变。
