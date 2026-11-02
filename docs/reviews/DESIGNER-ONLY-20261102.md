# 海外设计人员流程与 OUTON 合并候选审查

- 审查日期：2026-11-02；执行者：独立 code-reviewer；Skill：`.agents/skills/code-review/SKILL.md`。
- 初始 candidateId：`ff68b7aa01f66447b21bb08f6b9fff9feb2325340c9f2df19ae08f7338e34fd5`。
- 最终送审 candidateId：`6b6370ceece63161162de3d6fc5b8bc7fce0e7d943dddf9f3d06f06bea30cac7`。
- 范围：全部未提交实质 diff、新增海外0024迁移/测试、海外前端和预览/测试、identity-test角色fixture、OUTON九个发布模块及五个测试模块、源包清单与本轮源文档。CRLF归一后无实质差异的文件不当作功能改动。旧 `OUTON-INSTALL-20261102.md` 不作为本候选通过凭据。
- 合同：`docs/DESIGNER-ONLY-IMPLEMENTATION-20261102.md:3`、`:9`；源文档：`Product-Spec.md:1364`、`Design-Brief.md:226`、`DEV-PLAN.md:1587`。最新指令仅实现/测试/审查，不提交、不部署、不安装。
- 最终结论：**Stage 1 PASS / Stage 2 PASS**。HIGH 0、MEDIUM 0、LOW 1（浏览器测试同步稳定性）。仅批准上述候选的本地实现与测试审查；不代表生产部署/Skill安装已完成或已获授权。

## 快照变化复核

审查中主Agent修订三处并重新固定最终编号：`backend/tests/test_overseas_database.py:173`补上0022已经存在的输出文件表；`backend/tests/test_overseas_pictures.py:124`正确断言创建者降级为designer仍可读，另切换无关成员继续验证403；`frontend/src/views/overseas/admin/OverseasActivity.vue:59`修正“请先由提交图需”为“请先提交图需”。已逐处复核，不削弱拒绝路径。以下backend/frontend相对路径均位于`hengxin-smart-image/`。

独立浏览器复跑启动Vite开发服务器时，其生成文件写入与并行构建发生Windows文件写入错误。开发服务器已退出，主Agent恢复两份生成文件，改用最终生产构建的`vite preview`验证。随后`review-status`读取的currentId精确等于最终编号；临时生成文件不纳入结论。

## Stage 1：Spec Compliance — PASS

### 完整实现，逐条证据

