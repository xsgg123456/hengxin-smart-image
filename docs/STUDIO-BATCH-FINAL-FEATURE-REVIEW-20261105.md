# 海外批量标注 · 最终业务范围审查（2026-11-05）

## 快照、范围与结论

- 送审 candidateId：`3f9cbe9feb82fd582b56cd1cdedae3f855273ed99c9400be8e0ce7ddc733604a`。
- **Stage 1：PASS；Stage 2：PASS。仅适用于下述业务范围。** 未发现本范围 HIGH / MEDIUM 阻断问题。
- 本次为 fresh 独立审查：全读合同、读取业务实现与测试、检查原始验证日志、目视六张正式组件截图、实际打开批准预览及旧单图基准、独立执行类型检查与后端定向测试。不是沿用上一报告的待定结论。
- 依据：`docs/STUDIO-BATCH-ANNOTATION-20261105.md:1`；`Product-Spec.md:1`、`Design-Brief.md:1`、`DEV-PLAN.md:1`；`.agents/skills/code-review/SKILL.md:1`；`docs/HARNESS-REVIEW.md:1`。
- 前端范围：`src/api/overseas/studio.ts`；`src/views/overseas/studio/editing/*`、`StudioRevisionDetails.vue`、`use-revision-actions.ts`、`OverseasStudio.vue`、`StudioTurns.vue`、`StudioRevisionDraft.vue`、`studio-composer-draft.ts`、`studio-revisions.ts`、`use-studio.ts`；新增浏览器/草稿/事务测试及既有五个测试适配。
- 后端范围：`app/overseas/studio/{schemas,image_edits,queries,service,image_edit_history}.py`、三份新增 references 测试。
- 不包含发布工具、正式镜像安装测试、生产切换或线上验收；独立预览此前已有单独审查，本次只把它作为视觉依据。合同实施步骤5属于后续发布阶段，未执行不记为已完成。
- 开始及业务审查结束前读取 `review-status`，currentId 均为上述编号。主 Agent 随后通知发布范围存在 HIGH 并正在修复，因此全局 candidate 将变化。**本报告不能直接批准变化后的全局快照**；必须固定新 candidate，确认下述业务摘要不变，并取得发布范围独立 PASS 后再登记 `review-approve`。业务文件变化则需复审差异。
- 报告写入后的最终只读检查已观察到全局 currentId 变为 `f9ab9668a48506c956d94ff22d296c888e4c7e966edad6c9270572c1215446b4`，新增发布恢复状态文件在范围外；业务33文件与本报告摘要逐个比对一致。此编号只是审查中状态记录，仍须主Agent固定最终候选并关联审查。

以下路径以 `hengxin-smart-image/` 为根；`F/` = `frontend/src/views/overseas/studio/`，`B/` = `backend/app/overseas/studio/`。根目录 docs/output 不加此前缀。

## Stage 1：合同逐项对照

