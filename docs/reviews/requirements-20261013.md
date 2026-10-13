# 图需人工审核与资料阅读独立审查

- 日期：2026-10-13。
- 最终 candidateId：`bb96c6cf624acfc6aa130ea84c65b786270e6791f99006ba0d26f78eefc61a95`。
- 首轮 candidateId：`965fa0723dee2dfe1489853e20506d9c07ba4c3cc934ece8d900765b0e9a9cb9`，不以首轮结论覆盖修复后的代码。
- 范围：当前 git diff 和未跟踪源码，包括海外任务/资料/方案门禁、0010 迁移、正式 Vue 页面/资料阅读器、PDF 发布资源、增量部署脚本、对应单测/PG/真实 HTTP 测试。已有功能只检查本次影响范围，不将尚未开发事项作为缺陷。
- 依据：Product-Spec.md:982、Design-Brief.md:180、DEV-PLAN.md:1330；批准图 `output/design-review-20261013/node2-full.jpg`、`node2-decision.jpg`、`material-reader.jpg`。
- 方法：按 code-review skill 执行；读取源码、测试前提、原始日志和批准设计图。只审查，不修改产品源码、不提交、不登记批准。
- 快照：审查中存在多次修复，已按下方记录复核差异。最终运行 review-status，currentId 与最终候选一致，approved=false；批准登记由主 Agent 完成。

## 结论

最终 **Stage 1：PASS；Stage 2：PASS**，仅对应上述最终 candidateId。首轮设计差异、文件行数与时间展示问题均已复核修复，无遗留 HIGH/MEDIUM 阻断。主 Agent 可据此登记同一快照的 review-approve；任何后续源码变化仍需新快照复核。

## Stage 1：首轮发现及修复记录

### M1 — 放大阅读器缺少已批准的文件切换、版本上下文及页缩略导航

- 依据：`output/design-review-20261013/material-reader.jpg` 在放大窗口内显示资料文件 tabs、文件/版本信息、左侧页缩略图及选中状态；设计优先级高于文字 Brief。
- 实际：`hengxin-smart-image/frontend/src/views/overseas/OverseasMaterialReader.vue:6` 的文件 tabs 只在背景卡片；`:18` 放大弹窗仅有当前文件标题、打开/下载按钮及单个 reader，没有弹窗内文件切换和版本选择。`hengxin-smart-image/frontend/src/views/overseas/MaterialPdfReader.vue:3` 仅上一页/下一页和一个 canvas，没有缩略图导航。
- 影响：放大后需要关闭窗口才能切换文件，阅读导航及版本上下文不符合已批准界面。真实分页/缩放已经实现，但不能因此认定设计完整匹配。
- 优先级：MEDIUM。
- 完成标准：补齐放大窗口文件/版本栏与 PDF 页缩略图导航；验证文件切换不关闭弹窗、页选择同步及旧异步响应失效。修复代码证据见下方差异复核。

## Stage 1：完整实现的逐条证据

以下“完整实现”指已读取代码与所列证据支持该条，不代替全阶段验收。

