# 海外工作台草稿与批量移除独立审查 · 2026-10-22

## 快照、范围与结论

- 初始 candidateId：`fd6ba59810d9d08a4cfa514a68b5b018df6953a10375ae89fd6ea7c7e3109964`。
- 本报告实际审查 candidateId：`249b94d670600046ed418d7e660081014545474e8cfc9ffd3b43b89f11c86b49`。
- 审查期间只发生浏览器测试截图等待修正：增加确认框可见/动画完成等待、12项勾选DOM断言，以及截图 `animations: 'disabled'`。已复核 `frontend/tests/studio-draft-materials.browser.mjs:68`、`:69`、`:70`、`:86`、`:89`、`:91` 及重新生成的实际截图。运行实现未在这次快照切换中改变。最终只读 `review-status` 返回上述 currentId。
- 范围：`hengxin-smart-image/frontend/src/views/overseas/studio/` 下 `use-studio.ts`、`studio-composer-draft.ts`、`StudioMaterials.vue`、`OverseasStudio.vue`、`studio.css`，以及两个 `studio-draft-materials` 测试文件；只读追踪现有API、后端素材可见性和标注模块。
- 源要求：`Product-Spec.md:1270`、`DEV-PLAN.md:1512`、`Design-Brief.md:1`、`Product-Spec-CHANGELOG.md:843`，已读取原文。
- **Stage 1：PASS。Stage 2：PASS，附1项LOW非阻断提示问题。** 未发现本轮核心功能缺失、安全问题或新增范围漂移。
- 主Agent已决定修复该LOW；本报告仅适用于上述快照，不批准之后的代码。修复后必须重新固定快照并审查。reviewer未执行review-approve、未写clean、未提交、未部署。

以下前端路径简写相对于 `hengxin-smart-image/frontend/`。

## Stage 1 · Spec Compliance

