# 消息署名时间与海外合并发布候选审查

- 执行者：独立 code-reviewer；日期：2026-11-02；使用 `.agents/skills/code-review/SKILL.md`，遵守 `docs/HARNESS-REVIEW.md:5` 的快照凭据协议。
- 初始 candidateId：`543f27d7f17466f9eb5d417e4b86598535a6ef2fd7d61e3f3f1dc2470f0c554b`。
- 中间 candidateId：`1aaa148f7ad1f14d61bb0c59ccdb808b55c0817f3d10901108b0a23153419ccb`。
- 最终送审 candidateId：`8b5a21f941a81d665380b2e7d04f02b0fc639304b003d6c7dba9555ddf021935`。
- 最终结论：**Stage 1 PASS / Stage 2 PASS**，只适用于上述最终候选。当前 HIGH 0、MEDIUM 0；本轮发现的2项MEDIUM已修复并复验。生产执行和线上验收仍由主Agent继续，不由本报告代替。
- 范围：本轮全部累积需求及发布整合；相对已批准 `b79034980d927ef5a919ac073b3ae96c9e4fe1c99a264b2001c1f639f85ff554` 的 22 个代码/测试/发布文件增量。包括消息元数据、原生新增文件安装、17 文件 API 白名单、隔离 PG 启动修复和4个旧工作台测试对齐；核对三角色、字段/历史兼容、五人授权、OUTON 完整包及生产保护。
- 源文档：`Product-Spec.md:1364`、`:1379`、`:1382`，`DEV-PLAN.md:1587`、`:1599`，`Design-Brief.md:226`、`:230`，`docs/STUDIO-MESSAGE-METADATA-20261102.md:3`、`:7`。最新明确授权恢复提交及部署，覆盖旧文档/报告中的暂停描述。

下文 `backend/`、`frontend/`、`infra/` 均相对 `hengxin-smart-image/`。私人 UUID 不复制到报告。

## 快照及复用边界

开始时 `review-status` 返回初始候选；审查发现隔离 PG readiness 存在竞态后，主 Agent 修改 `scripts/release/outon-deploy.py:116`、`outon-database.py:58` 及 `test_outon_safety.py:122`，重新固定最终候选。已重新从 Stage 1 核对这些变化及累积合同，不将初始结论直接批准新代码。

完整 Linux 回归随后发现4个旧工作台测试模块的14项断言/fixture不符合当前批准合同。主Agent仅修改这4个测试，发布安装测试同时补入4模块并将有界超时从240秒调整到600秒，产生最终 `8b5a...` 候选。reviewer再次从 Stage 1 复核；未修改业务实现以迁就旧断言，详细失败与修复证据见下文。

读取 `.codex/review-state.json` 中已批准文件摘要与最终候选，差异精确为 22 文件。其余代码与旧批准快照相同；继承 `docs/reviews/WORKFLOW-COLLABORATORS-20261102.md:1` 和 `docs/reviews/DESIGNER-ONLY-20261102.md:1` 的逐项证据，同时重新抽查集中授权、表单、兼容写入、迁移与完整发布链路。本报告覆盖当前完整累积范围，不要求把未变化功能从头重复验证。

## Stage 1：Spec Compliance — PASS

### 完整实现：消息合同逐条核对

