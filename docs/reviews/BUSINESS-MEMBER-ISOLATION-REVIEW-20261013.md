# 国内与海外成员隔离整改：独立两阶段审查

- 审查日期：2026-10-13；reviewer：独立 code-reviewer。
- candidateId：`a527f5b1b6eef7553b8d6699408ad6ac980c22a580eaa2831d197fbf575e0bd1`。
- 基线 HEAD：`0f653b9e2850a201af90dfe61247dbf80959914d`。
- **Stage 1：PASS。Stage 2：PASS。** 未发现本轮需要修复的 HIGH / MEDIUM 问题。
- 范围：基线以上本轮全部已跟踪差异与未跟踪文件；身份服务、双业务认证/申请/成员管理、0028/0014迁移、前端入口及成员页面、维护工具、测试与隔离联调设施。共114个新增/修改代码文件，逐文件清单/行数/摘要保存于 `output/member-review-file-inventory.json`。
- 本报告仅批准本地实现快照。未审查生产具体人员归属，未执行生产部署或名单清理。源合同明确将这些操作留在本轮之外。

下文 `backend/`、`frontend/`、`infra/` 路径均相对仓库中的 `hengxin-smart-image/`；`scripts/`、`docs/`、`output/` 相对仓库根目录。结论依据源码、测试前提、原始日志及实际渲染截图，未把主Agent的口头声明当作验收证据。

## 快照与源文档

已自行读取 `.agents/skills/code-review/SKILL.md`、`.codex/agents/code-reviewer.toml`、`docs/HARNESS-REVIEW.md`，以及以下当前合同：

| 原文 | 审查结论 |
|---|---|
| `docs/BUSINESS-MEMBER-ISOLATION-PLAN-20261013.md:5` 至第10节 | 第1–10节完整纳入；其中第2节是旧行为证据，第5/8节的生产操作不是本轮已执行事项。 |
| `Product-Spec.md:1075`、`DEV-PLAN.md:1` | 最新授权覆盖前一段“方案待确认”；两边整改均在范围内。 |
| `Design-Brief.md:189` | 沿用既有Art/Element页面、三目录、明确申请、审批确认及身份恢复。 |
| `docs/OVERSEAS-PHASE17-CONTRACT.md:1`、`docs/OVERSEAS-PHASE18-CONTRACT.md:1` | 开头覆盖条款明确替代旧自动建档、双边兑换等约定，不把旧历史条款当成当前目标。 |
| `docs/BUSINESS-MEMBER-ISOLATION-VALIDATION-20261013.md:1` | 本地验证、发布准备及生产未执行边界已说明；逐一抽查实际日志和验证代码。 |

审查开始时 `review-status` 曾返回 `f367f5eeb7d8465e7a38b089d13eb7a35fe6423dd16f09f02e4a92905e485f89`，已立即告知主Agent。浏览器/构建运行生成了自动导入文件差异；主Agent停止Vite并恢复自动生成差异后，reviewer重新执行 `review-status`，当前编号恢复为上述原送审编号。没有用旧结论覆盖漂移版本。本报告不写 `.needs-review`，不自行登记批准；由主Agent对该同一编号执行 `review-approve`。

## Stage 1：Spec Compliance — PASS

### 完整实现：合同逐项对照

