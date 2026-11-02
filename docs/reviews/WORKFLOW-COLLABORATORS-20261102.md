# 指定五位设计人员工作流权限审查

- 审查日期：2026-11-02；执行者：独立 code-reviewer；依据 `.agents/skills/code-review/SKILL.md`。
- candidateId：`b79034980d927ef5a919ac073b3ae96c9e4fe1c99a264b2001c1f639f85ff554`。
- 结论：**Stage 1 PASS / Stage 2 PASS**。本轮 HIGH 0、MEDIUM 0、LOW 1（截图时机，见下文）。
- 范围：相对上一已批准快照 `6b6370ceece63161162de3d6fc5b8bc7fce0e7d943dddf9f3d06f06bea30cac7` 的全部 25 个代码/配置文件差异，以及与既有任务、材料、会话、归档、身份、统计和发布流程的整合。包含后端 9 个运行文件、2 个新增测试，前端工作台与新增浏览器测试，2 个基础设施配置，6 个发布运行模块和4个发布测试模块。
- 合同：`docs/WORKFLOW-COLLABORATORS-20261102.md:3`、`:9`；源文档 `Product-Spec.md:1379`、`DEV-PLAN.md:1595`、`Design-Brief.md:226`；验证记录 `docs/WORKFLOW-COLLABORATORS-VALIDATION-20261102.md:3`。
- 本报告批准本地实现及验证，不代表生产配置已经生效。用户禁止 Git 提交、部署、Skill 安装；消息实际姓名/时间仅讨论，不在本轮实施范围。

## 快照与旧审查范围

审查开始和结束均执行只读 `review-status`，currentId 都等于上述 candidateId。通过 `.codex/review-state.json` 的 `approved.snapshot.files` 与 `candidate.files` 比较，增量恰好25文件；审查期间没有源码变化。上一合并候选已完成的角色收敛、表单、0024迁移、OUTON完整包等逐项结论见 `docs/reviews/DESIGNER-ONLY-20261102.md:1`，未变化内容凭相同文件摘要继承，本轮再以完整85海外模块、相关专项和邻居工作台验证整合，没有将旧报告直接当作新候选批准。

下文 `backend/`、`frontend/`、`infra/` 路径均位于 `hengxin-smart-image/`。私人五人UUID不复制到报告或源码。

## Stage 1：Spec Compliance — PASS

### 完整实现

