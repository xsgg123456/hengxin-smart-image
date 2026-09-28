# 单图文字替换独立审查

- 日期：2026-09-28；角色：独立 code-reviewer；只审查，未修改业务代码、提交或部署。
- candidateId：`ef78a2638abcce9111b9c4ecac6319430c49c72d92a22256c9b644e5cb1bc142`。
- 范围：本候选的单图文字创建、共用标注编辑器适配、无 Skill 内置提示词、冻结/重试/返工、契约与迁移、测试；包含 `.agents/skills/product-spec-builder/references/workflow-iteration.md:23` 用户批准的通用性能验收规则。既有壁纸、商品、API/CLI 标注链路仅审受影响部分及回归证据。
- 源要求：仓库根 `Product-Spec.md:3`、`DEV-PLAN.md:3`、`Design-Brief.md:84`；按 `.agents/skills/code-review/SKILL.md` 两阶段执行。
- **Stage 1：PASS。Stage 2：PASS。** 没有发现本候选的 HIGH/MEDIUM 阻断问题。PASS 指授权范围内的工程实现及隔离验证，**真实 CLI 生成图片的文字、字体、布局及其他画面保持效果尚未验收**，不得据此宣称生产上线或真实效果通过。
- 开始及收尾用 `review-status` 核对受控快照；报告写入前未发现代码变化，currentId 与上述 candidateId 相同。批准登记由主 Agent 执行，本报告不写 `.needs-review`。

以下文件路径除注明“仓库根”外均相对 `hengxin-smart-image/`。

## Stage 1 · Spec Compliance

### 完整实现