| 合同条目 | 结论、源码位置与行为证据 |
|---|---|
| §1 共享企业认证、业务关系独立，合法双边成员保留 | ✅ `backend/app/modules/auth/membership.py:13`、`backend/app/overseas/auth/identity.py:8` 均按本库企业ID+provider_user_id查询；共享层没有“国内存在则海外排除”判断。`infra/identity-test/membership_checks.py:61` 对both/domestic/overseas/neither逐一比较两库完整身份相关行。 |
| §1 登录/选择/刷新/切换/恢复不自动申请或建人 | ✅ `frontend/src/views/auth/IdentityPortal.vue:64` 调用两个access，`frontend/src/api/identity/auth.ts:22` 对接access接口；申请只在显式确认后发生（`IdentityPortal.vue:138`）。`backend/tests/test_membership_applications.py:13` 拦截INSERT/UPDATE/DELETE并比较完整快照。 |
| §3.1 已授权启用可进入、只为所选业务发会话 | ✅ `IdentityPortal.vue:122` 只调用所选business的session；`backend/app/modules/auth/identity_bridge.py:18`、`backend/app/overseas/auth/router.py:35` 各自发cookie。`membership_checks.py:61` 验证另一库完全不变，真实浏览器断言管理员仅一次session调用（`frontend/tests/member-isolation-real.browser.mjs:145`附近）。 |
| §3.1 未加入入口禁用、明确申请目标业务 | ✅ `frontend/src/views/auth/BusinessEntry.vue:7`、`:15` 展示禁用入口和本业务申请；`IdentityPortal.vue:145` 确认目标业务，API仅提交票据；没有姓名/部门/角色自填字段。真实浏览器两边各执行申请。 |
| §3.1 待审批、本人撤回、不发业务会话 | ✅ `backend/app/membership/service.py:61` 仅写Application/Event；`:89` 只撤回匹配企业身份的pending；`BusinessEntry.vue:16` 提供撤回。`backend/tests/test_membership_applications.py:57` 验证重复提交/撤回事件，`:140` 验证另一身份不能撤回。 |
| §3.1 拒绝可重申，显示真实拒绝结果 | ✅ `service.py:78` 复用申请ID、增加version并保留事件；`BusinessEntry.vue:14` 显示服务端reason。`test_membership_applications.py:77` 及真实浏览器覆盖拒绝→重申→批准。 |
| §3.1 停用/撤权不能自行恢复 | ✅ `service.py:35` 将enrolled但未授权人员视为disabled，`:64` 拒绝申请；双adapter `enroll` 拒绝disabled/enrolled旁路。`test_membership_applications.py:131` 覆盖disabled、有成员但无角色、pending已归属三种情况且快照不变。 |
| §3.1 查询失败单独重试，不伪装无权限 | ✅ `frontend/src/api/identity/auth.ts:26` 区分401与error；`BusinessEntry.vue:17`、`:25` 显示连接失败与重试；`output/member-unified-identity-faults.log:1` 的503/退出失败重试与对应脚本分支匹配。 |
| §3.1 同身份恢复复用会话、保留草稿 | ✅ `frontend/src/api/identity/revalidate.ts:13` 去重并核对身份→业务/me→身份，未兑换票据；`IdentityPortal.vue:2` 以member.id保持组件，`:54` 重验期锁定body包含teleport弹层。`frontend/tests/identity-portal-lifecycle.test.ts:28` 实际编译SFC，断言无卸载、草稿保留及故障清理。 |
| §3.1 直接打开海外地址不得替用户申请 | ✅ `IdentityPortal.vue:87` 只有allowed才恢复/建立已选海外会话，未知状态回入口；没有自动apply路径。`frontend/tests/member-isolation-real.browser.mjs:11` 在选择页收集POST并断言无session/application。 |
| §3.2 成员、申请、历史待核对分离，列表/总数同过滤 | ✅ 国内 `backend/app/modules/auth/management_router.py:31`、`:63`，海外 `backend/app/overseas/members/service.py:46`，申请 `backend/app/membership/service.py:106` 各用同一filters计算count与rows。两页面 `users.vue:6`、`OverseasMembers.vue:8` 独立tab/query。`test_membership_applications.py:106`、`:207` 与真实浏览器校验人数。 |
| §3.2 本业务管理员批准并选择合法角色、拒绝不建人 | ✅ `backend/app/membership/routes.py:32`、`:39` 接本业务admin；`service.py:118` 锁内重验admin/申请状态/version/角色。只有approve调用adapter.enroll。`test_membership_applications.py:77` 覆盖非法角色、旧版本、重复处理；`:154` 注入审计失败后全库快照回滚。 |
| §3.2 已批准不能由申请人撤回成员资格 | ✅ `service.py:96` 仅pending可撤回；批准/重申重复返回409。`test_membership_applications.py:77` 逐项断言。 |
| §3.2 国内/海外管理员互不继承，海外单角色 | ✅ 两个 `application_router.py:5` 采用各自权限依赖；海外 `members/membership.py:17` 与 `service.py:70` 复用现行能力及单角色写入。`membership_checks.py:163` 验证跨业务管理401；Phase18实际HTTP验证多角色422。 |
| §4.1 access/session/application接口分离、查询零业务写入 | ✅ `backend/app/membership/routes.py:16`、`:20`、`:25` 明确指定用途；`service.py:45` 在no_autoflush中仅查询，不更新资料/last_login、不撤销/签发会话。独立复跑测试验证改姓名也不落库；HTTP快照覆盖成员/身份/角色/会话/申请/事件/审计行。 |
| §4.2 票据业务+用途绑定、一次性/重放/旧票拒绝 | ✅ `backend/app/identity/store.py:57`、`:63` 使用business+purpose命名空间和GETDEL；`router.py:148` 根据service key确定业务。`test_identity_ticket_purposes.py:15` 覆盖双业务×三用途、4并发只成功一次；`:32` 验证旧无用途键不可兑换。 |
| §4.2 身份来自服务端，不接受前端冒填 | ✅ `backend/app/core/browser_auth.py:12` 只接受ticket且extra forbid；`membership/routes.py:22` 将兑换断言member交服务；两adapter稳定ID查询。`test_membership_applications.py:140` 伪造name/role返回422，缺少防伪头403。 |
| §4.2 session最新权限、失败仍撤旧业务会话 | ✅ 国内 `identity_bridge.py:22`、海外 `auth/router.py:39` 都先取权限写锁、撤销previous，再查当前本库权限；未加入失败提交仅保留旧会话撤销。`test_membership_applications.py:39` 验证未知人零建档及旧会话失效；国内旧容器路径另有 `test_dingtalk_auth.py:252`。 |
| §4.2 同名/换号/跨标签/过期响应不串人 | ✅ `/me`返回sessionId（`identity/router.py:83`），业务DTO回传identitySessionId；`IdentityPortal.vue:85`、`:97`、`:131` 比较稳定会话ID并检查generation；`revalidate.ts:26` 前后核验。真实两个同名provider账户换号、旧页面清除且无新增session，见浏览器脚本后半段和原始日志。 |
| §4.2 全局退出与单业务退出/停用边界保留 | ✅ `frontend/src/api/identity/auth.ts:36` 先全局退出，再逐业务退出；`backend/app/modules/auth/dependencies.py:29`、`backend/app/overseas/auth/dependencies.py:29` 每请求校验统一身份有效。国内 `management_router.py:114`、海外 `members/service.py:80` 只撤销各自会话。`output/member-final-http.log` 中Phase17退出/停用/过期/服务不可用用例通过。 |
| §4.3 各库独立申请表、身份唯一、历史事件 | ✅ 国内/海外各 `application_models.py:11` 唯一约束corp_id+provider_user_id；`membership/models.py:10` 存身份/状态/version/时间，Event保留操作者和前后状态。withdraw/reject重申沿用ID并追加事件。 |
| §4.3 重复/并发首次提交幂等 | ✅ `service.py:62` 业务级事务锁后再查；pending返回原记录。reviewer独立对两边各8连接同时首次提交，结果均同ID/version=1、仅1申请和1 submit事件、0成员/身份/角色/session；详见本报告独立运行证据。 |
| §4.3 国内所有旧入口禁止普通人隐式建档 | ✅ `backend/app/modules/auth/dingtalk_members.py:45` 共用认证函数不为普通未知用户创建记录；网页回调 `router.py:78`、容器 `router.py:106`、统一兑换 `identity_bridge.py:27` 都经过此函数。`test_dingtalk_auth.py:96`、`:153`、`:252` 与bridge测试证明新行为。 |
| §4.3 国内显式初始化例外、查询不初始化 | ✅ `dingtalk_members.py:53` 同时校验配置企业和配置provider ID，仅identity不存在时bootstrap并审计；已有停用用户不再提权。`test_dingtalk_auth.py:109` 先access断言未建档后显式登录开通；`:270` 验证停用不恢复。 |
| §4.3 海外初始化必须已有主动申请、不重复提权 | ✅ `backend/app/overseas/members/bootstrap.py:14` 明确企业/人员配置、已有bootstrap审计和有效管理员保护，`:35` 查询pending申请；在同事务enroll+事件。`test_overseas_members_bootstrap.py:14`、`:46`、`test_overseas_members_postgres.py:120` 覆盖幂等/降权/并发。 |
| §4.3 既有成员保留、legacy必须申请审批才能复用原ID | ✅ 两个enroll查稳定身份后更新原记录，不按姓名建人；国内 `management_router.py:97`、海外 `members/service.py:95` 拒绝普通编辑legacy。`test_membership_applications.py:106` 和 `membership_checks.py:142` 验证原ID保留及目录移转。 |
| §5 历史只读报告、按证据分类、禁止pending一刀切 | ✅ `scripts/maintenance/member_audit.py:45` 输出身份/授权/会话/申请/业务引用摘要，不凭姓名/另一业务存在推断；`:63` 至`:76` 任何授权、会话、申请、引用均排除清理。`test_member_maintenance.py:63`、`:162` 覆盖新增引用与同名不同人。 |
| §5 legacy归属迁移独立、可回退、保留原数据 | ✅ 国内0028、海外0014各 `upgrade():24` 增加归属列与独立表，仅旧pending标legacy，其余enrolled；不删除成员/业务表。`backend/tests/test_membership_migrations.py:14` 对前一版本真实PG升级→回退→再升级，逐行核对历史ID与全部原字段。 |
| §5 明确业务+审核名单才能写，完整快照复核 | ✅ `member_cli.py:18` 强制business和URL环境变量，默认不apply；`member_reconcile.py:13` 要求审核者/原因/业务指纹/具体ID和expected全字段，`:64` 每ID重新比较完整快照和引用。`test_member_cli.py:23` 覆盖CLI默认模拟及执行链。 |
| §5 新角色/业务引用并发出现时跳过 | ✅ `member_catalog.py:124` 锁相关表，`member_reconcile.py:40` 锁后重建目录并校验schema/inventory，随后查最新记录；`tests/test_member_postgres.py:56` 用真实竞争事务测试roles/applications/archives三类在等待期间提交，全部跳过。跨schema任意FK保护见`:84`。 |
| §5 恢复资料先持久化、删除幂等、恢复不覆盖/不提权 | ✅ `member_reconcile.py:51` 先保存typed snapshot及摘要，`member_codec.py:67` fsync文件及目录，才删除；`member_restore.py:11`、`:30` 校验完整性/原ID/来源/权限状态，禁止覆盖或复用已占身份。独立复跑SQLite/PG round trip和磁盘故障回滚通过。 |
| §6 步骤交付和未执行部分边界 | ✅ 文档、共享后端、双前端、维护工具、迁移和综合验收都存在；生产历史人员核对没有冒称完成。证据入口 `docs/BUSINESS-MEMBER-ISOLATION-VALIDATION-20261013.md:1`，本报告亦限定本地。 |
| §8 同步发布、旧协议不降级建档、隔离回退准备 | ✅ `test_identity_ticket_purposes.py:32` 证明旧无用途票据拒绝；发布准备说明规定四服务同版本、备份副本迁移与保留隔离的回退，不直接降级删除有新业务数据的表。迁移结构回退已有本地测试，不据此声称生产恢复完成。 |
| §9 文档同步、保留历史上下文 | ✅ Spec最新授权段、DEV-PLAN顶部、Brief末尾与Phase17/18开头覆盖条款一致（上方源文档表）。 |
| §10 access状态/DTO、申请/撤回DTO、管理查询、审批参数 | ✅ `membership/service.py:17`、`:35`，`membership/routes.py:32`，`membership/schemas.py:9`：六业务状态、身份会话DTO、独立分页、search≤100、version正整数、角色合法、拒绝原因trim必填≤1000。`test_membership_applications.py:207`、`:222` 验证通配符转义/计数及原因边界。 |
| §10 expectedSessionId签票时检查，封住/me→ticket换号窗口 | ✅ `identity/router.py:134` 在签发前比较当前cookie记录；`frontend/src/api/identity/auth.ts:17` 传当前确认ID。`test_identity_ticket_purposes.py:90` 对三用途验证401且Redis票据集合不变、旧票换号后不可用；浏览器只延迟真实/me，真实签票401且没有业务申请/session请求。 |

