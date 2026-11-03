# 海外 Skill 文件夹管理最终独立审查

## 快照、范围与结论

- 最终 candidateId：`78d1119ef880fd732715e5943492586eb703dd8fe2670cc1977979a447d2c892`。
- **Stage 1：PASS。Stage 2：PASS。** 结论仅适用于该代码快照，主 Agent 应通过 `review-approve` 登记；本 reviewer 未改实现、未提交、未执行生产变更，也未写 `.needs-review`。
- 范围：本任务全部 Git changed/untracked 实现、测试、前端依赖及锁文件、`scripts/release/skill-folders-*`；核对合同 `docs/SKILL-FOLDERS-IMPLEMENTATION-20261103.md:7`、`Product-Spec.md:1401`、`DEV-PLAN.md:1621`、`Design-Brief.md:236`。下文 `backend/`、`frontend/` 均相对 `hengxin-smart-image/`。
- 本报告是提交和部署前的代码验收，不声称已完成生产部署、正式入口验收或 Windows 原生目录选择器验收。交付顺序第 4 步的这些后续操作仍由主 Agent 执行。
- 使用 `.agents/skills/code-review/SKILL.md`，先完整审查 Stage 1，再进入 Stage 2。前两轮失败报告不作为批准凭据。

## 审查中版本变化及复核

初始候选为 `f1e69d7b491a5f2bf8a5b83490f8a875860a36ed6f4602768b2ef42dfb089efe`，开始时 `review-status` 与之匹配。Stage 1 未发现剩余 HIGH；Stage 2 发现 `scripts/release/skill-folders-deploy.py` 有 325 行，违反 skill 的文件不超过 300 行标准，登记为 MEDIUM 并通知主 Agent。

主 Agent 安排修复并提供最终新候选。reviewer 对审查期间保存的文件 SHA-256 再比较，代码变化只有：`skill-folders-deploy.py`、`skill-folders-runtime.py`、`skill-folders-tests.py`、新增 `skill-folders-recovery.py`；另有验证 Markdown 更新。业务实现、前端构建对应源码、依赖、后端测试未变化。

对新候选重新从 Stage 1 核对源合同、范围和交付链：恢复逻辑移入显式依赖注入模块，不新增业务功能；`scripts/release/skill-folders-runtime.py:21` 将 recovery 加入必备 helper，`:45` 校验制品完整性。继而 Stage 2 逐行复核三项恢复动作及委托，独立复跑发布测试 9 项通过。最终 deploy 277 行、recovery 62 行、runtime 73 行、tests 158 行，全部变更代码文件均不超过 300 行。原 MEDIUM 已解决，旧候选不获批准。

## Stage 1：完整实现