| 条目 | 结论及实现证据 | 验证证据 |
|---|---|---|
| 提交先人工审核，不直接排 AI | 完整。backend/app/overseas/materials/service.py:65 绑定资料后设置 pending_review、requirements_approved=false；plans/service.py:45 拒绝无审核标记与 created/pending_review/returned | backend/tests/test_overseas_requirements.py:29 检查 Job/JobOutbox/Plan 全为 0，审核后均唯一；真实 HTTP 日志 PASS |
| 负责设计/设计主管权限；管理员不隐式处理 | 完整。tasks/requirements.py:12 锁成员、权限、任务行并检查 task.design 范围；permissions.py:33 区分 assigned/all，super_admin 不授予 task.design | test_overseas_requirements.py:58；infra/identity-test/requirements_checks.py:118 拒绝运营、他人设计、管理员 |
| reject 原因必填、进入 returned | 完整。tasks/requirements.py:49 校验状态及空白原因；:59 设置 returned；前端 OverseasRequirementsReview.vue:51 校验、确认、保留失败输入 | 前端 overseas-requirements-component.test.ts:48；HTTP 测试 reject 422/200 与 returned 断言 |
| 运营本人/运营主管修改、必需 task.create | 完整。tasks/requirements.py:12 校验 task.create 和所有权/主管角色；:69 仅 returned 可重提 | test_overseas_requirements.py:105 权限与保留原资料；真实 HTTP 外部运营 403 |
| 商品字段/SKU/资料修改重提，改设计需 task.reassign | 完整。tasks/requirements.py:76 校验设计资格和改派权限，:81 绑定资料，:83 更新字段并替换 SKU；OverseasRequirementsResubmit.vue:25 回填，:30 重提及异常状态 | test_overseas_requirements.py:158 验证保留一份/替换另一份与改派 403；前端组件测试验证字段/SKU/失败保留 |
| 版本、幂等、并发只能产生一个审核及分析任务 | 完整。tasks/requirements.py:12 请求摘要/查重、任务行锁、版本检查；:27 同事务事件/请求记录/提交 | test_overseas_requirements_postgres.py:35 相同/不同 key 竞争；:57 重提竞争；HTTP 两并发同 key 返回相同结果且 Job/Outbox 各 1 |
| 审核操作者/时间/结论/意见/版本和提交快照保留 | 完整。tasks/models.py:73 RequirementsReview 唯一 task/version；tasks/requirements.py:54 冻结商品、SKU、设计、materialIds；tasks/queries.py:54 返回历史 | test_overseas_requirements.py:65 比较修改前 SKU/materialIds，旧原件仍可读且不可删除 |
| 当前资料供 AI，历史资料留存并继续鉴权 | 完整。materials/service.py:115 按 task.material_ids 读取当前集合；plans/snapshot.py:18 使用当前集合；materials/service.py:28 根据当前任务权限鉴权旧绑定原件 | test_overseas_requirements.py:65 校验新任务 payload 仅新资料、旧原件字节、失权后 403；真实 HTTP 相同断言 |
| 已进行历史任务保持，不回退或重复生图 | 完整。0010_requirements_review.py:11 只给已有非草稿流程赋批准标记，material_ids=NULL 保留原集合，未改状态/版本/已有 job；:46 禁止破坏历史的降级 | test_overseas_requirements_migration.py:12 从真实 0009 七种状态迁移，重复 upgrade、job/material/国内快照对比 |
| 审核页真实任务/商品/SKU/人员/资料/记录/操作/流程 | 完整。OverseasRequirementsReview.vue:4 至 :33 均由 task/files 驱动，:48 权限控制；OverseasTasksPage.vue:12 只对 pending_review/returned 显示 | 前端实际 SFC 测试不只测纯函数，含确认取消、409、网络失败、失权和卸载迟到响应 |
| 通过与退回确认、失败不伪装成功 | 完整。OverseasRequirementsReview.vue:51 至 :69；OverseasRequirementsResubmit.vue:30 至 :45 只在成功响应后发 changed，失败保留草稿 | overseas-requirements-component.test.ts:48、:60、:66 |
| 双资料卡对齐、窄屏单列；无示例控件进入正式页 | 完整。OverseasMaterialsPanel.vue:7 双卡结构，:91 两列等宽，:97 小于 800px 单列；OverseasCreate.vue:5 区分正式说明；正式页数据接口路径为 api/overseas/v1 | 代码逐项比对；完整正式截图复核尚待修复后执行 |
| PDF 原件分页/缩放/放大 | 完整，M1 已修复。MaterialPdfReader.vue:26 使用真实 PDF page/render，:46 鉴权读取字节、PDF.js worker/本地字体/解码资源；未伪造原版式 | reviewer 实际读取最终 output/requirements-qa/pdf-reader.jpg，见真实3页、原件画布与缩略图、文件/版本栏；125%操作及下载字节验证由主 Agent 实测提供 |
| Word/表格安全内容预览、说明非原版式 | 完整。MaterialTextReader.vue:7 明示非原始版式，:14 表格文本插值，:16 pre 文本；material-reader-data.ts:3 拆表格与 Unicode 分页 | overseas-material-reader.test.ts:33 校验公式/脚本文字不执行，101 行分页与 Word 尾页 |
| 新窗口/原名原件下载/失败保留入口/服务端鉴权 | 完整。OverseasMaterialReader.vue:43 新开窗口前内容接口再鉴权，:52 Blob 下载使用原文件名，:58 textContent 创建安全独立阅读窗口；materials/service.py:28 后端权限 | 真实 HTTP PDF/DOCX/XLSX/CSV 字节、filename*、他人 403；前端下载拒绝回传测试 |
| 切换/关闭/卸载资源回收与旧响应失效 | 完整。OverseasMaterialReader.vue:37 epoch/abort/window close/URL revoke，:39 至 :42 watches，:66 卸载；MaterialPdfReader.vue:22 取消渲染、destroy，:27/:48 generation 检查 | overseas-material-reader.test.ts:39 卸载后 signal.aborted 且无迟到 URL；视觉修复后需补新导航路径验证 |
| 增量 0010 发布排空、备份、安装镜像、失败关闭海外、国内身份不变 | 静态完整。overseas-update-deploy.py:35 比对安装镜像 ID/旧 schema；:66 关闭海外入口→停 API→排空→停海外 outbox/worker→备份→迁移→切换→验证；:110 失败关闭海外；overseas-update-runtime.py:55 仅匹配海外路由，:89 排空，:99 dump/pg_restore list；既有 overseas-deploy.py:26 对镜像运行安装测试 | overseas-update-tests.py:16 隔离路由、:34 未知 worker 不视为空闲、:42 超时不杀执行器以及故障注入；生产部署尚未执行，不把脚本审查当成上线验收 |
| PDF 特殊资源精确验证 | 静态完整。scripts/release/package-overseas.py:86 仅允许固定 6.4.299 资源路径，核验依赖版本、拒绝 symlink、解压 gzip 后逐字节比对 pinned 依赖；frontend/vite.pdf-assets.ts:7 本地打包 | scripts/release/test_package_overseas.py 的 PDF worker/资源测试；非特例资产继续原审计 |