### §7 必须通过的验收矩阵

| 场景 | 验证结论与直接证据 |
|---|---|
| 仅国内授权进入国内 | ✅ 两库快照+另一库不变，`infra/identity-test/membership_checks.py:61`。 |
| 仅海外授权进入海外 | ✅ 同上四身份组合，`:61`。 |
| 双边授权只进入国内 | ✅ 双边原成员保留、仅国内会话变化，`:72`。 |
| 两边均未加入，仅完成认证 | ✅ repeated access全行零写入、双方/me401，`:63`。 |
| 主动海外申请 | ✅ 仅海外申请，正式成员总数不变、session403，`:82`。 |
| 批准/拒绝/撤回/重复/并发 | ✅ `:82` 真实并发审批200/409；`backend/tests/test_membership_applications.py:154` 失败回滚；reviewer并发首次提交补验通过。 |
| 双向跨业务管理员访问 | ✅ 双向401，`:163`；没有将一个员工分别获两边权限视为越权。 |
| 旧钉钉入口/容器/直接海外/旧session | ✅ `test_dingtalk_auth.py:96`、`:153`、`:252`，`test_membership_applications.py:39`，`IdentityPortal.vue:87`。 |
| 刷新/恢复/切换/故障/重放 | ✅ `identity-portal-lifecycle.test.ts:28`、`test_identity_ticket_purposes.py:15`，真实浏览器POST调用计数。 |
| 同名员工/A→B/跨标签退出换号 | ✅ `member-isolation-real.browser.mjs` 的真实同名和/me竞态两段；原始结果 `output/member-frontend-browser.log:4`。 |
| 停用/撤权旧会话与自助申请 | ✅ `membership_checks.py:114`、`test_membership_applications.py:131`；旧会话拒绝且另一库不变。 |
| 历史未知pending | ✅ `test_membership_migrations.py:14`、`membership_checks.py:142`；无自动申请、默认成员目录不计数。 |
| 执行前新增角色/业务引用 | ✅ `scripts/maintenance/tests/test_member_postgres.py:56` 真实等待后复查并跳过。 |
| 初始与最后管理员 | ✅ `test_overseas_members_postgres.py:66`、`:120`，`test_dingtalk_auth.py:109`；国内 `management_router.py:103` 和海外 `members/service.py:99` 同事务锁保护最后管理员。 |