| 合同条款 | 结论与代码证据 | 验证证据 |
|---|---|---|
| 交互1：每组批量入口，真实图片，任意组大小 | 完整实现。`F/StudioTurns.vue:13`传完整 turn.pictures；`F/editing/board-layout.ts:2`按数量计算布局；`F/editing/use-board-images.ts:13`读取真实图片并使用解码尺寸 | `frontend/tests/studio-process-component.test.ts:79`核对完整组、不改变归档勾选；`studio-editing-state.test.ts:11`覆盖1/6/12/100张 |
| 交互1：选择、框选、画笔、撤销、缩放和平移 | 完整实现。`F/editing/BatchBoard.vue:4`、`:21`、`:44`、`:52`、`:76`，原图坐标映射并限制在边界内 | 浏览器脚本`:29`鼠标真实绘制，正式batch-desktop截图第2/4张显示框与笔迹；状态校验和既有AnnotationCanvas复用 |
| 交互1：双击/精细编辑、前后图、返回整组共享状态 | 完整实现。`F/editing/BatchBoard.vue:94`；`F/editing/EditorDialog.vue:6`、`:8`、`:54`共用draftFor | 浏览器“同区进入单图精细标注”通过；`studio-editing-state.test.ts:22`证明数组替换共享 |
| 交互1：1380/1640弹窗与批准设计 | 完整实现。`F/editing/EditorDialog.vue:2`；`F/editing/style.css:1`为2.65fr/1fr、24px间距，`:7`窄屏滚动与固定footer | 目视1920/1440/390六张正式截图；实际打开批准批量预览及baseline=1旧单图对照，见视觉检查 |
| 交互2：用户/任务/会话/图片隔离 | 完整实现。`F/studio-revisions.ts:20`四元组键；`F/OverseasStudio.vue:105`建立逐图草稿；`F/use-revision-actions.ts:60`确认时校验原任务/会话及可编辑性 | `studio-editing-state.test.ts:22`隔离；`studio-batch-revisions.test.ts:73`迟到上传；浏览器跨会话不串材料 |
| 交互2：批量只带有标注图，每处必填，参考-only提示排除并保留 | 完整实现。`F/editing/EditorDialog.vue:56`、`:58`、`:81`；`F/editing/state.ts:43`，排除路径不清草稿 | 浏览器核对只含2/4张、标注空意见阻断、仅参考图明确提示；batch-desktop核对标注计数2/6 |
| 交互2：不替换其余原图；单张无标注仍可带回 | 完整实现。`F/editing/EditorDialog.vue:83`单张targets独立于marked；`F/use-revision-actions.ts:88`只回填指定引用；`F/use-studio.ts:28`发送前要求整体意见 | `studio-editing-state.test.ts:89`证明原图URL不替换；既有单张回归保留；发送payload只含p2/p4 |
| 交互3：JPG/PNG/WebP、20MiB、放大/替换/删除/坏图重试 | 完整实现。`F/editing/ReferencePanel.vue:5`、`:9`、`:11`、`:12`、`:33`；`F/editing/state.ts:62`检查类型/实际大小/解码；`B/image_edits.py:24`再次校验 | `studio-editing-state.test.ts:56`、`:71`错误/重试/替换竞态；`backend/tests/test_studio_image_references_validation.py:103`真实三种图片，`:118`实际20MiB与+1字节边界 |
| 交互3：三种用途，自定义多行/非空/2000字，每种说明非空/2000字 | 完整实现。`F/editing/ReferencePanel.vue:14`、`:17`、`:20`；`F/editing/state.ts:48`；`B/schemas.py:10` | 浏览器空自定义阻断及多行保留；后端validation`:25`空白/非法枚举/2001字拒绝且无新job；references`:52`完整长文本进入真实提示词 |
| 交互3：切预设保留隐藏自定义，只发送当前用途，逐图绑定 | 完整实现。`F/editing/ReferencePanel.vue:15`只隐藏字段；`F/use-studio.ts:155`按当前kind序列化；`B/schemas.py:28`预设清空customPurpose；`B/image_edits.py:20`冻结逐图索引 | 浏览器切换用途不丢字；`studio-batch-revisions.test.ts:47`预设不发送隐藏内容；后端同名文件字节与路径绑定断言 |
| 交互4：先核对、原尺寸上传、回输入卡片、不自动发送 | 完整实现。`F/editing/EditorDialog.vue:33`、`:85`；`F/editing/state.ts:93`实际naturalWidth/Height导出；`F/use-revision-actions.ts:65`上传、`:88`提交卡片 | 浏览器捕获真实multipart并核对参考原字节、上传4文件、sends=0；state`:89`验证解码1200×1600而非元数据120×160 |
| 交互4：失败保留、半批原子性与重试 | 完整实现。`F/use-revision-actions.ts:43`保留旧状态，`:70`本地准备next，`:85`全部成功后统一写回；WeakMap缓存已成功文件 | `studio-batch-revisions.test.ts:35`第二张失败仍保留旧摘要，重试只4次成功上传；浏览器上传503后零半批卡片、重试成功 |
| 交互4：继续编辑、取消、同图去重、清空组删除旧项 | 完整实现。`F/StudioRevisionDraft.vue:1`；`F/use-revision-actions.ts:20`移除对应材料并保留共享项，`:41`按groupIds替换；`F/editing/EditorDialog.vue:76`清空确认 | `studio-batch-revisions.test.ts:60`重新确认、清空到0、取消及普通附件保留；浏览器继续标注恢复用途 |
| 交互4：关闭保留未确认，已确认持久化、刷新/会话恢复、未知原请求 | 完整实现。`F/editing/EditorDialog.vue:73`关闭不清；`F/studio-composer-draft.ts:31`保存确认快照，`:44`恢复；`F/use-studio.ts:109`原pending请求重试 | 浏览器关闭重开、刷新恢复、跨会话及未知响应刷新后原body/key相等；`studio-batch-revisions.test.ts:47`未确认改动不污染已确认材料 |
| 交互5：发送原图、标注、逐图参考及用途/说明；Codex语义 | 完整实现。`F/use-studio.ts:155`；`B/image_edits.py:44`绑定索引和ID，`:66`明确原图基础、标注只定位、三种用途、参考不额外生成、不得跨图/不得画入成品 | references测试`:52`经HTTP、context_assets register/restore、HANDLER.prepare验证路径和文件字节；`:128`篡改索引/ID拒绝 |
| 交互5：4000字与顶层100附件/100生成图 | 完整实现。`F/editing/state.ts:45`计算含编号完整意见；`F/use-revision-actions.ts:54`上传前计数；`B/schemas.py:36`、`:44`限长 | `studio-editing-state.test.ts:40`完整文本超限；既有附件/引用限制回归包含在527项中 |
| 交互6：历史材料完整展示且冻结，不被改名/移除污染 | 完整实现。`B/image_edit_history.py:5`白名单DTO、`:13`恢复发送时元数据；`B/queries.py:115`接入；`F/studio-revisions.ts:8`按ID绑定；`F/StudioTurns.vue:22`详情入口 | references`:94`改Upload/Picture名字、移除素材后DTO及文件仍相同；PG同一合同测试；浏览器history截图完整用途/意见 |
| 交互6：旧消息、旧草稿、旧未知请求摘要兼容 | 完整实现。`B/schemas.py:37`默认空；`B/service.py:21`摘要剔除空references；`B/image_edit_history.py:10`缺字段默认空；`F/studio-composer-draft.ts:74`可缺referenceImages | references`:114`核对旧fingerprint精确相等，显式空references重放原响应；旧消息组件回归保留 |
| 实施1：源文档与旧协议/文件职责 | 完整实现。`Product-Spec.md:1`、`Design-Brief.md:1`、`DEV-PLAN.md:1`引用同一合同 | 本次直接读取文档；旧摘要实测见上行 |
| 实施2：references协议、inputIndex、类型大小/任务会话权限、安全DTO、无迁移 | 完整实现。`B/schemas.py:10`；`B/image_edits.py:20`；`B/service.py:84`；`B/queries.py:20`、`:36`、`:52`；`B/image_edit_history.py:5` | validation`:60`跨任务/会话/缺失/坏图/文档拒绝；`:138`交换冻结附件身份拒绝；diff无表/迁移 |
| 实施3：正式组件和API，不带预览模拟生成或三维旋转 | 完整实现。`F/OverseasStudio.vue:61`导入正式编辑器、`:118`提交；`F/use-revision-actions.ts:65`既有上传；`F/use-studio.ts:155`既有发送 | 正式目录无preview导入、假发送定时器或新生成API；模拟API仅在浏览器测试fixture中 |
| 实施4：类型/构建/前端/浏览器/后端/PG/审查 | 本业务范围验收通过，基线限制明确保留 | 前端527、浏览器26、独立类型exit0与后端55；Linux/PG127且0skip；全后端9fail完全匹配旧基线，详见下文 |
| 实施5：中文提交、打包部署、正式入口验证、回滚资料 | 后续发布阶段，本业务报告不批准或宣称完成 | `docs/STUDIO-BATCH-ANNOTATION-20261105.md:20`；发布工具另有独立审查，主Agent负责最终镜像及生产证据 |