| 合同条目 | 核对结论及代码证据 | 验证证据 |
|---|---|---|
| 1. 海外仅三角色 | `backend/app/overseas/auth/models.py:11`及`:37`枚举/数据库CHECK；`members/schemas.py:7`输入Literal；`permissions.py:25`拒绝未知及复数角色；`frontend/src/api/overseas/members.ts:4`仅三项 | `backend/tests/test_overseas_designer_roles.py:20`验证旧角色PATCH、筛选422及DB拒绝；128项独立后端专项通过 |
| 1. 删除运行时旧授权分支 | `backend/app/overseas/permissions.py:16`、`:32`、`:39`；`frontend/src/views/overseas/OverseasPortal.vue:9`、`overseas-preview/access.ts:2` | runtime海外目录搜索无operator/operator_manager角色分支；监控字段与历史保留项另列 |
| 1. 国内角色/身份不动 | `frontend/src/api/identity/auth.ts:13`国内仍接受operator，仅海外收敛；`infra/identity-test/membership_checks.py:155`依业务选择角色 | `backend/tests/test_overseas_designer_roles.py:34`国内operator审批200、海外422；源diff无国内后端运行文件 |
| 1. 旧角色映射与版本 | `backend/migrations/overseas/versions/0024_designer_roles.py:9`事务锁、`:15`仅受影响成员version+1、`:20`映射旧角色、`:27`替换CHECK；无DELETE/重建身份 | `backend/tests/test_overseas_designer_roles_migration.py:19`真实PG覆盖active/disabled/pending及legacy_unconfirmed；保留ID、归属、历史记录、时间及重复执行稳定 |
| 1. 生产旧角色实查 | `scripts/release/outon-baseline.py:21`只读快照；生产实查见`output/outon-install/designer_preflight.stdout:1` | 0.2.57、overseas_0023、5 designer / 1 design_manager / 2 super_admin，没有旧角色；未执行生产迁移 |
| 2. designer可创建 | `backend/app/overseas/permissions.py:39`、`tasks/service.py:47`；前端遵循服务端task.create | `backend/tests/test_overseas_designer_roles.py:70`无隐藏字段真实HTTP创建；browser三角色均到正式创建表单 |
| 2. 本人创建OR分配任务及统计 | `backend/app/overseas/permissions.py:32`、`:78`、`:91`同源并集；`tasks/queries.py:78`过滤先于分页；`management/facts.py:35`统计复用task_filter | `backend/tests/test_overseas_assignment.py:59`三角色分页、搜索、详情；`test_overseas_management.py:71`本人/无关数据与全局统计 |
| 2. 审核/执行仅本人负责 | `backend/app/overseas/permissions.py:36`设计只assigned；`tasks/requirements.py:24`检查task.design；`studio/service.py:17`经`studio/queries.py:20`检查任务级write权限；`frontend/src/views/overseas/OverseasRequirementsReview.vue:48`以task级capability控制 | `backend/tests/test_overseas_designer_roles.py:70`创建但未分配返回403；浏览器创建者没有审核按钮；转派后创建者仍读而无design |
| 2. 创建者提交资料与退回重提 | `backend/app/overseas/materials/service.py:75`检查task.create及created_by；`tasks/requirements.py:26`同规则；`tasks/queries.py:42`和`:48`能力投影一致 | `backend/tests/test_overseas_designer_roles.py:84`仅assigned不能提交/重提，主管可处理；浏览器失败保留、重试和重提成功 |
| 2. 主管全局创建/提交/重提，保持转派统计；超管全部 | `backend/app/overseas/permissions.py:30`、`:33`、`:37`、`:40`；`materials/service.py:81`及`tasks/requirements.py:26` | `backend/tests/test_overseas_assignment.py:49`转派矩阵；`test_overseas_designer_roles.py:84`主管全局提交/重提；128项专项 |
| 2. 管理授权不扩大 | `backend/app/overseas/permissions.py:41`成员/Skill/设置仍仅super_admin，原特定账号grant逻辑`:53`不变 | `backend/tests/test_overseas_management.py:109`主管settings403；成员浏览器撤权后收起管理导航；旧角色枚举移除没有扩大管理capabilities |
| 3. 共用字段顺序 | `frontend/src/views/overseas/OverseasCreate.vue:23`SKU在先，`:44`平台/品牌/名称/品名，`:50`设计slot；`OverseasRequirementsResubmit.vue:3`复用同组件 | browser DOM精确等于SKU 1→目标平台→品牌→任务名称→品名→负责设计；查看1366/390px截图匹配 |
| 3. 多SKU与设计选择保持 | `frontend/src/views/overseas/OverseasCreate.vue:25`增删1–100；`OverseasRequirementsResubmit.vue:4`原转派权限；`backend/app/overseas/tasks/requirements.py:86`设计变更仍须task.reassign | browser增删、多SKU请求及designerId断言；`backend/tests/test_overseas_assignment.py:49`普通设计不能转派 |
| 3. 移除market/remarks输入及审核详情remarks | `frontend/src/views/overseas/OverseasCreate.vue:23`至`:50`无两项；`OverseasRequirementsReview.vue:8`直接接SKU/资料；`OverseasTaskInfo.vue:19`无remarks/空提示 | `frontend/tests/overseas-requirements-component.test.ts:54`历史说明不可见；browser旧说明及目标站点控件数量0；历史market仍可在只读信息显示，符合仅移除输入合同 |
| 3. 新客户端不发remarks | `frontend/src/api/overseas/tasks.ts:86`白名单cleanDraft不含remarks，create/resubmit`:77`、`:81`统一调用 | `frontend/tests/overseas-tasks.test.ts:52`请求无remarks，响应仍保留；browser拦截create/resubmit验证 |
| 3. 后端兼容与历史保持 | `backend/app/overseas/tasks/schemas.py:23`market/remarks默认空；`tasks/requirements.py:93`只有显式提供才修改；审核快照`:61`保持历史 | `backend/tests/test_overseas_designer_roles.py:46`省略/空串/新内容、旧快照与DB持久化；`test_overseas_market_optional.py:45`同样验证market |
| 3. 幂等区分省略/空 | `backend/app/overseas/tasks/requirements.py:14`根据model_fields_set生成摘要，防止省略与清空混淆 | 上述remarks/market参数用例同key同内容重放成功，省略↔显式空返回409 |
| 4. 四阶段与人工审核退回保留 | `frontend/src/views/overseas/types.ts:63`四阶段；`studio/OverseasStudio.vue:4`正式工作台；`backend/app/overseas/tasks/requirements.py:50`人工决定、`:67`流转studio | browser四阶段文本精确断言；退回原因必填、取消不请求、确认一次、重提进入pending_review；工作台展开编辑/完成态回归通过 |
| 4. 运营称谓替换、执行操作者保留 | `frontend/src/views/overseas/OverseasRequirementsReview.vue:21`等及`backend/app/overseas/tasks/service.py:31`使用提交人；`management/monitor.py:23`operatorId、`management/router.py:27`/operators保持 | runtime文案搜索无新运营角色；`frontend/src/api/overseas/management.ts:9`及`:28`保留监控契约；相关管理专项通过 |
| 5. OUTON完整51文件、仅2JSON适配 | `scripts/release/outon-source.py:10`仅来源路径适配、验证字体/LogoSHA，`:30`复制完整树且复核原源；`docs/OUTON-SOURCE-MANIFEST-20261102.json:1`记录双份摘要 | reviewer对真实源目录/准备副本逐文件读取：51集合相同、49字节一致；仅manifest.json/font-reference.json改变，源及副本均匹配manifest |
| 5. 默认未分组/关闭，旧包及状态保持 | `scripts/release/outon-skill.py:23`追加不覆盖，`:48`验证旧包并复制；`:79`、`:92`比较全部原availability行；`backend/app/overseas/management/skills.py:25`缺省false/[] | `scripts/release/test_outon_skill.py:15`旧metadata及字节保持、`:32`拒绝重复；55项工具测试通过；仅准备，未安装 |
| 合并发布工具：9运行文件+0024；国内不动 | `scripts/release/outon-runtime.py:24`封闭白名单、`:48`manifest和baseline哈希校验；`outon-native.py:67`拒绝与国内共享源，`:36`守护无关服务/源 | `scripts/release/test_outon_release.py:59`名单精确匹配；`test_outon_native.py:116`无关源漂移拒绝 |
| 合并发布工具：正常停止、不强杀 | `scripts/release/outon-deploy.py:135`先idle再停止API再pause；`outon-native.py:81`设置SendSIGKILL=no/无限stop后先停outbox，超时保留保护 | `scripts/release/test_outon_native.py:41`忙碌拒绝、`:51`顺序、`:75`超时无强杀；`test_outon_release.py:104`提交竞态 |
| 合并发布工具：备份隔离恢复、迁移重复性 | `scripts/release/outon-database.py:46`隔离同名PG恢复及两次upgrade，`:90`备份指纹，`:134`门禁；`outon-runtime.py:96`仅受影响身份允许role/version/timestamp变化 | `scripts/release/test_outon_safety.py:145`失败清理、`:165`重复验证、`:185`漂移拒绝；`test_outon_contract.py:47`精确数据差异 |
| 合并发布工具：API/native一致及恢复 | `scripts/release/outon-native.py:172`逐文件备份/原子换入、真实用户编译；`outon-deploy.py:180`先迁移/native凭据再API；`:153`迁移开始后拒绝旧API恢复 | `scripts/release/test_outon_native.py:94`部分安装保留备份不可盲重试；`:126`迁移后拒绝旧服务恢复 |
| 合并发布工具：前端、Skill独立 | `scripts/release/outon-frontend.py:26`静态备份、旧hash资源保留；`:72`有漂移即拒绝回退；`outon-deploy.py:216`无自动Skill安装；`outon-package.py:34`要求提交且已审快照 | `scripts/release/test_outon_release.py:140`回退保留两代资源、`:150`碰撞拒绝、`:159`后续版本防覆盖；当前无部署动作 |