部分实现、未实现：本轮授权交付范围内未发现。未授权生产部署/名单处理及真实企业钉钉上线验收单独保留，不记成已交付，也不作为本地实现缺陷。Stage 1无HIGH后才进行以下Stage 2。

## Stage 2：Code Quality — PASS

| 维度 | 结论与证据 |
|---|---|
| 文件/职责 | ✅ 114个本轮源文件均≤300行，最大 `infra/identity-test/checks.py:297`。公共申请状态机与业务adapter分离，国内管理路由从auth路由拆出；维护工具按catalog/audit/reconcile/restore/CLI分工。清单见 `output/member-review-file-inventory.json`。 |
| 类型/契约 | ✅ 新增TS没有显式any；`frontend/src/api/identity/applications.ts:17`/`:24` 对DTO与页结构守卫，入参schema拒绝额外字段；独立 `pnpm typecheck` exit0。Python动态adapter模式统一使用两个已核对实现。 |
| 事务/故障 | ✅ `backend/app/membership/service.py:118` 权限与版本在锁内，成员/角色/申请/审计同commit；失败测试在真实服务逻辑上注入Event写失败后核对整个快照，未只断言HTTP错误。维护恢复包写失败确保删除回滚（`test_member_maintenance.py:149`）。 |
| 测试真实性 | ✅ 单测使用真实SFC编译与服务调用；IO替身不承担业务结论。双库HTTP使用真实PG/Redis/三API，身份提供方是明确隔离测试stub。浏览器换号用不同provider真实cookie；竞态仅延迟/me，不伪造签票401。旧Phase18/19改为当前单角色/超级管理员矩阵，并保留精确版本、审计增量、任务事件/outbox/request断言（`infra/identity-test/phase18_checks.py:62`、`phase19_checks.py:124`）。 |
| 引导/错误交互 | ✅ `MembershipApplications.vue:57` 合法角色/拒绝原因/二次确认；409只能刷新后再审；401/403清rows和敏感弹窗（`:42`）。两目录切换清旧行并用generation拒绝迟到响应（国内`:38`、海外`:66`）；网络故障保留可重试页面但清数据。 |
| 安全扫描 | ✅ 本轮扫描未发现硬编码真实密钥、前端密钥变量、eval/innerHTML/dangerouslySetInnerHTML、用户值拼接SQL。命中的凭据均为隔离测试常量；维护SQL标识符经dialect formatter引用（`member_catalog.py:126`），业务值参数化。 |
| 测试专用动态执行 | ✅ `frontend/tests/membership-test-harness.ts:24` 的new Function只编译仓库SFC、依赖严格白名单；`scripts/maintenance/tests/test_member_model_contract.py:32` 的exec只执行从本地迁移AST筛出的imports。均不进入产品执行路径、不接收远端内容。 |
| 维护敏感信息与安全边界 | ✅ `member_cli.py:50` 捕捉异常不输出URL/数据库参数；`member_audit.py:45` 不导出session/token值；`member_codec.py:53` 递归拒绝凭据列，`member_restore.py:25` 保证恢复仍是无权限legacy。真实CLI脱敏、嵌套凭据及跨schema引用测试均通过。 |
| Spec漂移 | ✅ 新增页面组件、API、申请/事件/国内审计表、directory_state均有§4/5/10条款；没有新第三方依赖或第二套认证。既有browser fixture仅调整新身份DTO/用途，不声称所有这些历史浏览器脚本本轮都运行。 |