本范围“部分实现/未实现”：无。引导真实性通过：上传、预览、替换、删除、重试、精细标注、继续编辑、返回核对都有事件实现（`F/editing/ReferencePanel.vue:29`、`EditorDialog.vue:73`、`BatchBoard.vue:94`）。未发现额外产品页面、生成接口或数据库结构造成Spec漂移。

## Stage 2：质量、安全、视觉与测试真实性

- **结构与类型 PASS。** 生产文件拆分为画布/草稿/读取/用途面板/确认事务/历史DTO，最大文件`F/use-studio.ts:1`为236行，`B/queries.py:1`为193行，均小于300行。新增业务代码扫描无显式any，独立vue-tsc退出0。`F/editing/use-board-images.ts:9`的epoch/AbortController与`:27`回收、`F/editing/state.ts:32`引用读取取消、`EditorDialog.vue:97`卸载清理覆盖迟到读取及URL生命周期。
- **安全 PASS（增量范围）。** 扫描eval、innerHTML/dangerouslySetInnerHTML、前端密钥变量、密钥前缀、个人绝对路径、硬编码password及显式any，未发现安全命中。`F/StudioRevisionDetails.vue:8`和`F/editing/RevisionDetails.vue:8`用文本插值显示输入；`B/image_edit_history.py:5`不输出bucket/object_key/inputIndex；`B/service.py:18`权限锁、`:84`任务/会话约束与`B/image_edits.py:51`索引身份绑定保持。未新增字符串SQL拼接或权限绕过。
- **测试真实性 PASS。** 单测中的mock Image/Canvas只用于验证状态/尺寸选择，不能独自证明真实解码；浏览器使用正式Vue组件、真实鼠标操作/图片解码及multipart字节，API被拦截，不冒充真实后端联调（`frontend/tests/studio-batch-annotation.browser.mjs:42`、`:47`、`:64`）。后端测试通过真实HTTP进入校验/冻结/提示词流程，PIL生成真实图片；20MiB使用实际文件长度，非只改metadata（`backend/tests/test_studio_image_references_validation.py:118`）。PG fixture实质替换get_session为pg_factory（`test_studio_image_references_postgres.py:19`），复用真实合同断言，无空壳assert。
- **故障与兼容 PASS。** 第二张上传失败、迟到上传、坏图替换竞态、未知响应原请求、跨任务/跨会话、重复UUID别名、冻结索引篡改、旧幂等均有可达输入和对应失败断言。既有五测试改动主要适配新增导入，旧收图测试按钮断言改为图片footer范围以排除合法新增组按钮（`frontend/tests/studio-delivery-status.test.ts:65`），未删原有收图状态语义；消息材料入口与完整组传递反而新增断言（`studio-message-metadata.test.ts:60`、`studio-process-component.test.ts:104`）。
- **视觉 PASS。** 本次实际打开`http://127.0.0.1:3036/preview-batch-annotation/index.html?baseline=1`并进入旧单张编辑器，再打开无baseline参数的批准批量画布。与正式`output/playwright/studio-batch/{batch-desktop,single-desktop,history,batch-1440,single-390,batch-390}.png`逐张目视对照：白底、蓝色按钮、浅灰画布、橙色定位标注、工具栏密度和左右间隔匹配；新增用途区与批准预览一致。1440与390批量图均已显示六张图片，不再是加载占位；390用途/说明可滚动到达、确认footer可见。数值：`F/editing/EditorDialog.vue:2`宽度、`F/editing/style.css:1`栅格/间距、`:7`移动滚动规则。
- **本轮差异复核。** 旧报告为bf83c958快照；本轮浏览器脚本`:40`加入loadedBoard检查，`:126`、`:129`在1440/390截图前等待六个blob image及非零矩形。其余业务实现本次重新读取审查，不仅凭“未变”声明沿用结论。当前候选业务文件摘要见报告末尾；发布范围修复不会自动获得本报告批准。