部分实现：无本轮已授权本地实施项缺失。未实现：生产迁移/安装/正式线上验收未执行，属于最新明确暂停范围，不视作本地实现缺陷。恢复发布授权后仍须运行生产实际制品安装测试、备份恢复与真实服务身份读取及正式页面验收，不能用本报告代替。

Spec漂移：未发现新页面、API或业务表。0024仅收敛原角色约束；后端remarks/market字段、监控operatorId及历史审计保留均是明确要求。预览角色、测试fixture适配属于已批准范围，不变更国内身份体系。证据：`outon-runtime.py:24`、`0024_designer_roles.py:9`、`frontend/src/api/identity/auth.ts:13`。

## Stage 2：Code Quality — PASS

- 结构/类型：新增发布模块按source/package/gate/database/native/frontend/skill分工；所有本轮实质变更代码文件及新增代码文件均不超过300行，新增TS无any。`frontend/src/api/overseas/tasks.ts:5`明确请求/响应remarks分离；`:86`白名单投影。`git diff --check`无输出、退出0。
- 错误与恢复：`outon-deploy.py:85`保存pytest双流与超时输出，失败/skip不发PASS凭据；`outon-native.py:172`先保存原件再原子替换；`frontend/src/views/overseas/OverseasRequirementsResubmit.vue:28`失败保留内容、409刷新、401/403失权；browser实走故障路径。
- 安全扫描：本轮新增行未发现硬编码密钥、eval、innerHTML、dangerouslySetInnerHTML、VITE公开秘密或shell=True。`outon-runtime.py:96`字符串SQL的表名/UUID有严格白名单校验；`test_outon_contract.py:67`注入输入拒绝。`outon-runtime.py:48`包路径/symlink/多余内容/哈希校验，`test_outon_safety.py:39`、`:53`验证。发布脚本中的服务器绝对目录为既有明确部署目标，并非用户隐私泄露；两份来源JSON已适配。
- 测试真实性：后端测试通过实际HTTP、持久数据库与无关身份验证；新PG迁移测试构造真实0023六成员、历史任务/审计/审核快照后升级，逐表比较并重复调用upgrade。`backend/tests/test_overseas_designer_roles_migration.py:19`、`:64`、`:91`。浏览器使用正式Vue/Element及最终生产构建，API为受控mock，**不等同真实后端端到端，也不等同生产验收**；脚本`frontend/tests/overseas-designer-only.browser.mjs:36`明确路由拦截。
- 视觉对比：独立打开最终构建创建/退回/修改及邻居正式工作台，并实际查看截图`output/playwright/designer-only/create-fields.png`、`returned.png`、`resubmit-390.png`、`resubmit-390-submit.png`及`output/playwright/overseas-polish/formal-1366.png`。表单保持白卡/蓝色Element控件、相同shell/字体，DOM顺序正确；窄屏单栏、提交及取消按钮可达，无横向溢出。既有`frontend/src/views/hengxin/prototype.css:7`列宽300/265px与22px间距、`:8`23/17px内边距未改变；共用表单`OverseasCreate.vue:89`18px字段gap和`:126`600px单列保持；邻居`studio/OverseasStudio.vue:2`布局未改，只有阶段文本。