### 实际视觉对比

已打开并逐张查看旧邻居渲染 `output/css-hotfix-production-members.jpg`，以及本轮 `output/playwright/member-isolation/` 中两个业务的 `applications.png`、`mobile.png`、`approval-mobile.png`、`entry-mobile.png` 共8张稳定截图，未操作生产页面。对应桌面1366×900、窄屏390×844。

- ✅ 既有侧栏、页签栏、标题、浅底白卡、蓝色操作按钮及表格分隔线保持一致；本轮增加的三目录页签和审批字段是授权变化。来源 `frontend/src/views/overseas/admin/OverseasMembers.vue:2`、`frontend/src/views/hengxin/admin/users.vue:4`；共用样式 `frontend/src/views/hengxin/prototype.css:26`（filter gap18px、wrap）、`:43`（h2 17px）、`:65`（筛选下间距20px），没有新增布局框架。
- ✅ 两业务申请表沿用ArtTable，窄屏内容在表内部横向滚动；刷新按钮、分页、审批按钮可滚入视野，无整页横向溢出。浏览器 `member-isolation-real.browser.mjs:27` 的unclipped检查同时验证祖先overflow裁切，不只量viewport。
- ✅ 审批弹窗 `MembershipApplications.vue:17` 为 `min(480px,94vw)`；390px截图中申请人、单选角色、错误提示、取消/确认完整可见。申请人只读、无部门输入。
- ✅ 入口两个业务卡及申请/撤回按钮在窄屏完整可见；错误/拒绝/停用文案由状态决定（`BusinessEntry.vue:25`），页面无模拟角色开关。无独立新设计稿，本项以最新Brief与邻居既有风格为准，不声称与旧截图业务文案逐字相同。