| 合同条目 | 代码证据 | 验证及结论 |
|---|---|---|
| 实际发送人取 Turn.actor_id，不取查看人、创建人或负责设计 | `backend/app/overseas/studio/message_metadata.py:19` 批量查询 Member；`studio/queries.py:128` 返回原 actor_id 和关联姓名 | `backend/tests/test_studio_message_metadata.py:52` 真实 HTTP 两个发送人、第三人查看及姓名更新；组件/浏览器分别展示，完整实现 |
| 姓名缺失/空白诚实降级 | `message_metadata.py:19` 空白归 null；`frontend/src/views/overseas/studio/StudioTurns.vue:6` 显示未知操作人 | 后端 `test_studio_message_metadata.py:72`，前端 `tests/studio-message-metadata.test.ts:16`；缺记录模拟明确标注为 SQLite 损坏历史 FK，不冒充 PG 正常可写输入 |
| 用户发送时间为该轮真实 created_at | `studio/queries.py:129`，`message_metadata.py:8` | 后端 `test_studio_message_metadata.py:98`、`:136` 断言精确值和归档后不漂移；无当前时间替代 |
| reply 有值取内容匹配的最近公开 message；重复文本按 ID 顺序 | `message_metadata.py:22` 仅 kind=message、文本相等，`:25` ID 降序、`:28` 每轮取首条 | `test_studio_message_metadata.py:86` 两次相同文本、更新的不同文本和 reasoning 干扰均覆盖；不使用 updated_at |
| reply 为空取最后公开 message，包括运行中过程组 | `message_metadata.py:24` 接受 null/空 reply；`:35` 使用最新公开文本；前端 `StudioTurns.vue:47` 与既有 `studio-process.ts:3` 的显示规则一致 | 后端 `test_studio_message_metadata.py:121` 三状态×三种 reply 共 9 组；组件测试 `studio-message-metadata.test.ts:35` 验证运行中 message 出现后时间显示 |
| 历史仅真实 completed_at 回退并标“完成于” | `message_metadata.py:41`；`StudioTurns.vue:49`、`:50` | 后端 `test_studio_message_metadata.py:103` 覆盖成功、失败、运行、空回复、缺完成时间；组件 `:27` 精确断言“完成于” |
| 缺真实时间显示“时间未记录”，尚无回复不虚构回复时间 | `message_metadata.py:36`、`:40`、`:42`；`StudioTurns.vue:48` | 组件测试 `:28`、`:39`、`:46` 覆盖未知/无回复/畸形时间；浏览器运行中无回复只有状态，完成刷新后才新增时间 |
| DTO actor/replyAt/replyTimeSource，兼容旧接口缺字段 | `frontend/src/api/overseas/studio.ts:9`、`:47`；`studio/queries.py:128` | `tests/studio-message-metadata.test.ts:53` 接受缺字段/null，拒绝错误类型及未知来源；actor 缺失时不借用当前登录人 |
| 输出明确时区，旧 naive 按 UTC；前端统一北京时间 | `message_metadata.py:12` 对 aware 使用 astimezone；`StudioTurns.vue:26` 复用 `frontend/src/utils/beijing-time.ts:2` | 后端 UTC/带偏移分支 `test_studio_message_metadata.py:159`；真实 PG 用例 `test_studio_message_metadata_postgres.py:15`；浏览器显式 America/Los_Angeles，1366/390 均显示北京时间 |
| 保持内容、过程、滚动、附件图片、只读与五人权限 | `StudioTurns.vue:8` 至 `:18` 原组件与操作保留，`:52` 滚动逻辑保留；`studio/queries.py:98` 先 access；`message_metadata.py:23` 仅查已授权轮次 | 浏览器只读输入禁用、刷新/换查看人，邻居工作台核心交互实跑；权限测试与全量回归核对整合 |
| 无新增 DB 字段或历史重写，无读取范围扩张 | `message_metadata.py:15` 只有 select；`studio/queries.py:19` 原读门禁仍执行 | 新模块无 mutation；0024 是既有三角色需求，不是消息存储改造；无新增业务 API/表/页面 |
| 长姓名窄屏换行，保持弱化文字和原布局 | `frontend/src/views/overseas/studio/studio.css:45` overflow-wrap:anywhere；small 保持 11px、灰色变量、8px间隔 | 独立打开真实最终 build，1366 和 390 下文本范围、祖先裁切、遮挡、视口全部通过；截图已实际查看 |

### 完整实现：旧范围与发布整合逐条复核