| Spec逐项要求 | 结论与实现证据 | 验证证据 |
| --- | --- | --- |
| 同一浏览器保存文字、Skill、已上传/引用附件 | 完整实现。`src/views/overseas/studio/studio-composer-draft.ts:23`、`:31`、`:78` 同步深监听序列化；`use-studio.ts:14` 接入。存的是服务端文件元数据和身份，不是未完成的本地File。 | 专项单测第1项，真实组件浏览器上传后reload并断言文字、Skill、两项附件恢复。 |
| 按用户、任务、对话隔离；刷新/离开后返回 | 完整实现。`studio-composer-draft.ts:13` JSON数组键避免分隔符碰撞；`:41` 按服务端当前会话激活，`:45` 切换时清字段；`use-studio.ts:67` 只在授权读取成功后恢复。实际task页面以任务id作组件key，`src/views/overseas/OverseasTasksPage.vue:23`。 | 专项单测第1、2项通过真正Vue组件卸载/重建验证返回，并验证其他用户、其他任务、其他会话不读取旧稿。浏览器reload通过。 |
| 已确认图片修改关系与标记恢复 | 完整实现。`studio-composer-draft.ts:35` 保存base、annotation、text、marks；`:54` 起从授权结果匹配图片，并重建revision和标注draft。没有把普通附件误恢复成图片修改。 | 专项单测第5项验证重建后标记数量，以及真实send入参imageEdits内pictureId/annotationId/text。对照 `StudioAnnotationDialog.vue:19`、`:21` 的编辑副本/确认机制。 |
| 隐藏及重复上传附件恢复 | 完整实现。`studio-composer-draft.ts:50` 用isAsset验证原身份；不强制附件仍存在于去重后的materials列表。`src/api/overseas/studio.ts:20` 验证id对应的固定相对URL。 | 单测第1项明确构造“上传返回身份不在可见列表”的情况，并保留隐藏附件；浏览器批量移除后reload仍有待发引用且send入参保留原id。后端 `backend/app/overseas/studio/material_list.py:20` 去重/隐藏与原附件身份独立。 |
| 存储不可用明确提示，未发送内容可继续编辑 | 完整实现。`studio-composer-draft.ts:40` 捕获写入异常，`:70` 捕获读取/结构异常；`OverseasStudio.vue:13` 显示ElAlert；locked不依赖notice。 | 单测第6项：存储抛错时文字仍可编辑，出现无法保存提示；损坏JSON/外部URL不恢复附件。低优先级提示清理问题另见Stage 2。 |
| 发送成功清稿，明确失败保留 | 完整实现。`use-studio.ts:110` 成功时clear；`:118` 失败分支不清草稿；`studio-composer-draft.ts:73` 清当前及指定原会话键。 | 单测第3项验证409失败跨重建保留，成功后localStorage为空；浏览器发送失败reload保留、成功reload清空。 |
| 响应未知保留原请求、不自动发送 | 完整实现。`use-studio.ts:18`、`:43` 复用sessionStorage pending；`:119` 仅确定性4xx清pending；`:127` 固定body、key和原会话；`:130` retry使用原pending。新增localStorage恢复只赋值，不调用发送API。 | 单测第3项503跨重建保持锁定，重试body/key完全相等；第4项新会话响应丢失、读取已切换会话后重试清理原会话草稿。浏览器部分覆盖明确失败，未知响应由组件状态测试覆盖。 |
| 开始新对话成功清旧稿且不串入新会话 | 完整实现。`use-studio.ts:129` 记录原会话，`:110` 清旧稿后`:111` 激活新会话。 | 单测第3、4项，浏览器新会话后reload空白。 |
| 复用勾选/全选；蓝色引用下方红色移除；单项入口保留 | 完整实现。`StudioMaterials.vue:5`、`:8`、`:12`、`:14`；`studio.css:67` 列布局、gap 8px、第二按钮margin-left为0。 | 浏览器全选4项、取消0请求、部分失败后1项仍选中；实际打开桌面截图与用户原截图比较。 |
| 未选、只读、忙、已完成禁用并显示加载 | 完整实现。`StudioMaterials.vue:14` 使用disabled/chosen/removing；`use-studio.ts:21`、`:23` 汇总状态，`:158` 再校验，`:162` 在第一请求前同步加锁。 | 单测第6、7、8项覆盖只读、运行中重复调用及已完成；浏览器0项禁用及完成态禁用。 |
| 批量一次确认，显示数量和保留边界 | 完整实现。`OverseasStudio.vue:72` 起一次ElMessageBox，包含N、历史、已发送文件、输入区已引用附件；确认后才调用removeMaterials。 | 浏览器取消后removed数组为空；修正后confirmation.png实际显示“这4项”及三项保留说明。 |
| 仅列表隐藏，历史、已发送、输入区引用保留 | 完整实现。`use-studio.ts:169` 仅接收返回的Studio数据，不改attachments/revisions。复用DELETE接口 `src/api/overseas/studio.ts:66`；后端 `backend/app/overseas/studio/material_list.py:48` 只写MaterialVisibility.hidden，不删除Upload/Material。 | 单测和浏览器都验证已引用附件仍在；历史文件保留还经现有后端源码审查，本轮未做真实数据库写入。 |
| 成功从列表消失，部分失败明确成功/未完成数，失败勾选可重试，刷新不复活 | 完整实现。`use-studio.ts:159` 去重/筛选当前id，`:165` 顺序请求，`:170` 单项失败继续，`:172` 返回实际计数；`OverseasStudio.vue:77` 两类反馈；`StudioMaterials.vue:28` 仅过滤已不在列表的选择。 | 单测第7项中间失败仍处理后项、随后重试；浏览器3成功1失败反馈及b保持勾选，重试后刷新列表空。后端commit在 `material_list.py:63`，持久性沿用已有实现；没有把模拟API当成生产持久化证明。 |
| 权限丢失停止后续批量请求 | 完整实现。`use-studio.ts:41` 401/403/404置denied并通知上层，`:165` 每次请求前检查。 | 单测第8项403只调用1次，余项不发送。权限丢失会清服务端视图，恢复权限后需要重新载入；没有冒充权限仍有效继续操作。 |
| 桌面窄屏视觉与可见性 | 匹配本轮设计。`StudioMaterials.vue:14` 复用Element Plus，`studio.css:67` 全宽纵向危险次操作；没有新增自定义主题。 | 查看desktop-selected、confirmation、mobile-empty、mobile-selected及用户原截图。1366×900桌面与390×844展开窄屏底部两按钮可见，浏览器insidePanel检查所有裁切祖先。窄屏沿用覆盖式素材栏，需“收起”回到完整输入区。 |
| 仅本地实施，不提交不部署 | 匹配。浏览器 `tests/studio-draft-materials.browser.mjs:7` 限定loopback，`:33` 起拦截外部/业务请求；运行实现未加后端接口。 | 本审查仅只读代码/测试/截图和写报告，无Git提交与生产写入。 |

部分实现：无本轮阻断项。未实现：无。死引导：本轮新增确认、失败重试及存储提示均有相应执行路径。Spec漂移：无新增页面/API/表；图片修改关系持久化属于Spec明确的已确认引用保存。