### 编译及运行：原始输出

reviewer独立运行，未修改产品代码：

```text
# backend cwd，TEST_IDENTITY_REDIS_URL 指向主Agent指定隔离Redis
.venv/Scripts/python.exe -m pytest tests/test_membership_applications.py tests/test_identity_ticket_purposes.py tests/test_identity_service.py tests/test_identity_client.py -q --tb=short
............................................................             [100%]
60 passed, 2 warnings in 7.81s
exit_code: 0

# 仓库根目录，TEST_MEMBER_MAINTENANCE_DATABASE_URL 指向 membership_audit_test
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/maintenance/tests -q --tb=short
60 passed, 1 skipped in 19.07s
exit_code: 0

# frontend cwd
pnpm typecheck
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.28 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
exit_code: 0

# 本轮身份/申请/成员及维护模块 compileall -q
stdout: （空）
exit_code: 0
```

两项后端警告为既有Starlette/httpx/anyio弃用提示；维护唯一skip是海外没有国内独立identity表的非适用分支（`scripts/maintenance/tests/test_member_maintenance.py:123`）。PG10项全部执行，未将环境缺失跳过当通过。`git diff --check` exit0，只有工作区CRLF→LF提示。

reviewer补做并发首次申请：用给定 `membership_audit_test`，每业务随机schema、8个真实独立PG连接，结束后DROP各自随机schema；可复现命令：