| 合同/验收条目 | 实现证据 | 验证证据与结论 |
|---|---|---|
| 恰好截图五人，稳定UUID，active/enrolled designer | `scripts/release/outon-workflow.py:22`校验5条、规范UUID、互异和状态；`:58`只读查询实际有效角色，包含独立full-access影响 | 独立比较 `output/workflow-access/binding.private.json:1` 与 `output/outon-install/workflow_members.stdout:1`，完全一致，姓名集合精确等于陈妹/周仁平/胡礼辉/黄湘婷/姚锐娟，5个不同ID；`test_outon_workflow.py:31`、`:69`验证拒绝路径 |
| 配置缺省为空，不使用full_access、不按姓名/所有designer授权 | `backend/app/overseas/config.py:32`独立frozenset UUID字段；`permissions.py:60`仅有效designer且ID命中；`infra/compose.overseas.yaml:15`默认`[]` | `backend/tests/test_overseas_workflow_grant.py:32`配置验证及脱敏；`:109`同名异ID/未配置/角色变化；增量扫描不含5人UUID；私人文件git check-ignore通过 |
| 有效身份才授权，停用/待审批/未入目录/无角色/多角色/未知角色失败关闭 | `backend/app/overseas/auth/dependencies.py:13`在登录请求及principal构造前检查；`permissions.py:60`先校验真实角色，再应用grant | `test_overseas_workflow_grant.py:82`7类既有session重查；原full_access专项与完整海外回归通过 |
| task.read读取所有海外任务，列表过滤/分页/详情一致 | `backend/app/overseas/permissions.py:69`只扩展task.read到all；`:100`SQL筛选与`:113`对象判定同源；`tasks/queries.py:77`先过滤后计数分页 | `test_overseas_workflow_grant.py:46`三类关系、pageSize=1、total=3、mine=2、详情capabilities精确断言 |
| 本人创建OR本人负责task.design；他人只读 | `backend/app/overseas/permissions.py:69`design为created/assigned；`studio/queries.py:18`写入要求task.design；`studio/service.py:17`集中mutation门禁 | `test_overseas_workflow_grant_studio.py:22`分别走created/assigned真实HTTP会话创建、改名、上传、发送、取消、返工、归档、完成/解冻/删除会话；`:66`他人任务逐接口403 |
| 本人创建或负责可提交、审核、退回、重提 | `backend/app/overseas/permissions.py:80`can_submit_requirements；`materials/service.py:75`及`tasks/requirements.py:13`使用同一规则；`tasks/queries.py:42`投影对应能力 | `test_overseas_workflow_grant.py:150`3类关系，提交→退回→重提→通过；他人三项403；幂等重放相同响应 |
| 状态/版本/幂等/素材归属校验保持 | `materials/service.py:63`仅本人未提交资料或同任务重提资料；`:88`状态版本；`tasks/requirements.py:29`版本、`:49`审核状态、`:77`重提状态；`studio/service.py:17`原mutation保持 | 上述重放及异任务材料拒绝、`test_overseas_studio_file_recovery.py:172`、`:190`、`:226`、`:278`状态/会话/删除/撤权，完整85模块751通过 |
| 本人未提交私人材料仍owned | `backend/app/overseas/materials/service.py:21`、`:28`未绑定材料仍所有者限制；绑定后才按任务读scope | `test_overseas_workflow_grant.py:179`读取、下载、删除及挪用于创建均403 |
| 他人消息、材料、会话、图片、输出、归档可读 | `studio/queries.py:18`，`materials/service.py:28`，`archives/service.py:63`、`:92`，`pictures/queries.py:19`、`:43`，`execution/router.py:26`均复用任务读scope | `test_overseas_workflow_grant_studio.py:66`实际GET覆盖工作台/events/transcript、附件、原材料、图片、输出、任务材料、归档详情/下载/列表、方案、图片、jobs、执行事件，HEAD也通过 |
| 所有他人业务写独立拒绝 | `studio/service.py:17`、`execution/cancel.py:17`、`pictures/review.py:18`、`plans/service.py:75`；`tasks/requirements.py:24`；恢复接收单独write门禁 | `test_overseas_workflow_grant_studio.py:66`发送/会话创建改名删除/上传移除/取消/归档/完成解冻/审核/分析/归档删除/job取消全403；`test_overseas_workflow_grant.py:195`Linux legacy方案确认/生成重试/图片修改确认/归档边界 |
| 管理、改派、任务删除保持；统计不扩大 | `permissions.py:26`角色scope未增加管理能力；`:69`只扩展task.read/design；`management/facts.py:37`明确stats.read；`tasks/requirements.py:87`改派仍检查task.reassign | `test_overseas_workflow_grant.py:46`管理/改派/删除403及stats=本人并集；`:150`重提不能变更负责设计；`test_overseas_workflow_grant_studio.py:104`无关任务usage为0 |
| 原管理员/主管/未配置designer不变，国内保持 | `permissions.py:60`有效角色为designer才collaborator，`:71`角色限定；本轮无国内业务代码变更 | `test_overseas_workflow_grant.py:109`转为主管按原scope；独立permissions/full_access/assignment专项；全85海外回归；未变化国内文件摘要继承上一快照 |
| 恢复文件GET API/native均用read，POST仍design，仅列表元数据 | `studio/recovery_router.py:24`按operation决定write；`recovery_files.py:16`身份/任务/会话复核；`:37`available传write=False/idle=False；`:58`receive默认write=True | `test_overseas_workflow_grant_studio.py:129`真实API转实际handle_native，GET200、POST403，直接native receive403，撤grant/停用后API/native GET均403；`recovery_listing.py:38`仅返回DTO，`:69`、`:122`保留受限目录及保护路径 |
| 前端按每任务capabilities，旧pending不能绕过只读 | `frontend/src/views/overseas/studio/OverseasStudio.vue:17`、`:20`两个重试按钮禁用；`:21`、`:36`、`:42`会话/发送/恢复采用任务能力；任务控制层原门禁保持 | 新browser三种关系；他人隐藏file input、drop/paste、dispatch disabled click、旧pending、切换会话均零写；本人创建/负责各12写 |
| marker仅刷新信号，不可authorize，撤权同ID/角色/version也重取任务 | `auth/router.py:32`添加信号；`permissions.py:14`authorizable集合不包含marker；`frontend/src/views/overseas/OverseasTasksPage.vue:154`watch capabilities，`:106`接收相同version的新能力 | `test_overseas_workflow_grant.py:130`marker直接authorize403；`frontend/tests/overseas-workflow-collaborators.browser.mjs:156`仅移除marker，任务GET增加、输入/新会话/改名禁用、无补发旧请求 |
| 页面风格与消息署名时间不改 | 本轮前端运行变化只有`OverseasStudio.vue:17`禁用绑定；既有布局/样式和署名时间组件摘要不变 | 实际打开最终build三种任务及邻居工作台，查看稳定截图；polish脚本1366/1920布局、输入两行和编辑弹窗通过 |
| 发布白名单扩至14运行文件+0024，API/native一致 | `scripts/release/outon-runtime.py:24`15项封闭集合、NATIVE_FILES为14个app文件；`outon-baseline.py:7`相同名单；`outon-package.py:55`打包workflow helper | 独立核对私人baseline15项、仅新迁移为null、前端基线0.2.57；`test_outon_release.py:59`白名单测试及65项工具测试通过 |
| 私人binding绑定hash，API overlay只改image和grant | `outon-workflow.py:97`prepare核实有效身份及原grant；`:109`保存bindingHash；`:127`漂移门禁；`:114`、`:120`严格overlay整对象比较 | `test_outon_workflow.py:45`、`:62`、`:93`仅合法key/image可变化，不改full_access/其它服务配置，未知已有grant拒绝 |
| native停稳、迁移后安装独立env/drop-in，保护原配置 | `outon-native.py:175`要求迁移凭据、stopped、备份并安装14源码；`:209`先workflow.install再start；`outon-workflow.py:163`再次stopped，独立600 env/644 drop-in；`:148`未知配置inventory拒绝 | `test_outon_native.py:126`实际临时源码安装顺序；`test_outon_workflow.py:84`只含授权key，`:126`未知drop-in拒绝；原配置文件hash由`outon-native.py:36`核对 |
| 启动后实际环境校验，原失败恢复/排空/隔离恢复/国内保护保持 | `outon-workflow.py:180`核对两个进程grant及原OVERSEAS_/HX_环境摘要；`:191`核对API；`outon-deploy.py:136`idle→API停→复查idle→pause→native停；`:155`迁移后禁止旧API恢复；`outon-database.py:134`备份恢复证明后才迁移 | `test_outon_workflow.py:113`、`:136`失败保留marker/禁盲重试及环境漂移拒绝；native/safety/contract全部通过；生产调用未执行，真实安装验证仍属于待授权发布步骤 |