表内未带仓库前缀的 backend/frontend/infra 路径均相对 `hengxin-smart-image/`；scripts 路径相对仓库根。

## 证据边界与编译原始输出

已读取 `output/requirements-frontend-tests.log` 末尾：

```text
ℹ tests 301
ℹ suites 0
ℹ pass 301
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8963.9761
```

已读取 `output/requirements-build.log` 原始末尾：

```text
dist/assets/index-B4cnDj_F.js                                                               963.71 kB │ gzip: 307.80 kB
✓ built in 34.50s
```

已读取 `output/requirements-http-20261013.log`：

```text
PASS real PDF/DOCX/XLSX/CSV original bytes; pending no AI; roles; reject/resubmit; concurrent idempotent approval one queued job; old evidence authorization; domestic unchanged
PASS ALL requirements review real HTTP integration
```

`output/requirements-backend-final-targeted-20261013.log` 是旧失败记录，原始末尾 `1 failed, 48 passed, 2 warnings in 20.05s`，不得当通过证据。后续实际读取最终全量日志，结果为：

```text
2051 passed, 17 skipped, 15 warnings in 328.12s (0:05:28)
```

17 项跳过均是现有 Linux root、本地 skill/Bubblewrap 或非 root WSL 专用宿主条件，不代表这些能力本次通过。迁移/锁测试的代码前提已独立检查，另不虚构未收到的 PG 专项日志。

reviewer 独立运行 `pnpm typecheck`，原始输出如下，exit_code=0：

