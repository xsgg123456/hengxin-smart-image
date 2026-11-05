# 海外批量标注功能审查 · 2026-11-05

## 快照、范围与结论

- candidateId：`bf83c9582a4f9210e63c38c9ee32b75a96ea514c562694586419142538b474c6`。
- 依据：`docs/STUDIO-BATCH-ANNOTATION-20261105.md:1`、`Product-Spec.md:1`、`Design-Brief.md:1`、`DEV-PLAN.md:1`；使用 `.agents/skills/code-review/SKILL.md`。
- 范围：后端 studio 的 schemas/image_edits/image_edit_history/service/queries 与新增 references 测试；前端 studio/editing、use-revision-actions、use-studio、composer-draft、studio-revisions、OverseasStudio、StudioTurns、RevisionDetails/Draft、API 契约及相关测试。发布脚本由另一 reviewer 审查，本报告不批准其内容。
- Stage 1：功能实现逐项匹配，未发现 HIGH 产品缺失或安全问题；合同验收项仍有待补证据，不能据此宣布整轮完成。
- Stage 2：代码质量、安全扫描及桌面视觉检查完成；暂不登记 PASS，等待下列验证缺口关闭。
- 审查开始、中途、定向测试结束时 `review-status` 的 currentId 均为上述 candidateId；当时未发现快照漂移。任何后续代码或测试修改均需新 candidateId 和差异复核。

## 待完成验证

1. **MEDIUM · 响应式真实图片截图不完整。** `frontend/tests/studio-batch-annotation.browser.mjs:122`、`:125` 打开批量弹窗后立即截图。已目视 `output/playwright/studio-batch/batch-1440.png` 和 `batch-390.png`，六张图片均仍为“正在读取图片…”。目前只能证明加载态排版，不能证明这两个宽度的真实图片呈现。应等待全部 image 的 blob URL 与非零尺寸后重新截图、目视。1920 批量与单张、历史及390参考用途区域已有有效截图。这是证据缺口，不据此推断生产加载失败。
2. **MEDIUM · 后端完整回归尚未收敛。** 最终结果为 `9 failed, 2726 passed, 430 skipped, 6 warnings in 522.69s (0:08:42)`（`output/batch-annotation-preview/backend-regression.log:472`）。已读堆栈：1项路由白名单漏列既有skill-transfers等管理接口（`:134`），7项`safe open unavailable`为Windows缺POSIX dir_fd/O_NOFOLLOW安全打开能力（`:203`等），1项创建symlink触发WinError1314（`:337`）。相关失败实现不在本轮业务diff；仍需既有基线归因及Linux隔离环境补验，不能称全量通过，也不应为验收削弱安全打开保护。
3. **待验收 · PG 集成尚无执行证据。** 三项 PG 测试已实现于 `backend/tests/test_studio_image_references_postgres.py:34`、`:38`、`:42`，检查其 fixture 确实覆盖 get_session 为 pg_factory；本次尚未收到隔离 PG 执行结果。生产打包、部署、正式入口验证属于合同后续发布阶段，由主 Agent 与发布 reviewer 完成，未执行部分不算已有产品缺陷。

以下代码路径均以 `hengxin-smart-image/` 为前缀，除非明确写为根目录文档/output。表格省略前缀的 `editing/*` 和 Studio/use/studio 文件均位于 `frontend/src/views/overseas/studio/`；后端 schemas/service/queries/image_edits/image_edit_history 均位于 `backend/app/overseas/studio/`。

## Stage 1 · 功能逐项对照