### 部分实现、未实现、Spec漂移

本轮授权的本地实现项没有缺失。生产授予、部署、迁移和Skill安装没有执行，符合 `Product-Spec.md:1380` 的暂停要求，不计为实现缺陷。身份绑定只读证据不是线上grant已生效的证明。

未发现新增业务页面、API或表；marker是范围变化信号，已有权限入口和恢复API被复用。`permissions.py:14`、`auth/router.py:32`、`recovery_router.py:32`为对应证据。当前用户尚未授权消息姓名/时间修改，因此没有将该讨论写入本轮实现或验收。

## Stage 2：Code Quality — PASS

- 结构/类型：独立读取25增量文件并扫描，所有变更Python/Vue/MJS均不超过300行；授权集中于 `permissions.py:60`、`:69`、`:80`，列表/详情/写入不复制个人名单。新增 `outon-workflow.py:1`负责绑定及环境，native/deploy仍分别负责停启和编排。16个OUTON脚本内存compile通过；类型检查退出0。
- 安全：25文件未发现eval、innerHTML、dangerouslySetInnerHTML、公开VITE密钥、sk-ant/sk-proj密钥、shell=True或五人真实UUID硬编码。`outon-workflow.py:17`拒绝symlink，`:29`规范UUID，`:143`/`:146`验证所有者与mode，`:148`限制systemd配置集合。已有Redis Lua调用位于未变更 `studio/recovery_transport.py:72`，脚本固定、参数分离，不是执行用户代码。
- 故障路径：`outon-native.py:185`先保存原字节再替换，`:177`禁部分安装盲重试；`outon-workflow.py:165`保留开始凭据，失败不伪造installed；`outon-deploy.py:86`安装测试超时/失败/skip不得给通过凭据。对应测试实际制造磁盘失败、配置漂移、超时和旧API恢复拒绝。
- 测试真实性：新增权限HTTP测试复用真实FastAPI路由和数据库Session；身份服务为隔离stub，后端fixture使用SQLite，不冒充线上身份端到端（`backend/tests/test_overseas_auth.py:34`）。三种关系通过数据库设置created_by/designer_id可达条件；未知/多角色专门模拟数据库损坏以验证失败关闭（`test_overseas_workflow_grant.py:99`），不当作正常可写业务输入。新增native用例复用真实handle_native与临时会话目录，只有传输被替换（`test_overseas_workflow_grant_studio.py:142`）。Linux/PG全套含真实PG相关模块和迁移；不能称751条全部都运行在PG存储上。
- 浏览器边界：正式Vue/Element和最终build，API为mock；验证按钮、controller边界、读取预检、下载事件与撤权刷新。下载导航有请求进入本地preview代理并出现 `ECONNREFUSED 127.0.0.1:8009`，因此**浏览器没有证明原件下载成功或字节一致**。原件字节证据来自完整后端回归 `test_overseas_attachment_downloads.py:49` 的 `response.content == data` 等；新增跨任务读取测试主要证明HTTP授权200/403。未将这两层拼成真实端到端下载结论。
- 视觉对比：reviewer在独立 `127.0.0.1:3057` 的既有build preview上运行新增三关系流程及邻居 `overseas-polish.browser.mjs`，实际查看 `{created,assigned,other}.png`、`stable-{created,assigned,other}.png` 与 `output/playwright/overseas-polish/formal-1366.png`。沿用相同Art壳、蓝色Element按钮、白卡和会话/素材列；只读控件灰显、下载入口仍可见。原 `studio/studio.css:17` 输入14px/12px圆角、`:60`窄屏规则未变；邻居实测两行输入、16px展开编辑和1366/1920边界通过。本轮未声称新增三关系各自完成390px全套。
- `git -c core.safecrlf=false diff --check`无输出、退出0。审查preview通过Ctrl+C停止，3057不再有Listen；没有启动vite dev或改写生成源码。