| 合同验收点 | 代码与验证证据 |
| --- | --- |
| 仅海外现有 Skills 页面增加入口，不改变国内业务 | `frontend/src/views/overseas/admin/OverseasLiveSkills.vue:2` 接入；`backend/app/overseas/management/router.py:12` 挂载海外路由。未增加国内入口或改国内业务模块。 |
| 一次拖入一个完整目录，递归枚举所有 readEntries 批次 | `frontend/src/views/overseas/admin/skill-folder-read.ts:14`、`:41`；`frontend/tests/skill-folders.test.ts:16` 断言 206 文件/207 条目及 4 次枚举，真实浏览器另验证 105 个同级文本。 |
| 全文件、空目录、相对路径、大小和 SHA-256 清单 | `skill-folder-read.ts:31`、`:37`、`:58`；`frontend/tests/skill-folders.browser.mjs:27` 从本地原目录独立生成 expected，`:62` 精确比对服务端全部 111 条目。 |
| 任何读取失败、路径冲突、能力缺失整体拒绝 | `skill-folder-read.ts:22`、`:26`、`:32`、`:42`；`frontend/tests/skill-folders.test.ts:24` 覆盖读取失败、缺能力、冲突和越界，未退化为漏空目录的 FileList。 |
| 目录树、数量、大小、名称、描述预览及显式上传 | `frontend/src/views/overseas/admin/SkillFolderUpload.vue:8`、`:12`、`:29`；真实 SFC 测试 `frontend/tests/skill-folders-components.test.ts:50`，浏览器 result 与截图 01/04。 |
| 原始字节与任意合法资源完整保留，不按扩展名过滤 | `backend/app/overseas/management/skill_transfer_store.py:108`、`:122`；`skill_publication.py:49`、`:55` 复制原 bytes。`backend/tests/test_overseas_skill_transfers.py:78` 验证二进制含 00/FF、空目录和完整回读。 |
| 有效 YAML name/description；正文首个 H1，无 H1 回退 name | `frontend/src/views/overseas/admin/skill-folder-metadata.ts:16`、`:23`、`:34`；`backend/app/overseas/management/installed_tree.py:94`、`installed_catalog.py:63`。前端 YAML/标题回归 `frontend/tests/skill-folders.test.ts:95`，服务端标题测试及 Linux 最终日志均通过。本地不支持的 YAML 明确显示待服务器校验，未改写源文档。 |
| 缺失的明确包内资源拒绝；真实空目录链接、围栏示例不误拒 | `backend/app/overseas/management/installed_tree.py:131` CommonMark 链接解析，`:152` 历史 reader 接受目录条目；`skill_transfer_store.py:16` 对新包全部本地链接检查并防越界。`backend/tests/test_overseas_skill_transfers_failures.py:173`、`:190`、`:206` 覆盖缺失/嵌套/编码/reference-style/空目录/围栏，并通过 upload→install→catalog 实际链路。 |
| 外部依赖不冒充实际运行已验证 | `frontend/src/views/overseas/admin/SkillFolderUpload.vue:21` 明示完整性与实际运行的边界；包内脚本没有执行入口。 |
| 单文件64 MiB、整包256 MiB、1000文件、2000条目 | `backend/app/overseas/management/skill_transfer_schema.py:8`、`:24`、`:46`；前端 `skill-folder-read.ts:9`。`backend/tests/test_overseas_skill_transfers.py:143` 的超限清单断言 422 且暂存根无新增项。 |
| 暂存、服务器校验、安装副本复核清单与哈希 | `skill_transfer_store.py:144`、`:153`；`skill_publication.py:49`、`:65`、`:81`。篡改、复制失败和指针失败见 `backend/tests/test_overseas_skill_transfers_failures.py:44`、`:58`、`:173`，失败没有发布损坏包。 |
| 新增默认关闭、未分配平台；更新保持原配置 | `skill_publication.py:176` 仅新包重置可用性，更新不改现有行；`backend/tests/test_overseas_skill_transfers.py:78`、`:99` 精确断言 enabled/platforms。 |
| 持久状态、查询、失败重试、请求幂等、并发串行 | `skill_transfer_store.py:66`、`:76`、`:80`；`skill_publication.py:118`、`:152`；`skill_publisher.py:19`、`:137` 的进程锁与 asyncio 锁。`backend/tests/test_overseas_skill_transfers_failures.py:22`、`:79`、`:147` 验证重启、响应丢失和两个并发发布。 |
| 权限：写入同开关且 skills.manage，下载 skills.manage | `skill_transfer_router.py:11`、`:14`、`:60`、`:65`；root publisher 在 `skill_publication.py:19` 再鉴权。`backend/tests/test_overseas_skill_transfers.py:131` 验证普通管理读取与禁止上传，修改请求保持 browser guard。 |
| 同名同内容幂等；不同内容列增删改并明确确认 | `skill_transfer_store.py:158`、`skill_publication.py:169`；`SkillFolderUpload.vue:14`、`:17`、`:80`、`:99`。组件测试及真实浏览器在点击确认前核对旧 checksum 未变，见 browser `:91`。 |
| 新轮用新包；已提交、排队、在途、重试继续旧冻结版本 | `skill_publication.py:133` 与已有 `backend/app/overseas/studio/service.py:37` 共用 admission gate，旧 release 不删除；`installed_catalog.py:125`、`:135` 按固定 release/checksum 冻结读取。更新/删除后的旧 bytes 由 `test_overseas_skill_transfers.py:99`、`:121` 与真实浏览器旧 release 下载断言验证；不是实际生产付费执行验收。 |
| 仅保存为文件夹，无 ZIP；选择父目录后原 rootName 建根，历史回退 name | `frontend/src/views/overseas/admin/SkillFolderActions.vue:3`、`:27`；`skill-folder-save.ts:66`、`:71`；`backend/app/overseas/management/skill_downloads.py:15`。不存在 ZIP 交互/API。 |
| 导出固定版本，完整子目录/空目录/原始文件，逐文件读回且全树清单一致才成功 | `skill_downloads.py:19` 固定 release 并核 SHA；`skill-folder-save.ts:116`、`:139`；`SkillFolderActions.vue:23`。真实浏览器 OPFS 句柄核验 savedEntries=111 与原目录完全相等，含中文和二进制。 |
| 目标同名不覆盖；中断明确不完整，可核验重试；不增加系统文件 | `skill-folder-save.ts:71`、`:101`、`:145`；`SkillFolderActions.vue:25`、`:40`。`frontend/tests/skill-folders-save-conflicts.test.ts:19` 起的10项检查已有文件、外来空文件/目录、替换句柄、用户编辑和 writer 等待窗口；组件 `:106` 验证重试复用首次 release/句柄。包内无额外标记文件。 |
| 取消目录选择不导出，能力不支持明确说明 | `skill-folder-save.ts:66`、`SkillFolderActions.vue:30`、`:36`；`frontend/tests/skill-folders-components.test.ts:97` 断言取消时 package 请求为0。 |
| 行删除二次确认名称、影响、取消/确认 | `SkillFolderActions.vue:41`、`:48`；`frontend/tests/skill-folders-components.test.ts:78`；真实截图03和浏览器取消后 catalog 数量不变。 |
| 删除从当前、全部平台、新轮移除；确认期间变更冲突；可删最后一项 | `skill_publication.py:190`、`:206`、`:209`；`installed_catalog.py:95` 合法空目录/空发布读取。`test_overseas_skill_transfers.py:121` 验证版本冲突、删除重放、空目录及重装默认状态；浏览器最后项删除为空且旧 bytes 仍可读。 |
| 删除与移出平台明确区分 | `frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:22` 同时保留编辑/移出平台和独立删除组件；`:25` 解释移出平台仍保留文件历史。 |
| API 正式目录只读；root独立受控UDS；输入有界；拒绝链接/特殊/越界；不执行包脚本 | `skill_transfer_router.py:1`、`skill_publisher.py:125`、`skill_transfer_client.py:12`、`installed_tree.py:27`、`:47`、`:65`。最终 Linux UID10001/0660/拒绝UID65534的原始证据见下文。 |
| 发布失败可恢复、记录操作者、保持现有字节和配置 | `skill_publication.py:88`、`:138`，故障注入覆盖事务/指针/状态保存；`scripts/release/skill-folders-deploy.py:56` 基线与配置比对、`:134` 备份；`skill-folders-recovery.py:15`、`:34` 保留新冻结包且不回卷数据库。实际只读旧包17个/433条可读。 |
| UI继承现有卡片/表格/弹窗、蓝主操作/红删除、树可展开滚动、窄屏与过滤语义 | `OverseasSkillCatalog.vue:2`、`:40`、`:51`；`SkillFolderUpload.vue:2`、`:127`；`SkillFolderActions.vue:5`、`:66`。reviewer 独立打开 Skills、上传弹窗、邻居系统配置页比较实际渲染，并检查390×844关闭侧栏后的弹窗及底部操作，详见 Stage 2。 |