| Spec 条目 | 判定和代码证据 | 验证证据 |
|---|---|---|
| 原入口，一张原图，任务名必填、SKU 可选，可移除/替换 | 匹配。`frontend/src/views/hengxin/text/index.vue:1`、`components/TextCreateTask.vue:3`（后者及下文未写完整前缀的组件位于 `frontend/src/views/hengxin/`）；`components/TextCreateTask.vue:6`、`:9`、`:18`；后端 `backend/app/modules/tasks/snapshots.py:10`、`:29` | 独立浏览器上传一图、输入名称、原图预览成功；多图/空意见拒绝测试 `backend/tests/test_builtin_text_tasks.py:61` |
| 保持格式/大小限制，原图显示与编辑不降采样 | 匹配。`components/ImageUpload.vue:5`、`:84`；`components/TextCreateTask.vue:44` 使用原文件下载；`components/annotation/AnnotationEditor.vue:5` 传 naturalWidth/Height；`components/annotation/annotation-export.ts:12` 按原尺寸导出；后端 `snapshots.py:36` | 独立页面显示原图 496×749，HTTP 原文件下载 200；既有原尺寸导出测试 `frontend/tests/annotation-canvas.test.ts:99`、`:114` 在 197 测试中通过 |
| 直接复用 CLI 单张画布：框选、画笔、编号意见、缩放平移、撤销、删除、清空、提交预览 | 匹配。`components/TextCreateTask.vue:13` 直接引用 AnnotationEditor；`components/annotation/AnnotationEditor.vue:5` 直接引用 AnnotationCanvas；`components/annotation/CliAnnotationDialog.vue:3` 使用同一组件 | 独立打开新入口与邻居并截图，工具栏、编号意见、原图、预览均存在；主 Agent 已实际操作框选/画笔/撤销/缩放/平移/移除；画布几何和导出回归覆盖 `frontend/tests/annotation-canvas.test.ts:31`、`:56`、`:82`、`:168` |
| 不标注也可提交；标注各处意见必填，整体补充可选，总意见 1000 字 | 匹配。`components/TextCreateTask.vue:13` require-text/marking-optional；`components/annotation/annotation-drafts.ts:18` 每条检查及拼接后长度检查；`components/annotation/AnnotationEditor.vue:23` 动态文案 | 独立无标注预览并真实 POST 202；`frontend/tests/annotation-drafts.test.ts:6`、`:15`；后端 `snapshots.py:17`、`:32` 再校验 |
| 标注独立辅助图，不替换原图、不增加输出槽 | 匹配。`backend/app/contracts/business.py:227`、`backend/app/modules/tasks/service.py:51`、`:62`、`:65`；`backend/app/execution/materials.py:94`；`components/TextCreateTask.vue:56` | `backend/tests/test_builtin_text_tasks.py:29` 参数化无标注/标注两路径，断言单 TaskSource、单 ResultSlot、独立 annotationPath；主 Agent 浏览器标注 POST 202 且一 sources + annotationFileId |
| 新建文字不显示/查询/依赖模板和默认 Skill，无伪造 Skill | 匹配。`frontend/src/views/hengxin/use-create-task.ts:36`、`:61` 提前返回；`backend/app/modules/tasks/snapshots.py:39`；`service.py:53`；`backend/app/execution/materials.py:105` 不挂载 Skill | 无 SkillRecord 时创建、列表、详情及材料准备通过 `backend/tests/test_builtin_text_tasks.py:29`；独立浏览器请求清单没有模板/Skill 获取，文字 POST 202 |
| 内置提示词限制指定位置/指定文字、字体各属性、原布局、其他文字/商品/背景/构图/尺寸、一张输出，标注不进入成品 | 匹配。`backend/app/execution/text_prompt.py:4` 完整列出约束；`:23` 指定无标注底图，`:27` 单列定位参考图；未增加字体编辑器或局部合成 | `backend/tests/test_builtin_text_tasks.py:29` 检查冻结指令、尺寸及路径；`:118` 检查 runner 首轮/返工提示词。此项仅证明指令和编排存在，不证明模型真实遵守 |
| 示例等长/近长替换，不增加溢出检测、缩字、换行或长度确认 | 匹配。`components/TextCreateTask.vue:1` 至 `:70` 只做上传和意见适配；`backend/app/execution/text_prompt.py:4` 无新增排版流程 | 全受控 diff 未发现额外字体排版 UI、API 或依赖；独立预览使用“防窥钢化膜→张帅钢化膜，保留28°”意见 |
| 冻结原图、意见、标注、提示词版本/内容；重试不漂移 | 匹配。`backend/app/modules/tasks/service.py:56`、`:59`、`:65`；`backend/app/modules/tasks/revision_inputs.py:24`；`backend/app/execution/materials.py:34` 从任务快照取提示词；`backend/app/execution/text_prompt.py:16` 不读取新版常量 | `backend/tests/test_builtin_text_tasks.py:29` 修改当前部署指令后旧任务仍使用旧内容；`:140` 首轮失败重试保持标注，改标注 409 |
| 继续修改无 Skill，明确无标注版本为底图，CLI 同会话、版本保留 | 匹配。`backend/app/execution/materials.py:41`、`:73`、`:105`；`backend/app/execution/prompts.py:35`；`backend/app/execution/text_prompt.py:23` | `backend/tests/test_builtin_text_tasks.py:118` 实际 runner 编排、模拟 CLI 子进程，验证 resume、currentPath、两版和同 session；历史底图回归 `backend/tests/test_single_revision_materials.py:32`、`:83` |
| 历史文字 Skill 保持记录与执行语义，壁纸/商品不全局取消 Skill 校验 | 匹配。`backend/app/execution/materials.py:33` 仅 builtin_prompt 非空的新文字走内置分支，`:108` 保留旧 Skill；`backend/app/modules/tasks/snapshots.py:64` 保留模板绑定；`backend/migrations/versions/0020_builtin_text_tasks.py:12` 不重写旧数据 | 独立运行迁移 SQLite/PostgreSQL 及历史材料测试通过。`backend/tests/test_codex_runner.py:51` 明确构造历史快照，未把新入口伪装成旧能力；`backend/tests/test_skill_catalog_frozen.py:25` 转商品流程继续测绑定冻结 |
| 列表/详情适配空 Skill，输出一个位置 | 匹配。`backend/app/modules/tasks/queries.py:64`、`:84`、`:91`；`list_batch.py:42` 过滤空 id；`frontend/src/api/hengxin/validate.ts:41` 仅文字允许 null；`components/TaskTemplate.vue:13`、`:98` 使用处理方式文案 | 独立浏览器受理后任务列表/详情均 200，无页面异常；`backend/tests/test_builtin_text_tasks.py:29` 和 `frontend/tests/service.test.ts:97` 断言空 Skill/输出数/契约 |
| 更换/移除图清旧标注；草稿按身份和新建会话隔离；同会话恢复 | 匹配。`frontend/src/views/hengxin/task-creation-session.ts:20` 使用身份、类型、query 键；`:24` 换图清理草稿与新 annotationKey；`components/TextCreateTask.vue:40` 清上传缓存 | Vue 真实 setup/unmount 生命周期测试 `frontend/tests/task-creation-session.test.ts:113`、`:131`；主 Agent 浏览器移除操作清空验证 |
| 上传失败和未知提交保护，不能重复建立任务 | 匹配。`components/TextCreateTask.vue:37`、`:51`、`:65`；`frontend/src/views/hengxin/task-submission.ts:17` 保存快照与幂等键；`backend/app/modules/tasks/service.py:42` 先查幂等 | `frontend/tests/task-creation-session.test.ts:25`、`:98`、`:144` 覆盖身份改变、迟到回执及 annotationFileId 重放；主 Agent 首次503→确认原请求202，sameKey/sameBody/锁输入均 true |
| 异步进度、失败/取消保留原图与旧成品、下载/历史沿用，不付费自动重试 | 匹配受影响链路。`backend/app/modules/tasks/service.py:21` 继续 enqueue，`:79` 继续现有轮次校验；`backend/app/execution/materials.py:25` 文件校验失败会终止，未改发布/下载流程 | 全量日志通过；取消 fencing `backend/tests/test_tasks.py:100`、旧 token 拒绝发布 `:164`；新文字材料故障 `backend/tests/test_builtin_text_tasks.py:140`。未跑真实 CLI 或生产下载回归 |
| 原 API/CLI 画布兼容与视觉继承 | 匹配。`components/annotation/AnnotationEditor.vue:41` 给新文案属性默认“成品/确认提交修改”，画布和 CSS 没有修改；CLI 原入口 `components/annotation/CliAnnotationDialog.vue:3` 无改动 | 独立真实打开 CLI 修改弹框，并与新入口比较截图；API 共用编辑器回归由既有197前端测试和静态默认值检查支撑，未在此独立浏览器再次完整操作 API 提交 |