### LOW：浏览器截图应等待退出动画完成

`frontend/tests/overseas-workflow-collaborators.browser.mjs:170`在解冻对话框关闭后的立即截图可能截到离场遮罩；首轮assigned截图有半透明弹窗残影，不能直接用作稳定布局证据。建议未来在截图前等待dialog/overlay隐藏或关闭动画。本次未修改测试源码及任何断言，只在内存执行副本给最终截图增加等待、禁用截图动画，生成并查看 `stable-*.png`，整套原业务断言再次通过。此项不影响授权判断，不阻断本候选。

## 验证原始输出

reviewer独立运行后端6模块：workflow_grant、workflow_grant_studio、permissions、full_access_grant、assignment、studio_file_recovery：

```text
105 passed, 3 skipped, 2 warnings in 19.12s
```

3条skip仅为Windows缺少POSIX safe-open的legacy授权用例；最终Linux完整运行已覆盖且无skip。两条warning是既有Starlette/httpx与AnyIO弃用提示。

reviewer独立运行6个OUTON测试模块及既有skill_platform_release：

```text
.................................................................        [100%]
65 passed in 1.88s
```

初次使用系统Python未安装pytest，输出 `No module named pytest`；没有安装依赖，改用项目既有backend venv得到上面的有效通过结果。独立内存编译原始输出：