部分实现：无。未实现：本次送审代码范围内无。Spec 漂移：未发现；新增 transfer/publication/download API 与受控发布服务均由合同第 3、5、7 项授权，恢复模块是既定发布流程拆分。

## Stage 2：代码质量、安全和测试真实性

- **代码组织 PASS**：上传 schema/store、发布事务、UDS 服务、下载、前端扫描/元数据/保存/界面职责分开；恢复模块显式接收同一 runtime 和 gate 函数，避免重新加载错误的发布常量。证据：`scripts/release/skill-folders-deploy.py:247`、`skill-folders-recovery.py:6`、`:15`、`:34`，发布测试 `skill-folders-tests.py:110`。全变更代码行数检查、Python compile 均通过；未发现新增 TypeScript `any`。
- **错误路径 PASS**：上传校验后再次 install 复核，失败状态持久化；已提交审计用于恢复丢失响应；删除未知结果先读回确认，不误报成功。证据：`skill_publication.py:124`、`skill_publisher.py:94`、`SkillFolderActions.vue:53`。独立后端29项与前端28项复跑通过。
- **安全扫描 PASS（本次变更）**：扫描变更实现/测试/发布脚本的密钥、eval、HTML注入、前端暴露密钥模式；未发现实际密钥、动态执行包内容或新增不安全HTML渲染。`skill-folder-metadata.ts:23` 仅解析数据，Vue插值展示文本；`skill_transfer_schema.py:30` 校验路径；`installed_tree.py:47` 拒绝符号/硬链接和特殊文件；下载校验固定清单 `skill_downloads.py:22`。部署中绝对路径是固定海外目标，`skill-folders-runtime.py:24`，没有从上传根名构造主机部署位置。
- **权限隔离 PASS**：socket主目录 root:10001/0750、socket0660，发布服务无公开端口、只读容器文件系统、专用可写挂载，业务API只读挂载socket。publisher仅复制所需数据库和权限配置，MinIO/Redis等必填项使用无凭据占位。证据：`skill_publisher.py:139`、`scripts/release/skill-folders-deploy.py:30`、`:142`；真实最终权限日志验证同一运行形态。
- **发布范围与完整性 PASS**：固定API10模块/native2个reader，不迁移schema；prepare拒绝基线或无关配置漂移，candidate不能关闭生产入口，release需要已审已提交源码；制品拒绝多余/缺失文件及错误哈希。证据：`skill-folders-runtime.py:14`、`:38`；`skill-folders-package.py:17`、`:30`、`:59`；`skill-folders-deploy.py:20`、`:56`、`:118`。最终9项发布测试包含recovery缺失、委托及candidate拒绝；发布打包工具不新增包内Skill文件。
- **测试真实性 PASS**：后端测试使用真实API与publisher应用、临时目录及数据库，故障注入位于复制/rename/commit/state-save等实际边界；前端组件测试编译真实SFC，但Element控件被测试替身替换，因此另核真实浏览器。浏览器使用CDP原生目录拖入，文件与空目录来源于真实磁盘；保存仅替换系统选择器，内部为真实Chrome OPFS句柄。证据：`backend/tests/test_overseas_skill_transfers.py:23`；`frontend/tests/skill-folders-components.test.ts:10`；`frontend/tests/skill-folders-browser-helpers.mjs:4`、`:19`；`frontend/tests/skill-folders.browser.mjs:54`、`:65`。并未把内存文件系统单测冒充Windows落盘验收。
- **实际视觉比较 PASS**：reviewer 使用 CUA 在 `http://127.0.0.1:3054/#/overseas/admin/skills` 和邻居 `/#/overseas/admin/settings` 实际打开比较，白卡、边框圆角、标题层级、页面留白、蓝色操作与既有页面一致。上传对话框760px上限、94vw，树/差异280px滚动区、按钮8px间隔与源码一致，见 `SkillFolderUpload.vue:2`、`:127`。独立查看稳定截图02保存成功、03删除确认、04差异；390×844时主动关闭已有侧栏遮罩，确认上传入口、换行、树滚动、差异内容和底部关闭/查询按钮可达并成功关闭。旧05截图有侧栏遮挡，不能单独证明窄屏完成；本次实际操作补足该项。未改UI或业务数据，最后恢复浏览器视口。