### 部分实现、未实现、引导真实性及漂移

- 授权工程范围无部分实现或未实现条目。UI 的“标注可选”“修改意见必填”“预计输出1张”“标注仅定位”均对应以上代码及隔离验证。
- **未验证项**：Spec 的真实图片效果检查未执行；`Product-Spec.md:14`、`:16` 明确要求单列该边界，真实生成又不在本轮授权内。不存在“提示词写了所以效果已通过”的推断。
- 无新增无关页面/API/表。新增 `builtin_prompt` 字段及 nullable Skill 外键是无 Skill 冻结要求所需；新 TextCreateTask 是入口薄适配，未复制画布。`frontend/src/types/import/components.d.ts:75` 的变化为移除未使用组件生成声明，类型构建通过。
- 通用规则 `.agents/skills/product-spec-builder/references/workflow-iteration.md:23` 仅新增性能验收覆盖展示质量、入口及完整等待路径的约束，与主 Agent 提供的用户授权一致，不改变产品运行行为。

## Stage 2 · Code Quality

| 检查 | 结果和证据 |
|---|---|
| 命名、类型、职责、文件大小 | PASS。新 `TextCreateTask.vue` 74 行，内置 prompt 30 行、迁移22行；本候选改变的 py/ts/vue 文件均未超过300行。`components/TextCreateTask.vue:39` 明确缓存 File/Picture，`:58` 检查 alive/draftKey；新增代码未引入 any。画布、导出、草稿、任务提交分别复用现有职责，未复制实现。 |
| 错误/竞态路径 | PASS。`components/TextCreateTask.vue:58`、`:62`、`:66` 对迟到上传按草稿键隔离；`components/annotation/AnnotationEditor.vue:49`、`:57`、`:88` 代次保护原图/预览；`task-submission.ts:18`、`:29` 将回执写回原 state 而非新身份状态。 |
| 测试真实性 | PASS。新增后端通过真实路由、持久化、材料准备及真实 runner 编排，mock 边界是付费 CLI 子进程；`backend/tests/test_builtin_text_tasks.py:92` 明确模拟，未用图片结果证明效果。前端会话测试使用真实 Vue 生命周期；几何/导出纯函数用例另有浏览器操作补充。历史 Skill 测试直接构造旧快照有清晰注释，属于兼容状态而非当前新建路径。 |
| 安全扫描 | PASS（本次 diff 范围）。扫描 eval、innerHTML/dangerouslySetInnerHTML、暴露 VITE 密钥、sk-* 密钥模式无新增命中；`backend/app/modules/tasks/revision_inputs.py:50` 限标注所属用户、可用图片与大小；`business.py:229` UUID 校验；`materials.py:25` 校验冻结内容；`text_prompt.py:29` 将意见作为 JSON 数据传入，未拼接 shell/SQL。新增迁移测试 schema 来源 uuid4，未接受外部标识符。 |
| 迁移/测试辅助改动 | PASS。`backend/migrations/versions/0020_builtin_text_tasks.py:12` 重复运行保持旧行及外键，downgrade 保留数据而不恢复非空约束，代码明确说明；不是完整物理回退。`backend/tests/test_api_image_execution_pg.py:40` 仅让独立 schema 包含现有 image_variants 表，不改变业务 schema 或弱化断言。 |
| 视觉实比 | PASS。独立在 `review-text` 会话打开3038新文字入口与3039原CLI单张修改，截图 `output/playwright/review-text-editor.png` / `review-text-neighbor.png`，均已通过 view_image 实际查看。蓝色按钮、浅色边框卡片、橙色标注约定、字号、工具布局继承组件；共用 CSS `components/annotation/AnnotationEditor.vue:100` 的24px间距、8px意见边框及900px窄屏布局未改。新页面外层采用 `TextCreateTask.vue:4` art-card 与16px任务字段间距。另实际查看主Agent768px截图 `output/text-narrow.png`，无水平溢出；右侧意见区在窄屏沿用内部滚动。 |