| 合同条目 | 结论与实现证据 | 行为证据 |
|---|---|---|
| 交互1：每组入口、任意真实图片数 | 匹配。`frontend/src/views/overseas/studio/StudioTurns.vue:13` 传 turn.pictures；`editing/board-layout.ts:2` 按数量计算列数和适应比例，无固定六张数组 | `frontend/tests/studio-editing-state.test.ts:11` 覆盖1/6/12/100张 |
| 交互1：缩放、平移、选择、框选、画笔、撤销 | 匹配。`editing/BatchBoard.vue:4`、`:44`、`:52`、`:76`、`:21`；坐标按实际解码尺寸映射，越界点截在图片内 | 浏览器脚本`:29`真实鼠标画框/画笔；1920截图显示两处不同标注 |
| 交互1：双击/精细编辑、上一张下一张/返回、共享状态 | 匹配。`editing/BatchBoard.vue:94`、`editing/EditorDialog.vue:6`、`:8`、`:54` 共用 draftFor | browser日志“同区进入单图精细标注”；state测试`:22`证明共享替换 |
| 交互1：1380/1640和既有风格 | 匹配。`editing/EditorDialog.vue:2`；`editing/style.css:1` 保留2.65fr/1fr、24px间距；蓝色变量、橙色既有 AnnotationMarks | 目视正式1920、批准custom-purpose截图，并实际打开 baseline=1 原单张编辑器比较；1440/390完整加载见待验证项 |
| 交互2：用户/任务/会话/图片隔离 | 匹配。`studio-revisions.ts:20` 四元组 key，`OverseasStudio.vue:105` 按图片建草稿；`use-revision-actions.ts:60` 校验任务/会话/可编辑性 | state测试`:22`；batch-revisions测试`:73` 验证迟到上传仅回原会话 |
| 交互2：批量仅有标注、每处必填、参考-only排除并保留 | 匹配。`editing/EditorDialog.vue:56`、`:58`、`:81`；`editing/state.ts:43`；排除不调用forgetDraft | browser日志“标注缺少意见阻止提交”“未标注仅参考图明确排除”“核对仅2和4张” |
| 交互2：其他原图不替换；单张可无标注带回补意见 | 匹配。`editing/EditorDialog.vue:83` 单张targets不依赖marked；`use-revision-actions.ts:88`仅设置选中原图ID；`use-studio.ts:28`要求发送前补意见 | 新增代码未修改Picture；旧单张契约测试保留；state快照测试`:89`确认原图URL未替换 |
| 交互3：JPG/PNG/WebP、20MiB、预览/替换/删除/坏图重试 | 匹配。`editing/ReferencePanel.vue:5`、`:8`、`:12`、`:33`；`editing/state.ts:62`校验大小和解码；后端`image_edits.py:24`再校验 | state测试`:56`、`:71`；后端validation测试`:103`、`:118`通过真实三种编码和20MiB/+1字节文件 |
| 交互3：三种用途、自定义2000字多行非空、说明必填2000字 | 匹配。`editing/ReferencePanel.vue:14`、`:17`、`:20`；`editing/state.ts:48`；后端`schemas.py:10`双端校验 | 后端validation测试`:25`非法枚举、空白、2001字均422且无新job；reference测试`:52`完整长文本 |
| 交互3：切换预设保留自定义草稿，只发送当前用途 | 匹配。`ReferencePanel.vue:15`仅v-if隐藏；`use-studio.ts:155`只为custom发送自由用途；`schemas.py:28`预设清除customPurpose | browser日志“切换用途保留自由文字”；batch-revisions测试`:47` |
| 交互4：确认核对、真实原尺寸上传、不自动发送 | 匹配。`EditorDialog.vue:33`、`:85`；`editing/state.ts:93`实际解码尺寸exportAnnotation；`use-revision-actions.ts:65`实际api.upload，`:88`回填，不调用send | browser multipart字节解析`:60`，带回时sends为0；state测试`:89`验证自然尺寸1200×1600而非元数据120×160 |
| 交互4：半批失败、重试、继续编辑/取消/更新去重、清空移除 | 匹配。`use-revision-actions.ts:43`先准备局部next；`:85`全部成功后统一提交；WeakMap复用成功文件；`:20`取消只清对应图；groupIds支持空批删除 | batch-revisions测试`:35`在第二张标注上传失败后证明旧摘要不变，重试总4次；`:60`验证清空到0及普通附件保留 |
| 交互4：关闭保留、确认材料持久化、切换/刷新、未知请求复核 | 匹配。`EditorDialog.vue:73`关闭不清草稿；`studio-composer-draft.ts:31`保存冻结marks/references，`:44`恢复；`use-studio.ts:109`原pending body/key重试 | browser日志关闭重开、刷新恢复、跨会话、未知响应刷新后原请求；batch-revisions测试`:47`未确认编辑不污染已确认材料 |
| 交互5：原图/标注/逐图参考文件和用途发送，Codex语义 | 匹配。`use-studio.ts:155`；`image_edits.py:40`校验索引身份，`:66`说明原图基础、标注定位、三种参考用途及不得画入成品 | references测试`:52`经真实HTTP、context_assets register/restore、HANDLER.prepare检查同名不同文件字节与路径；`:128`篡改拒绝 |
| 交互5：4000字及顶层100/100 | 匹配。`editing/state.ts:45`对完整带编号文本计数；`schemas.py:36`、`:44`；`use-revision-actions.ts:54`上传前限制 | state测试`:40`；已有发送/上传限制回归在527通过中 |
| 交互6：历史逐图完整信息、发送时冻结、后续改名/移除不污染 | 匹配。`image_edit_history.py:5`白名单DTO，`:13`冻结名字/类型/大小；`queries.py:115`接入；`studio-revisions.ts:7`按ID还原；`StudioTurns.vue:22`历史入口 | references测试`:94`改Upload/Picture名字并隐藏素材后历史DTO和文件字节不变；browser历史核对完整自定义用途 |
| 交互6：旧消息/旧草稿/旧幂等摘要 | 匹配。`schemas.py:37`默认空，`service.py:21`从摘要剔除空references；`image_edit_history.py:10`旧payload默认空；`studio-composer-draft.ts:74`兼容缺少referenceImages | references测试`:114`核对旧fingerprint精确相等并显式空references重放同响应 |
| 实施2：权限、绑定、无需新表 | 匹配。`service.py:84`按当前会话解析附件和图片；`queries.py:20`、`:36`、`:52`权限/归属；`image_edits.py:20`引用ID和inputIndex共同冻结；无模型/迁移改动 | validation测试`:60`跨任务、跨会话、缺失、坏图、文档均拒绝且无新job |
| 实施3：真实组件/API、无模拟生成与三维旋转 | 匹配。`OverseasStudio.vue:61`导入正式EditorDialog，`:118`confirmRevisions；生产editing目录无演示数组、计时模拟发送或新生图API | browser脚本拦截API只存在tests；正式实现调用既有上传/发送 |
| 实施1/4/5：源文档、验证、发布 | 源文档已同步；验证和发布仍进行中，见待完成验证，不能将整个合同标记完成 | 根目录Spec/Brief/Plan头部及本报告界限 |