## 编译与测试原始输出

构建日志 `output/skill-folders-frontend-build.log` 的命令头及最终输出（中间资产清单省略，未改写原始输出）：

```text
> hengxin-smart-image-frontend@0.2.63 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4807 modules transformed.
✓ built in 34.36s
```

全前端日志 `output/skill-folders-frontend-all-final.log`：

```text
ℹ tests 514
ℹ suites 0
ℹ pass 514
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10897.285
```

reviewer 独立运行前端扫描/导出冲突/组件专项：

```text
ℹ tests 28
ℹ suites 0
ℹ pass 28
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1184.0271
```

reviewer 独立运行后端 `test_overseas_skill_transfers.py` 与 `test_overseas_skill_transfers_failures.py`：

```text
29 passed, 2 warnings in 18.71s
```

核对既有日志 `output/skill-folders-backend-final.log`、`output/skill-folders-release/linux-final.log`：

```text
40 passed, 2 warnings in 21.76s
51 passed, 2 warnings in 26.71s
```

上述2条warning为既有Starlette/httpx与anyio弃用警告，不是用例跳过。最终Linux镜像 `9f179268423d729c` 含最新CommonMark reader。

reviewer 对最终拆分后候选独立执行 `python scripts/release/skill-folders-tests.py` 和变更Python编译/行数检查：