```text
> hengxin-smart-image-frontend@0.2.25 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

存在 pnpm 配置位置 warning，不影响本次 exit 0。构建命令自身也包含 `vue-tsc --noEmit && vite build`（frontend/package.json:17）。

reviewer 首次用系统 Python 运行发布测试得到 `No module named pytest`；随后使用项目 `backend/.venv/Scripts/python.exe` 正确重跑：

```text
......................................                                   [100%]
38 passed in 0.35s
```

主 Agent 独立保存的 `output/requirements-release-tests.log` 也为 `38 passed in 0.96s`。reviewer 对真实 dist 调用 collect_assets（只读）结果：

```text
pdfjs_symlink False
audited_assets 825
```

最后时间展示修复后，reviewer 再次对最终 dist 运行相同检查得到 `final_audited_assets 826`（新增日期相关拆包产物）。这证明实际打包资源通过包括 PDF.js 特例的完整资产检查；不是只以构造测试代替真实构建文件。

实际浏览器独立尝试打开 3015 时出现动态 chunk 获取失败（identity-main-D_Mvqss4.js）及空白；与主 Agent 协调确认构建曾清空 dist，未当成已证实源码缺陷。独立 fixture 登录后能进入海外，但共享身份的另一登录令任务访问转为401；随后停止浏览器操作，避免共享测试身份互相失效。视觉比对使用主 Agent 通过真实 CUA 打开的正式页和邻居页截图，由本 reviewer 实际加载像素检查，不将静态 CSS 或测试数据构造当截图。

## 修复后差异复核

1. 候选 `50af955edcb21cac24d0fec74c1b631f5774cdb80f73ec83f74a60cb179467a7`：新增 MaterialPdfThumbnail.vue:8，draw 使用 generation、前一 render cancel/等待、卸载取消；MaterialPdfReader.vue:8 添加页缩略图/选中状态、:22 使用 shallowRef 持有 PDFDocumentProxy，:23 每组最多 8 页；OverseasMaterialReader.vue:19 在弹窗内提供文件 tabs、:20 解析版本及原件/文本切换，切换 selected 不关闭窗口。M1 功能差异已修复。
2. 候选 `8eea0c6419d85ad1c1166be698795491edd3f69e5171ba1481bf9bf980382d88`：MaterialPdfReader.vue:69 阅读区/缩略图上限 min(650px,55vh)，OverseasMaterialReader.vue:18 弹窗 margin-top=4vh。infra/identity-test/checks.py 从 305 行移除重复空行至 292 行，没有语义变化，解决 skill 的 300 行上限问题。
3. 候选 `14784f355537586c46af712e4058c81bbffc32d52908a837d12bae5e3bd917cb`：requirements.ts:3 新增 formatTaskTime，OverseasRequirementsReview.vue:28、:30、:50 统一提交/审核/流转日期为中文年月日时分，非法日期显示破折号，避免原始 ISO 微秒/UTC 在商品信息区折为四行。实际 `output/requirements-qa/review-top.jpg` 为单行 `2026/10/13 12:05`，符合可读日期要求。
4. 最终候选 `bb96c6cf624acfc6aa130ea84c65b786270e6791f99006ba0d26f78eefc61a95`：scripts/release/test_package_overseas.py 仅移除文件末尾多余空行。已重新读取末尾测试，断言保留，git diff --check 无错误，review-status 的 currentId 与此号一致。

日期修复后的实际 SFC 由 reviewer 独立重跑，exit_code=0，原始输出：

```text
✔ 实际审核SFC：退回必填、确认取消、409/网络失败保留意见和幂等、通过成功 (171.024ms)
✔ 实际审核SFC：无权限隐藏操作，卸载后迟到成功不派发 (75.3111ms)
✔ 实际重提SFC：绑定资料保留、字段SKU回填、失败/409保留修改、成功回审核 (18.4051ms)
ℹ tests 3
ℹ pass 3
ℹ fail 0
ℹ duration_ms 1194.1277
```

## Stage 2：已完成的静态/测试审查

| 项目 | 证据与结论 |
|---|---|
| 命名/类型/职责/文件规模 | 新需求逻辑集中 tasks/requirements.py:12，阅读拆为主阅读/文本/PDF/缩略图；API 客户端 tasks.ts:10 定义类型、:35 校验服务端记录。扫描 60 个变更代码文件，修复后无超过 300 行文件。未发现新增生产 TypeScript any。 |
| 测试真实性 | requirements HTTP 测试使用真实身份、HTTP、PG、MinIO 与真实 PDF/DOCX/XLSX/CSV；approval 后仅排队、无启动收费 worker（infra/identity-test/requirements_checks.py:1、:142）。PG 用 Barrier/独立 session 检查锁而非 SQLite 伪并发（test_overseas_requirements_postgres.py:35）；前端编译实际 SFC 并触发 handler（overseas-requirements-component.test.ts:27），涵盖取消、空意见、409、网络失败、幂等、卸载。 |
| 旧 fixture 修改 | test_overseas_plans.py 的新 fixture 先调用真实 requirements-review 成功接口，再校验新的版本号；迁移 fixture 使用当时反射表插入，未把新版字段塞进旧 schema（test_overseas_management_migration.py）。旧图片失败重试仍保留真实重试与版本断言，未简单删除失败测试。 |
| 安全扫描 | 对全部变更生产代码搜索 eval、dangerouslySetInnerHTML、innerHTML、sk-ant/sk-proj 与 VITE KEY/SECRET/TOKEN：0 命中。测试中的 new Function 只用于编译仓库自有 SFC，不读取上传内容。MaterialTextReader.vue:14/:16 Vue 文本插值，OverseasMaterialReader.vue:61 textContent 安全写入，未将文档变为 HTML。 |
| 权限/注入/路径 | tasks/requirements.py:12 锁成员并重查任务范围，权限发生变化时重放仍需授权；materials/service.py:28 原件不绕过任务权限。新增 SQL 为固定语句，未拼业务输入。overseas-update-deploy.py:124 release 正则限制目录参数，package-overseas.py:64 拒绝 symlink、:86 精确资源校验。发布脚本中的固定 /opt 路径是部署目标，不是用户目录泄漏。 |
| 依赖核验 | frontend/package.json:79 精确 pin pdfjs-dist 6.4.299；官方 [Mozilla 发布页](https://github.com/mozilla/pdf.js/releases) 与 [npm 包页](https://www.npmjs.com/package/pdfjs-dist) 确认该正式版本存在。本次不把版本存在等同于无任何未来漏洞。 |
| Spec 漂移 | 新 RequirementsReview 表、审核/重提两接口、资料阅读器和 0010 增量发布均在本轮批准范围内；未发现额外产品功能或第二套身份系统。证据 tasks/router.py:48、tasks/models.py:73、DEV-PLAN.md:1330。 |
| 邻居页面视觉 | 实际读取 `output/requirements-qa/tasks-list.jpg` 与最终 `review-top.jpg`，1280×720 下侧栏230px、页头、品牌、蓝色按钮及标签、白卡/浅灰底保持既有正式工作区风格；审核页按批准图增加300px工作流栏、16px圆角、24px内距（OverseasRequirementsReview.vue:75），真实资料与人员信息代替示例。最终提交时间单行。 |

最终 `pdf-reader.jpg` 已实际读取像素：1280×720，弹窗顶边29px对应4vh，双文件 tabs、版本、原件/解析文本、蓝色下载按钮、PDF 页缩略图和灰底白纸均可见；阅读区自身滚动。与批准 material-reader.jpg 的主要结构匹配，真实文档内容不当作示例版式硬编码。缩略图按最多8页一组、窄屏隐藏而保留上一页/下一页是保持可用性的实现，未移除分页能力。结合审核页与邻居页实际截图比对，完成两阶段 PASS。

## 未批准范围

生产发布、收费 AI 执行和钉钉容器兼容性不属于本报告已实测结果；生产执行须由主 Agent 按已审增量脚本完成排空/备份/镜像安装测试/迁移与线上验证。IAB 原生新窗口的手工验收受浏览器能力限制：已核查 window.open 同步打开、opener=null、鉴权后 Blob/textContent、关闭/切换清理，但不声称已在 IAB 手工看见完整原生窗口。本 reviewer 未写 clean、未调用 review-approve。