## 上轮证据缺口关闭与保留限制

1. 响应式证据已关闭：实际目视1440/390完成态；`output/batch-annotation-preview/production-browser.log:22`、`:24`有对应加载检查，脚本确实在截图前等待。
2. 后端9项失败已归因：`backend-regression.log:463`至`:471`的九个测试标识与原始0713d71隔离导出的`backend-baseline-failures.log:413`至`:421`逐个一致。7项POSIX安全打开限制、1项Windows symlink权限、1项旧路由白名单断言；相关失败文件不在业务diff。**全后端结果仍然是9 failed，不描述为全绿。**
3. PG与Windows受限项补验已关闭：主Agent提供的固定生产依赖镜像、UID10001、只读挂载候选app/tests、隔离Postgres执行日志为`backend-linux-postgres.log:13`的127 passed、0 failed/0 skipped。包括三项新增PG合同及Windows受限8项；本审查核验日志与fixture，未自行再次运行容器。剩余旧route白名单失败不属于本轮范围。
4. 生产安装测试、真实上线及只读正式入口验证尚属发布工作；不能把本地浏览器fixture结果作为生产验收。已有依赖审计high 39、moderate 35、low 5、critical 0为未改依赖基线（`docs/STUDIO-BATCH-VALIDATION-20261105.md:14`），本次未新增依赖，不声称整个项目零漏洞。