| 累积条目 | 证据及结论 |
|---|---|
| 海外三角色及旧角色迁移、国内保持 | `backend/app/overseas/auth/models.py:11`、`members/schemas.py:7`、`permissions.py:26`；`backend/migrations/overseas/versions/0024_designer_roles.py:10` 加锁、只映射旧角色并更新受影响成员版本、保留 ID/历史，`:44` 禁止降级；`frontend/src/api/identity/auth.ts:13` 国内 operator 保留。摘要与旧批准一致；旧报告对应迁移/国内隔离用例继续有效 |
| 非指定 designer、主管、超管及管理权限保持 | `permissions.py:33`、`:36`、`:39` 原三角色 scope；`:69` 仅指定 designer 扩展 task.read/design，stats/manage/reassign/delete 不扩展；旧报告完整权限矩阵与本轮独立 workflow 用例通过 |
| 五人精确稳定 UUID，身份有效才授权，不使用姓名/full_access 授权 | `permissions.py:60` 先 member_roles 验证再 UUID 命中；`scripts/release/outon-workflow.py:22` 恰好 5 个不同 UUID、active/enrolled/designer；`:58` 只读验证实际有效角色。reviewer 比对私人 binding 与生产只读证据，精确为陈妹/周仁平/胡礼辉/黄湘婷/姚锐娟 |
| 本人创建 OR 负责全流程，他人只读，私人未提交材料不扩张 | `permissions.py:69`、`:80`、`:100`、`:113` SQL/对象同源；`materials/service.py:21`、`:63` 所有权；`studio/service.py:17` 原写门禁；`studio/recovery_files.py:37` GET 读、receive 写。独立 `test_overseas_workflow_grant*.py` HTTP 回归通过；旧 report 列举逐写接口拒绝及 native 路径 |
| 管理、转派、删除、统计不扩张，撤权不能靠旧 UI 写入 | `permissions.py:26`、`:69`，`tasks/requirements.py:87`；`frontend/src/views/overseas/OverseasTasksPage.vue:154` capability 刷新；`studio/OverseasStudio.vue:17` 重试禁用。`output/message-metadata-workflow-browser.log:1` 当前版本 created/assigned 各 12 写、other 0 写及撤权刷新通过；浏览器为 mock API，不替代后端授权证据 |
| 表单顺序、多 SKU、移除 market/remarks 输入及 remarks 展示 | `frontend/src/views/overseas/OverseasCreate.vue:23`、`:44`、`:50` 精确 SKU→平台→品牌→任务名→品名→负责设计；共用重提组件 `OverseasRequirementsResubmit.vue:3`；`OverseasTaskInfo.vue:19`、`OverseasRequirementsReview.vue:8` 无补充说明。旧审查1366/390 DOM及截图逐项证据保持，独立邻居脚本再次验证无站点 |
| 历史字段保持及幂等区分省略/显式空值，四步人工审核流程保留 | `backend/app/overseas/tasks/requirements.py:16` 摘要根据 fields_set 区分；`:93` 仅显式输入赋值；`:58` 审核快照保持，`:50` 人工审核/退回；`frontend/src/api/overseas/tasks.ts:86` 新客户端不传 remarks；`types.ts:63` 四阶段。旧批准测试摘要相同 |
| OUTON 完整 51 文件，源不改，仅两份来源 JSON 适配 | `scripts/release/outon-source.py:10`、`:33`、`:47`；`docs/OUTON-SOURCE-MANIFEST-20261102.json:1`。reviewer 再次逐文件 SHA-256 核对原目录/准备目录：各 51 文件与 manifest 精确一致，49 原字节一致，改动仅两个已登记 JSON |
| 新 Skill 未分组默认关闭，旧内容/分组/开关保持 | `scripts/release/outon-skill.py:23`、`:66`、`:85`、`:99`、`:102`；`backend/app/overseas/management/skills.py:23` 缺省 false/[]。脚本合并旧完整集合、安装前后比较全 availability，不写入新平台/开启记录。真实生产安装和双身份读验证属于后续发布验收 |
| API17 文件及 native16 文件完整、新 helper/0024 均纳入 | `scripts/release/outon-runtime.py:23`、`:28`、`:37`，`outon-baseline.py:7` 同名单；`outon-package.py:47` 从已审 commit 打包；`test_outon_release.py:59`。独立核对私人 baseline 恰好17项、0.2.57，null 恰好新 helper 和0024；native仅16个 app 文件 |
| 原生新文件 baseline=None 安全安装/备份，其他文件和业务保护 | `scripts/release/outon-native.py:43` guard兼容尚未安装/部分已装新文件，安装凭据后强制存在；`:185` 新路径必须不存在且父目录存在，旧文件先备份；`:201` 继承权限/原子替换并实际身份编译。`test_outon_native.py:126`、`:140`、`:153`、`:160`、`:174` 覆盖首次安装/冲突/部分安装/缺失/损坏；`:68` 拒绝共享源码，`:64` 保护无关 PID |
| 实际五人配置/API与native环境一致，原管理配置不改 | `outon-workflow.py:97`绑定Hash；`:120`overlay仅image/grant；`:163`停稳后独立env/drop-in；`:180`核对进程grant及其他业务环境摘要；`:191`API校验。`outon-native.py:216`在源码后、启动前装配置，发布工具测试通过 |
| 不强杀在途任务、备份隔离恢复/迁移前门禁、恢复边界明确 | `outon-deploy.py:136`idle→停API→再次idle→pause→native正常停止；`outon-native.py:94`禁SIGKILL/无限stop，超时保留保护；`outon-database.py:46`同名隔离库恢复及两次迁移、`:134`真实备份凭据门禁；`outon-deploy.py:155`迁移开始后拒绝旧API恢复。工具故障测试通过，不声称已执行生产恢复 |
| 实际镜像测试、前端和 Skill 独立发布顺序 | `outon-deploy.py:103`实际新镜像只读/临时PG测试，`:97`失败/skip/超时不签凭据；`:182`要求迁移和native均验证再切API；`outon-frontend.py:27`静态备份与漂移保护；`outon-skill.py:103`API及降权native读取完整目录。发布制品与真实生产安装尚未执行，必须由主Agent继续取得证据 |