## 验证原始输出与边界

独立实跑（隔离 PostgreSQL 的 TEST_DATABASE_URL 指向127.0.0.1:15439专用测试库）：

```text
.venv/Scripts/python.exe -m pytest tests/test_builtin_text_tasks.py tests/test_builtin_text_migration.py tests/test_single_revision_materials.py tests/test_skill_catalog_frozen.py -q --tb=short
............................                                             [100%]
28 passed, 2 warnings in 6.29s
```

两条 warning 均为既有 Starlette/httpx/anyio 弃用提示。独立 `compileall -q app migrations/versions/0020_builtin_text_tasks.py tests/test_builtin_text_tasks.py tests/test_builtin_text_migration.py` exit 0，原始 stdout 为空；`git diff --check` exit 0，仅 Git CRLF/LF 提示，无空白错误。

读取并核对主 Agent 保存的全量日志，未重复全部长测试：

```text
# 仓库根 output/text-backend-verified.txt
1354 passed, 113 skipped, 15 warnings in 160.93s (0:02:40)

# frontend/text-task-tests.log
ℹ tests 197
ℹ suites 0
ℹ pass 197
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3484.5155

# frontend/text-task-build.log
> hengxin-smart-image-frontend@0.2.10 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 29.29s
```

构建日志包含 pnpm 配置字段弃用提示，不是本次编译失败。113项 skip 不记作通过，不扩张到未满足环境的测试能力。

独立浏览器上传/不标注提交到隔离真实 API 的网络原始结果：

```text
390. [POST] http://127.0.0.1:3038/api/v1/files => [200] OK
391. [GET] http://127.0.0.1:3038/api/v1/files/ff9e213d-3e40-4ee6-bb9b-a64a547150ac/content?download=true => [200] OK
395. [POST] http://127.0.0.1:3038/api/v1/tasks => [202] Accepted
455. [GET] http://127.0.0.1:3038/api/v1/tasks?page=1&pageSize=12&scope=all&search= => [200] OK
456. [GET] http://127.0.0.1:3038/api/v1/tasks/22e97f77-2e01-484c-ac1e-cf6d1e297efc => [200] OK
```

该浏览器后端是临时 SQLite + MemoryStore，只受理任务，不执行收费生成。带编号标注真实受理和503未知响应重放属于主 Agent 提供并结合代码/测试复核的证据；独立 reviewer 未声称再次运行全部浏览器情形。尚无真实 CLI 图片、生产部署、生产迁移或钉钉容器的本轮验收结论。