## 编译和测试原始输出

审查者本次独立执行，frontend工作目录：

```text
> .\node_modules\.bin\vue-tsc.cmd --noEmit
[stdout/stderr 均为空]
exit_code: 0
```

审查者本次独立执行，backend工作目录：

```text
> .\.venv\Scripts\python.exe -m pytest tests/test_studio_image_edits.py tests/test_studio_image_references.py tests/test_studio_image_references_validation.py -q
.......................................................                  [100%]
55 passed, 2 warnings in 34.17s
exit_code: 0
```

两项原始警告为已安装Starlette的httpx TestClient弃用提示及anyio.abc.BlockingPortal别名弃用提示，不是本轮失败。

读取主Agent原始日志，未冒充本次独立全量执行：

```text
# output/batch-annotation-preview/production-regression.log:850
ℹ tests 527
ℹ suites 0
ℹ pass 527
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 13697.3482

# output/batch-annotation-preview/production-build.log:599
✓ built in 31.27s

# output/batch-annotation-preview/backend-regression.log:472
9 failed, 2726 passed, 430 skipped, 6 warnings in 522.69s (0:08:42)

# output/batch-annotation-preview/backend-baseline-failures.log:422
9 failed, 43 passed, 2 warnings in 5.21s

# output/batch-annotation-preview/backend-linux-postgres.log:13
127 passed, 2 warnings in 105.04s (0:01:45)
TEST_EXIT 0
```

浏览器原始结果为`output/batch-annotation-preview/production-browser.log:1`起26行PASS，`output/playwright/studio-batch/validation.json`记录errors/unexpected均为空；脚本只访问loopback与被拦截API，未触发真实收费生成。

## 业务内容摘要（供最终候选关联）

以下逐文件SHA-256以UTF-8文本CRLF→LF归一计算；聚合摘要为按路径排序的“路径 + 空格 + hash + 换行”UTF-8字符串SHA-256。只批准此清单内容，不批准清单外发布改动。

文件数：33；聚合SHA-256：`9c7f2ddeb4f3a8df9fbda78caab8893f5355bea1896c63d29a61f2171d8c00d9`。