### 部分实现、未实现、Spec 漂移

本轮代码实施项没有缺失，没有新增合同外业务页面、API、数据库字段或其他设计人员权限。消息为已有读接口 DTO 扩展（`studio/queries.py:128`），只读两次批量查询（`message_metadata.py:15`）。

生产提交/部署/0024迁移/五人配置/OUTON安装及正式页面验收尚未执行。本报告只能批准候选代码与已完成测试，不能表示生产已经生效；最新授权已允许主 Agent 在审查通过后继续这些步骤（`docs/STUDIO-MESSAGE-METADATA-20261102.md:16`）。

## Stage 2：Code Quality — PASS

- 结构/类型：22 增量文件全部不超过300行，新增 Python 内存 compile 通过；消息时间与署名单独放入 `message_metadata.py:1`，不将身份逻辑散落前端；`studio.ts:47` 使用 unknown 守卫，未新增 any。`git -c core.safecrlf=false diff --check` 无输出、退出0。
- 性能：姓名和公开 message 各一次批量查询，按已授权轮次过滤，未新增每轮姓名/转录查询；`test_studio_message_metadata.py:170` 对3轮真实 SQL 计数精确各1。没有宣称原 view 的其他逐轮查询已被优化。
- 安全：22 文件扫描未发现危险执行、HTML注入、公开 VITE 密钥、sk-ant/sk-proj密钥、shell=True 或意外本机路径；eval唯一命中 `backend/tests/test_studio_recovery_transport.py:34` 的既有 MemoryRedis mock 方法，`:35` 先断言固定脚本，方法仅记录内存队列，不执行传入代码。新增 SQL 使用 SQLAlchemy 表达式（`message_metadata.py:22`）。发布原有动态表名/UUID在 `outon-runtime.py:84`、`:103` 严格限制；源码/包哈希、链接和文件集合检查保持（`:53`）。未扩展消息读取授权。
- 测试真实性：新增消息 HTTP 测试走真实 FastAPI 路由、Session 与模型；身份服务及执行结果是隔离 fixture，不触发收费生成。`test_studio_message_metadata_postgres.py:21` 确实替换 get_session 为真实 PG factory，实际 timestamptz 验证两个时区。SQLite 缺 FK 的历史数据用例没有被描述为 PG 正常路径。`test_studio_sessions.py:152` 的旧断言修订增加“创建者可读但写403”，再切真正无关 designer 验证读403，没有删除拒绝测试。
- 前端测试分层：组件测试 stub 掉子组件，仅证明消息头；真实浏览器使用完整正式 Vue/Element 和最终 dist，API 为受控 mock（`studio-message-metadata.browser.mjs:31`），真实验证换查看人/刷新、缺信息、非UTC浏览器、运行到完成、禁用状态和裁切。不声称浏览器与生产 API 端到端已通过；后端授权/持久化由对应 HTTP 与 PG 测试证明。
- 视觉：reviewer独立用 `127.0.0.1:3062` 最终 build 打开消息页和邻居工作台，执行两套 browser 后实际查看 `output/playwright/message-metadata/1366-finished.png`、`390-long-name.png`、`output/playwright/overseas-polish/formal-1366.png`。同一侧栏/白卡/蓝色Element按钮/三栏及窄屏展开，消息头弱化11px灰字、长名换行，没有变更气泡、输入区或折叠结构；1366姓名头520.1875×58.5px、390姓名头352×78px，范围/遮挡/裁切断言全通过（browser`:68`）。本次自行启动的preview已Ctrl+C停止。