### LOW，非阻断观察

`frontend/tests/overseas-members-faults.browser.mjs:66`等待第一个loading-mask后，`:67`立即测同selector的裁切。最终生产构建首跑出现过渡中元素卸载（Element is not attached to the DOM），同候选直接重跑整套通过，非权限/业务断言失败。建议未来让fixture等待本次延迟请求已挂起及稳定的目标loading节点，再做裁切断言，避免把过渡动画误判为业务回归。未修改测试以掩盖失败。

## 验证与原始输出

reviewer独立运行后端7模块（designer_roles、market_optional、permissions、assignment、management、requirements、tasks）：

```text
128 passed, 2 warnings in 16.88s
```

两条warning来自既有Starlette/httpx和AnyIO弃用提示。不是权限失败。

reviewer独立运行5个OUTON测试模块+既有skill_platform_release：

```text
.......................................................                  [100%]
55 passed in 1.59s
```

reviewer独立类型检查原始输出（退出0）：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.58 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

前端全套原始摘要，已读取`output/designer-frontend-tests.log`末尾：

```text
ℹ tests 441
ℹ suites 0
ℹ pass 441
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10310.055
```

最终生产构建完整原始输出：`output/outon-install/designer-build.log`。已读取命令及结束摘要，并用该dist独立浏览器验证：