```text
hengxin-smart-image/backend/app/overseas/studio/image_edit_history.py be7745a440100649a9e952707eb2f97fdfdb6277a6ff385149ad84b13e48c8ef
hengxin-smart-image/backend/app/overseas/studio/image_edits.py d044554cfef0e9ae177ddb32eb0039c1de7e843ea89445a2bfe7556e54e44660
hengxin-smart-image/backend/app/overseas/studio/queries.py a9d284bc44fc9cc87b66c3aed8ff16de471ae8d553758893fe3130d745a04da7
hengxin-smart-image/backend/app/overseas/studio/schemas.py b404d72b617b4cab417657fdf7ac29d82312709a09109945af08445957737ca7
hengxin-smart-image/backend/app/overseas/studio/service.py 46e700db5b4fe8c8b00272c64ccd2bcc3a537e0c28d540913ed5d96ee0100ec1
hengxin-smart-image/backend/tests/test_studio_image_references.py bb91e5a2c24f699b9e5573a5632e250d650fc7b205683c17632379fa7f35f357
hengxin-smart-image/backend/tests/test_studio_image_references_postgres.py e9e8175e9e77bb0525a14a437b99decb8fca0774de6052ebf22440cc31ada998
hengxin-smart-image/backend/tests/test_studio_image_references_validation.py e67e3cabc4bd6bf53064f0ce6a29033f9708c4d0d9ffb130fadb19d542fa9ae0
hengxin-smart-image/frontend/src/api/overseas/studio.ts 83dc8e1cce526e03915fafc4e557a4a3f6c24afadf40df0ab06b69995f1f207c
hengxin-smart-image/frontend/src/views/overseas/studio/OverseasStudio.vue 1996d3b7e219e69700920f0ffe45603348615004c901635edf4df72b56393f5d
hengxin-smart-image/frontend/src/views/overseas/studio/StudioRevisionDetails.vue c1e3da0014dd5cb2cc592dd84386389f4b111090d6733ad942a0897c2e551c99
hengxin-smart-image/frontend/src/views/overseas/studio/StudioRevisionDraft.vue 5ebd102fe45bc340b26008ed0e9b45f162eeb45a9fb9b3c9df3147c716617fd1
hengxin-smart-image/frontend/src/views/overseas/studio/StudioTurns.vue 283bcea67f08812dd0871d7115f74fb40a0f120842413e34fe08aa2a51edac77
hengxin-smart-image/frontend/src/views/overseas/studio/editing/BatchBoard.vue 28611d6ae0f6fde66f7c6ac247262bbaf20f67c3f3ac5c4e694325a2a3be2e47
hengxin-smart-image/frontend/src/views/overseas/studio/editing/EditorDialog.vue 61c02d5bf6cb5bb9f274f990642135f8e055758fdc6a044fea7e901fd82322c2
hengxin-smart-image/frontend/src/views/overseas/studio/editing/ReferencePanel.vue e3262f6705cfcb0b3fe2a41f542a877e09a1e9d7e9ae423032b0b92d26976ed3
hengxin-smart-image/frontend/src/views/overseas/studio/editing/RevisionDetails.vue 024eb70024939265dd76b9eecdf5872119c34de44f169ee64b36fdd2b8b56c47
hengxin-smart-image/frontend/src/views/overseas/studio/editing/board-layout.ts a06c8b75154a0234e0da5a3cec0e0221765b7f9b9748d027e43434fe63970339
hengxin-smart-image/frontend/src/views/overseas/studio/editing/state.ts e5f7dc893789fd5454ab32bdc845b274ef5de1b6140a6194e188aacfa3ac74f1
hengxin-smart-image/frontend/src/views/overseas/studio/editing/style.css 05f43025847a1e91632a2d3802f9b8a15d9ac8b53dd0be3218fc7b8862d1a5bb
hengxin-smart-image/frontend/src/views/overseas/studio/editing/use-board-images.ts 70e3dc2f2818bf3e270d65c3204a0b6dfe807953e2dcd2ef78c77887e847fbb3
hengxin-smart-image/frontend/src/views/overseas/studio/studio-composer-draft.ts 8f0056fba7d8e0cad11778482d1e9bff17c3aef57d7c8238cfddcea66d594a7e
hengxin-smart-image/frontend/src/views/overseas/studio/studio-revisions.ts 239a80e3720c0c85b63fb0ceffa8338f25b71c8dc303999cbe1fea77badc65c4
hengxin-smart-image/frontend/src/views/overseas/studio/use-revision-actions.ts ea39712818e680b67ee7b64726f9bf919a44c2784e9ebf484e75e4e761a2276b
hengxin-smart-image/frontend/src/views/overseas/studio/use-studio.ts 1514a10d816fffbe43f02811fb9e1ccdd39f6c517b419622c93d09a24e65790f
hengxin-smart-image/frontend/tests/studio-batch-annotation.browser.mjs bdf61a90079659cb6337761617e747f39c64c5af75bce4393bcd6e36751e5bd4
hengxin-smart-image/frontend/tests/studio-batch-revisions.test.ts d1cb5cb2dcadfb5d99468aa4c2066a1ec8ec250f08e8c96ce01e6ce74d7a7c6f
hengxin-smart-image/frontend/tests/studio-delivery-status.test.ts e03724a36fe666183f91c273a5b610a9bf83284c230f020f4e02daaa521e9c47
hengxin-smart-image/frontend/tests/studio-editing-state.test.ts 2c7dff26a9a4660dbc9b16fed0c42ac09e06a543d50e7fc832b387b5adb07950
hengxin-smart-image/frontend/tests/studio-lifecycle-component.test.ts 837d8a1ef02ed5f55985e3598eaaa6a59fa6ef3814ad19dd0438bb5fd7cc7bfd
hengxin-smart-image/frontend/tests/studio-message-metadata.test.ts 09924e38fb930b8045e2a297f4cc6829fc800da18b1e5eb10f7f52fc5bd25d31
hengxin-smart-image/frontend/tests/studio-outputs.test.ts a7320b15be43cc6c2c6abc1012241fb96f23b05d22c5ceb78fad7e0b33c5fea2
hengxin-smart-image/frontend/tests/studio-process-component.test.ts db4defd78b516c32b08e67bbe15e9603a1609e1817b6d42613803cbccd73a23f
```