```powershell
# TEST_MEMBER_MAINTENANCE_DATABASE_URL 须显式设置为隔离 *_test 数据库，脚本再次限制允许库名。
& hengxin-smart-image/backend/.venv/Scripts/python.exe output/member-review-concurrency.py
```

脚本 `output/member-review-concurrency.py:1`，原始日志 `output/member-review-concurrency.log:1`：

```text
PASS domestic: 8 concurrent first submissions; identical application id/version=1; 1 application; 1 submit event; 0 members/identities/roles/sessions
CLEANED review_member_849be4754b8944a4a3e5bdb7efabf3f3
PASS overseas: 8 concurrent first submissions; identical application id/version=1; 1 application; 1 submit event; 0 members/identities/roles/sessions
CLEANED review_member_37eb26f2e5834176b9ea7c4891f214de
```

主Agent已运行且reviewer打开核对的原始日志摘要（没有把这些写为reviewer重跑）：

```text
# output/member-linux-pytest.log:61
2151 passed, 17 skipped, 15 warnings in 465.24s (0:07:45)
CLEANED hx-overseas-regression-d4bb5ebf0fc9

# output/member-frontend-tests.log 最后8行
ℹ tests 335
ℹ suites 0
ℹ pass 335
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8722.728

# output/member-frontend-build.log 最后一行
✓ built in 35.99s
# output/member-frontend-preview-build.log 最后一行
✓ built in 35.51s

# output/member-final-http.log
PASS both DBs unchanged by repeated access; only selected business creates sessions
PASS domestic apply/withdraw/reject/reapply/concurrent approval/disabled and opposite DB unchanged
PASS domestic legacy excluded until explicit application/approval, stable member ID retained
PASS overseas apply/withdraw/reject/reapply/concurrent approval/disabled and opposite DB unchanged
PASS overseas legacy excluded until explicit application/approval, stable member ID retained
PASS independent admin roles and operation-bound tickets
PASS ALL member isolation real HTTP integration

# output/member-phase19-http.log
PASS ALL Phase 19 real HTTP integration
```

Linux全套17个跳过按主Agent验收说明为既有root/Bubblewrap技能权限及WSL条件，本报告不把它们计为已执行。本轮身份竞争窗口后续增量另有32项日志且已包含在reviewer独立60项复跑中。

浏览器原始输出（`output/member-frontend-browser.log:1`）：

```text
[
  "海外：只读选择、明确申请撤回、角色审批、拒绝重申、独立计数、待核对只读、390px PASS",
  "国内：只读选择、明确申请撤回、角色审批、拒绝重申、独立计数、待核对只读、390px PASS",
  "同名换号：实际不同provider身份、旧业务页清除、双边仍未加入、恢复无会话兑换 PASS",
  "申请确认后/me与票据之间换号：真实票据401，业务申请与会话HTTP零调用 PASS"
]
```

另核对 `output/member-unified-identity-real.log:1` 四种授权组合、`output/member-unified-identity-faults.log:1` 与 `output/member-overseas-members-faults.log:1` 故障结果。后者沿用旧日志标题“多角色”，实际脚本与后端现行单角色合同核对，不据标题推断支持多角色。

## 交接结论

本轮本地实现两阶段均PASS，批准对象仅为报告顶部candidateId。最终快照必须再次匹配后由主Agent登记凭据。生产部署、真实企业钉钉验收与历史人员审核清理仍未执行；此前截图中具体人员是否误建不属于本报告的已核实结论。