```text
COMPILE_PASS 16 scripts; each <=300 lines
DELTA_FILES 25
DELTA_SCAN_PASS no forbidden patterns or private member UUIDs; changed code <=300 lines
FIVE_MEMBER_BINDING_MATCHES_READ_ONLY_EVIDENCE
```

reviewer独立类型检查原始输出，退出0：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.58 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

已读取本候选前端单测/构建日志 `output/playwright/workflow-collaborators/unit-tests.log`、`build.log`；没有把查看日志表述为reviewer再次构建：

```text
ℹ tests 441
ℹ suites 0
ℹ pass 441
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10778.4138

> hengxin-smart-image-frontend@0.2.58 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4708 modules transformed.
✓ built in 39.33s
```

reviewer独立浏览器原始输出：

```text
PASS workflow collaborator capability UI [{"relationship":"created","writable":true,"writes":12,"reads":59},{"relationship":"assigned","writable":true,"writes":12,"reads":56},{"relationship":"other","writable":false,"writes":0,"reads":38}]
PASS: fixed two rows; long draft; 1920/1366 clipping; 16px/Enter/Escape/done; session drafts; completed disabled; six platforms/no site input
```

稳定截图复跑仍为created/assigned各12写、other零写；读请求次数受刷新/轮询时机影响，不作为固定计数验收标准。

完整Linux两批原始日志 `output/workflow-ci/run_batch_a.stdout`、`run_batch_b.stdout`：

```text
ISOLATED_TESTS 42
382 passed, 2 warnings in 289.09s (0:04:49)

ISOLATED_TESTS 43
369 passed, 2 warnings in 245.12s (0:04:05)
```

合计85模块、751通过、0失败、0跳过，含新增全部22授权用例。reviewer独立读取归档并核对：

```text
ARCHIVE a sha256 847726706a4bd7fc2d07d5c4a751bb8fb72fee2ba8b4b69a2c653a2fffeef613 verified_sources 636 tests 42
ARCHIVE b sha256 282c9ac0c5a3fed97854b315e18bb62a23f60958ea425b585a1ddbc6b5bee16c verified_sources 636 tests 43
EXACT_FULL_TEST_SET 85
```

两批无测试名称交集，并集精确等于当前全部85个test_overseas模块。每包636个app/tests/migrations条目与当前工作区CRLF归一后相同，前端平台seed字节一致；执行脚本使用生产依赖镜像、无外网临时PG容器及只读测试容器，finally清理仅本次临时资源（`output/workflow-ci/run_batch_a.py:21`、`:34`、`:39`）。这不是生产部署。

结束前currentId仍为 `b79034980d927ef5a919ac073b3ae96c9e4fe1c99a264b2001c1f639f85ff554`。reviewer未执行review-approve、未写.needs-review、未提交/部署/安装。主Agent可依据本报告登记同一candidateId的两阶段PASS；之后代码变化需重新固定快照并复核。