```text
> hengxin-smart-image-frontend@0.2.58 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 35.70s
```

reviewer在`http://127.0.0.1:3044`的最终构建独立复跑三套现有browser脚本，原始通过输出：

```text
PASS three role create access; ordered fields; SKU add/remove; no site/remarks; designer selection; failed create retry; read-only reviewer capability; reject required/cancel/confirm; resubmit retry and preserved historic remarks; desktop/mobile clipping
PASS：多角色/只读身份/冲突刷新/禁用确认/空态/窄屏/断网恢复/401/403/撤权与国内隔离
PASS: fixed two rows; long draft; 1920/1366 clipping; 16px/Enter/Escape/done; session drafts; completed disabled; six platforms/no site input
```

成员脚本首跑原始失败已保留说明：

```text
locator.scrollIntoViewIfNeeded: Element is not attached to the DOM
at unclipped (.../frontend/tests/overseas-members-faults.browser.mjs:13:17)
at .../frontend/tests/overseas-members-faults.browser.mjs:67:9
```

真实源包逐字节核对原始输出：

```json
{"files":51,"byteIdentical":49,"adapted":["assets/brand/font-reference.json","assets/brand/manifest.json"],"sourceAndPreparedMatchManifest":true}
```

Linux初轮30模块输出`output/outon-install/run_ci.stdout`：`2 failed, 326 passed, 2 warnings in 170.43s`，不能报成全通过。两处旧预期已按新candidate增量复核，并读取最终真实Linux/PG定向日志`output/outon-install/run_targeted.stdout`：

```text
ISOLATED_TESTS 2
...............                                                          [100%]
15 passed, 2 warnings in 54.51s
```

全83模块首次执行在480秒达到外层超时，约79%进度；除两项已知旧测试外，平台迁移测试缺少共享前端seed fixture。该测试归档仅打包backend，缺少`frontend/preview-skill-platforms/seed.json`，不能将此轮作为全量通过证据。补齐执行包fixture后分42+41模块隔离重跑，源码candidate未变，最终结果如下。


最终Linux两批完整原始日志：`output/designer-ci/run_batch_a.stdout`与`output/designer-ci/run_batch_b.stdout`：

```text
ISOLATED_TESTS 42
382 passed, 2 warnings in 304.58s (0:05:04)

ISOLATED_TESTS 41
347 passed, 2 warnings in 255.89s (0:04:15)
```

合计83模块、729通过、0失败、0跳过。包含真实PG0024迁移、重复升级、历史数据保护及平台迁移；该结果取代此前超时及旧预期失败记录作为最终全套证据，未隐去此前失败。

reviewer独立核对两包SHA256、模块集合、包内代码和当前工作区：

- `output/designer-ci/batch_a.tar.gz`：`1af37fed3394ae0fb8fe3087a150bef0607a31634d8eda37623f3d14fc1c211d`。
- `output/designer-ci/batch_b.tar.gz`：`cbe13b91b00f55e3aedd1bd3b100cbb3b870e13156949b826c2c6450a6831fc4`。
- 两批测试名称无交集、并集精确等于完整83模块；每包636个app/tests/migrations及Alembic配置条目与当前工作区CRLF归一后一致；seed字节亦一致，Dockerfile显式复制到`/frontend/preview-skill-platforms/seed.json`。因此最终两项测试修复已包括在全套运行中，不再仅靠前述定向补测推断。
- 最后只读`review-status`：`currentId=6b6370ceece63161162de3d6fc5b8bc7fce0e7d943dddf9f3d06f06bea30cac7`，与本报告审查候选一致。审查自行启动的preview已停止。

独立审查不执行review-approve、不写.needs-review、不提交Git、不部署、不安装Skill。主Agent可依据本报告将相同candidateId及Stage 1/Stage 2 PASS登记；后续源码变化必须重新固定和复核。用户追加需求和发布授权仍由主Agent处理。