### MEDIUM 已修复：隔离 PostgreSQL 临时服务造成假 ready

初始候选 `outon-deploy.py:116` 与 `outon-database.py:58` 默认 socket `pg_isready` 会命中首次初始化的临时服务，其随后关闭再启动正式服务；`createdb`/恢复可能随机遇到无socket，备份恢复路径是在业务已停稳后运行，会延长维护中断。该行为与 [Docker PostgreSQL 官方 entrypoint](https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh#L264) 中临时服务 `listen_addresses=''`、初始化后停止的实现一致；主 Agent 隔离 CI 已出现真实 `createdb: ... No such file or directory`。

主 Agent 已将两处 pg_isready、createdb及restore的pg_restore全部指定 `-h 127.0.0.1`（`outon-deploy.py:116`、`:121`，`outon-database.py:58`、`:64`、`:67`），避免临时socket假ready。`test_outon_safety.py:122`、`:181` 在两个真实函数执行分支断言命令；reviewer独立69项发布测试通过。新候选重新核对 Stage 1，无业务范围扩张。本问题已解决，不留作当前候选缺陷。

### MEDIUM 已修复：旧工作台测试未跟随三角色及创建者读取合同

完整B批次真实结果为14失败，不能报成通过。7项图片预览仍把创建者降为designer后的读取期待为403；另7项材料/恢复/解冻测试仍插入已删除operator/operator_manager角色，先触发数据库CHECK而没有到达原测试目标。reviewer已读取完整trace及修订，未发现因此需要改动生产权限的证据。

- `backend/tests/test_studio_image_preview.py:28` 增加创建者HEAD200、无design发送403，缺blob仍503；`:83` 验证创建者能读真实原图字节，再切真实无关designer，GET/HEAD403且不读取blob。
- `backend/tests/test_studio_material_list.py:114` 验证创建者只读、无关成员读写403；`:146` 以现行角色与无角色验证移除权限/写入计数。`:163` 多角色采用真实数据库唯一约束拒绝，验证回滚仍只有designer、权限未升级，而不是构造数据库根本不能写入的多角色成功fixture。
- `backend/tests/test_studio_recovery_transport.py:128` 明确丢失分配、无关任务、停用、无角色；`:145` API释放事务后才改变身份/归属，断言native实际消费，创建者仅available200而receive403，其余两操作403，OutputFile始终0；`:216` API拒绝时不入队。
- `backend/tests/test_studio_reopen.py:86` 仅现行三角色/无角色矩阵，额外断言创建者可读但非负责仍不能解冻及版本不变；没有删除合法角色下的拒绝覆盖。

`scripts/release/outon-runtime.py:37` 将上述4模块纳入37模块的实际镜像安装测试，依赖仍由 `outon-package.py:16` AST递归收集。`outon-deploy.py:90` 上限600秒、`:93`保留超时双流，`:97`仍拒绝失败/skip；`test_outon_release.py:25`、`:38`、`:49`验证。调整基于完整Linux538项耗362秒、另一批1047项耗485秒的工作量证据，没有取消执行时限或放宽结果标准。

## 验证原始输出与边界

reviewer 独立后端命令（backend目录）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_message_metadata.py tests/test_studio_message_metadata_postgres.py tests/test_studio_sessions.py tests/test_overseas_workflow_grant.py tests/test_overseas_workflow_grant_studio.py
54 passed, 6 skipped, 2 warnings in 15.96s
```

6条为本地Windows缺PG或POSIX能力，不能计作通过；Linux补验结果单列。2 warnings 为既有 Starlette/httpx 与 AnyIO 弃用提示。

reviewer独立发布工具：backend venv pytest运行 `scripts/release/test_outon_{release,safety,native,workflow,skill,contract}.py` 和 `test_skill_platform_release.py`：

```text
.....................................................................    [100%]
69 passed in 2.61s
```

reviewer独立类型检查退出0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.58 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

读取主 Agent 本候选前端单测 `output/message-metadata-tests.log` 及生产构建 `output/message-metadata-build.log`，未声称reviewer再次构建：

```text
ℹ tests 444
ℹ suites 0
ℹ pass 444
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9828.0674

> hengxin-smart-image-frontend@0.2.58 build
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 36.62s
```

reviewer独立真实浏览器输出：

```text
PASS message metadata real component browser [{"width":1366,"timezone":"America/Los_Angeles","headers":["Codex 已回复2026-11-02 10:03:04","Codex 已回复完成于 2026-11-02 11:04:05","Codex 已回复时间未记录","Codex 已回复时间未记录","Codex 已回复2026-11-02 12:05:06","Codex 已回复2026-11-02 13:06:07","Codex 已回复2026-11-02 14:07:08"],"bounds":{"width":520.1875,"height":58.5,"visible":true,"uncovered":true,"contained":true,"viewport":true}},{"width":390,"timezone":"America/Los_Angeles","headers":["Codex 已回复2026-11-02 10:03:04","Codex 已回复完成于 2026-11-02 11:04:05","Codex 已回复时间未记录","Codex 已回复时间未记录","Codex 已回复2026-11-02 12:05:06","Codex 已回复2026-11-02 13:06:07","Codex 已回复2026-11-02 14:07:08"],"bounds":{"width":352,"height":78,"visible":true,"uncovered":true,"contained":true,"viewport":true}}]
PASS: fixed two rows; long draft; 1920/1366 clipping; 16px/Enter/Escape/done; session drafts; completed disabled; six platforms/no site input
```

reviewer独立文件及制品证据核对输出：

```text
FIVE_UUID_BINDING_EXACT_READONLY_MATCH
API_17_NATIVE_16_BASELINE_EXACT
originalEntries 51 EXACT_HASH_PASS
entries 51 EXACT_HASH_PASS
CHANGES ['assets/brand/font-reference.json', 'assets/brand/manifest.json']
FINAL_DELTA_COMPILE_SIZE_PASS 22
ARCHIVE_VERIFIED a sources 641 tests 60
ARCHIVE_VERIFIED b sources 641 tests 71
EXACT_FULL_MODULE_SET 131
FULL_RUN_DIFF_ONLY_FOUR_REVIEWED_TESTS
REPAIR_ARCHIVE_EXACT 641 sources 10 test_modules
INSTALL_TEST_MODULES 37
```

Linux运行包A SHA256 `aff5261b62696fb1cc34cd1f442f43a8faa570e3de1d49b37cfa5ec19401192e`；B `be0dbdbece3021f77b3368f891499bec6372f4e4339c54b04221604d7abf96d8`。初次核对时每包641个app/tests/migrations/Alembic源文件与中间候选相同；131测试模块无交集，并集精确等于全部 test_overseas/test_studio模块。最终候选与两包的差异只有上述4个已审测试文件，所有业务代码相同。repair包SHA256 `ae0a54e600875c190fd3f9d8c4b99de13ee196171c8e937c9807a8987ce92191` 的641源文件与最终候选CRLF归一后全部相同，10模块包含4修订、metadata2、两项skip来源及workflow_grant2。隔离runner使用无外网临时PG、只读测试容器和仅清理本次临时资源的finally（`output/message-ci/run_batch_a.py:21`、`:34`、`:40`），这不是生产部署。

完整Linux两批原始输出，读取 `output/message-ci/run_batch_a.stdout` 和 `run_batch_b.stdout`：

```text
ISOLATED_TESTS 60
538 passed, 2 warnings in 361.93s (0:06:01)

ISOLATED_TESTS 71
14 failed, 1031 passed, 2 skipped, 2 warnings in 485.41s (0:08:05)
```

B的14失败全部位于上述4个测试模块，原始失败日志完整保留，未覆盖。它不能作为最终全量通过凭据。最终候选只改4测试及发布测试配置，生产代码与两批已测代码完全一致；reviewer已逐文件验证，未变化测试沿用原证据，受影响模块重新验证。

4模块修正后的Windows原始日志 `output/message-release/studio-fixture-alignment.log`：

```text
97 passed, 2 warnings in 26.62s
```

最终候选Linux定向10模块 `output/message-ci/run_repair.stdout`，同时覆盖4修正模块、消息SQLite/PG、两项skip来源、两组五人授权：

```text
ISOLATED_TESTS 10
SKIPPED [1] tests/test_studio_context_safety.py:142: Windows junction regression
SKIPPED [1] tests/test_studio_open_outputs.py:89: Set STUDIO_INCIDENT_FIXTURE to the preserved production record
163 passed, 2 skipped, 2 warnings in 123.86s (0:02:03)
```

新增消息PG时区、授权、4修正模块均没有skip。Windows junction已在本机实际运行，`output/message-release/windows-junction.log`：

```text
.                                                                        [100%]
1 passed in 0.50s
```

私有历史事故原记录未提供，用例明确要求 `STUDIO_INCIDENT_FIXTURE`（`backend/tests/test_studio_open_outputs.py:87`）。该单项未验证，不能声称覆盖那份真实历史事故输入；同模块其他合成回归已运行，不把它们冒充私有原记录。这个未变更、可选私有fixture用例不阻断本轮新增消息/授权/发布代码审查。没有把重叠的定向用例累加成虚构的“最终全量一次通过”数量。

最终只读 `review-status` 的 currentId 为 `8b5a21f941a81d665380b2e7d04f02b0fc639304b003d6c7dba9555ddf021935`，与最终送审编号一致。报告为普通Markdown，不改变代码快照。主Agent可为同一编号、本文路径及Stage 1/Stage 2 PASS登记review-approve；之后任何受控代码变化都须重新固定并复核。reviewer没有登记凭据、写clean、提交、部署、安装Skill或修改产品代码。