## Stage 2 · Code Quality

### LOW · 修正内容后旧恢复提示仍保留

- 位置：`src/views/overseas/studio/studio-composer-draft.ts:39`、`:69`、`:70`、`:73`。
- 失效Skill恢复后notice设为“草稿中的 Skill 已不可用，请重新选择后发送。”；用户选择有效Skill并成功写入后，save只清除与storageWarning完全相等的提示，旧恢复提示不清。clear同样不清notice，因此成功发送后仍显示旧警告。损坏草稿提示也有相同残留路径。
- 独立执行真实useComposerDraft（Vue effectScope/ref、内存Storage）得到原始输出：

```text
before: 草稿中的 Skill 已不可用，请重新选择后发送。
after selecting valid skill: 草稿中的 Skill 已不可用，请重新选择后发送。
after successful-send clear: 草稿中的 Skill 已不可用，请重新选择后发送。
```

- 影响为提示真实性，不阻止有效稿保存和发送、不丢内容。建议区分存储错误、恢复错误和Skill有效性，修正状态或清稿时清相应提示，并增加回归。主Agent已决定修复；后续快照需独立复核。

### 其余质量结果

- 职责/类型：PASS。持久化独立helper，API协议不变；5个运行文件均不超过300行，use-studio约232行。新增代码未使用any；批量循环有finally释放锁，失败分支不会越过权限锁。依据 `studio-composer-draft.ts:7`、`:23`，`use-studio.ts:158`。
- 测试真实性：PASS。`tests/studio-draft-materials.test.ts:23` 使用真实Vue renderer挂载useStudio，`:48` 等用例卸载/重建而非只测序列化函数；浏览器实际导入正式组件并拦截API，`:61` reload、`:66`取消、`:73`失败仍选中、`:78`失败发送、`:85`窄屏均有行为断言。图片标注用例覆盖组合状态及发送协议，但未完整浏览器绘画；不据此声称做了端到端标注导出验证。
- 截图真实性：最初confirmation未包含弹窗、mobile-selected视觉尚未勾选，已指出并由主Agent修正。本次报告以最终等待/禁动画的真实截图为证据，不使用旧截图结论覆盖新版本。
- 安全：PASS（限定本轮差异）。对5个运行文件扫描eval、innerHTML/dangerouslySetInnerHTML、密钥标识和any未命中。`studio-composer-draft.ts:49` 拒绝错误版本/结构；`:50` 复用固定相对URL校验；图片来自已授权服务端数据。localStorage内容未被当作权限凭据、未引入HTML拼接/动态执行。后端 `queries.py:33` 仍检查attachment归属当前任务。
- 视觉：PASS。实际对照用户原侧栏截图与新桌面图，标题、素材卡、蓝色主按钮、字号和边距沿用；新增红色plain按钮处于蓝按钮下方8px。最终窄屏全选蓝色勾选和N=12一致，底部无截断。依据 `studio.css:67` 和 `tests/studio-draft-materials.browser.mjs:89`。
- 已有额外回归失败：主Agent报告旧 `studio-native.browser.mjs:65` Markdown图片数量预期0实际1，HEAD覆盖基线同点失败。此用例未计入PASS。验证过程记录在 `docs/STUDIO-DRAFT-MATERIALS-VALIDATION-20261022.md:35`；当前变更不涉及Markdown渲染。

## 编译、测试原始输出与边界

审查者独立运行专项单测，退出0，摘要原文：

```text
ℹ tests 8
ℹ suites 0
ℹ pass 8
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 351.8679
```

审查者独立运行专项浏览器，退出0，原文：

```text
PASS: upload/reload, draft text/Skill/attachments, hidden material recovery, selection/cancel/all/partial failure/retry, send failure/success, new conversation, readonly, desktop/mobile clipping checks
```

审查者独立运行 `pnpm typecheck`，退出0，原始输出（无类型诊断）：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.46 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

已读取主Agent保存的全量日志 `output/studio-draft-materials-unit.log`，末尾原文：

```text
ℹ tests 340
ℹ suites 0
ℹ pass 340
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8012.7154
```

已读取 `output/studio-draft-materials-build.log`，命令及末尾关键原始输出：

```text
> hengxin-smart-image-frontend@0.2.46 build:overseas D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build --config vite.overseas.config.ts --mode demo

🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for demo...
transforming...
✓ 4683 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 31.55s
```

这是本地前端与隔离协议验证，不是生产、真实数据库、真实模型调用验收；本轮后端未变更。以上两阶段结论仅覆盖列明的Spec增量与candidateId。