```text
.........
----------------------------------------------------------------------
Ran 9 tests in 0.936s

OK
changed code files <=300 lines: PASS; changed Python compile: PASS
```

最终实际权限与旧包只读日志：

```text
{"image": "hengxin-skill-folders-test:9f179268423d729c", "productionShapedPaths": true, "apiUid": 10001, "socketMode": "0660", "minimalEnvironmentStartup": "PASS", "apiReadOnlyCatalogAndSocket": "PASS", "unauthorizedUid": "DENIED"}
{'release': 'e567660e4a4008bc59e9ad006ec5badd2f05f3888933ac53013542edc9411368', 'packages': 17, 'entries': 433}
```

真实浏览器 `output/playwright/skill-folders/result.json`：6项检查通过、`errors: []`、`entries: 111`、`savedEntries: 111`。浏览器使用最终前端构建和358116fe29283ef2隔离后端；之后reader修复由最终Linux51项和旧17包只读测试覆盖，该边界不隐藏。

## 已知边界，不扩大通过声明

- 保存以完整目录、字节、哈希为验收对象，不保证本地ACL/创建时间或外部依赖能运行；代码及提示证据 `SkillFolderUpload.vue:21`、`skill-folder-save.ts:116`。
- File System Access没有本实现可用的原子独占创建/CAS。已检查首次、下载等待、writer创建、重试阶段的冲突，但不能宣称抵抗任意外部进程在最终检查后同时改文件。实现注释 `skill-folder-save.ts:108` 和10项冲突测试如实界定；相关接口标准见 [WHATWG File System](https://fs.spec.whatwg.org/)。
- 新增YAML固定2.9.1，官方发布说明包含递归merge alias限制，预览另设长度与alias预算；参见 `frontend/package.json:90`、`skill-folder-metadata.ts:6`、`:25` 及 [yaml 2.9.1发布说明](https://github.com/eemeli/yaml/releases/tag/v2.9.1)。现有依赖审计仍有历史high73/moderate54/low11，不能称依赖全零风险；本次不将历史依赖治理扩入需求。
- 生产发布、已审制品正式安装、真实入口及Windows原生目录选择窗口仍需主 Agent按交付顺序验证。此报告不替代这些操作。

最终判断：没有剩余HIGH/MEDIUM审查缺陷；同一最终候选两阶段PASS，可进入快照批准与后续已授权交付。