## Stage 2 · 质量、安全、测试真实性

- **结构/类型：通过。** 新逻辑拆为草稿状态、批量画布、图片读取、参考面板、提交事务和历史DTO。生产范围文件均低于300行；现有最大改动文件 `frontend/src/views/overseas/studio/use-studio.ts:1` 为236行，`backend/app/overseas/studio/queries.py:1` 为193行。新增TS无显式any，审查者独立类型检查退出0。
- **安全：未发现新增漏洞。** 生产变更扫描硬编码密钥、eval、innerHTML/dangerouslySetInnerHTML、VITE密钥变量及个人绝对路径，无相关命中。`StudioRevisionDetails.vue:8`、`editing/RevisionDetails.vue:7`以Vue文本插值展示用户意见；`image_edit_history.py:5`仅白名单输出，不泄露inputIndex、bucket、object_key。引用仍经`service.py:84`与`queries.py:36`身份和会话检查，未新增SQL拼接或权限绕过。
- **测试真实性：关键路径成立，环境界限保留。** 状态单测包含mock Image/Canvas，不能独立证明真实解码；实际浏览器补充真实图片解码、鼠标标注、multipart文件字节和工作台交互。浏览器API响应使用拦截fixture，不能声称已连真实后端；后端HTTP测试补足schema、事务拒绝、冻结字节、权限与提示词。PG仍待实跑。具体位置：`frontend/tests/studio-editing-state.test.ts:89`、`studio-batch-annotation.browser.mjs:43`、`backend/tests/test_studio_image_references.py:52`。
- **视觉：桌面通过，响应式证据待补。** 实际打开 `http://127.0.0.1:3036/preview-batch-annotation/index.html?baseline=1` 并进入旧单张编辑器；与正式single-desktop、batch-desktop、history截图及已批准custom-purpose截图目视比较。白底弹窗、按钮高度/边框、工具栏、橙色标注、右侧间距一致；生产右侧参考内容为已批准新增内容。数值证据：`editing/EditorDialog.vue:2`、`editing/style.css:1`、`:6`；1440/390见待完成验证。
- **Spec漂移：未发现。** 没有新增表、迁移、收费生成调用或额外页面。独立预览目录为本轮已批准设计依据，正式UI不导入该目录；`frontend/package.json:3`版本递增属于已授权发布准备，不构成新增产品能力。

## 编译与测试原始输出

审查者独立执行，工作目录为 frontend：

```text
> .\node_modules\.bin\vue-tsc.cmd --noEmit
[stdout/stderr 均为空]
exit_code: 0
```

审查者独立执行，工作目录为 backend：

```text
> .\.venv\Scripts\python.exe -m pytest tests/test_studio_image_edits.py tests/test_studio_image_references.py tests/test_studio_image_references_validation.py -q
.......................................................                  [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
55 passed, 2 warnings in 22.95s
exit_code: 0
```

读取主 Agent 构建和全前端回归日志的原始末尾（非 reviewer 重跑）：

```text
# output/batch-annotation-preview/production-build.log
✓ built in 40.48s

# output/batch-annotation-preview/production-regression.log
ℹ tests 527
ℹ suites 0
ℹ pass 527
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 13697.3482
```

`production-browser.log` 审查时共有24项PASS，包含真实组件交互与未知请求恢复；不是最初交接所称25项。后端全量、PG与部署未验证结论不得由以上局部结果替代。主 Agent 尚不得按本报告登记两阶段PASS；补齐证据/归因后需复核同一或重新固定的快照。
