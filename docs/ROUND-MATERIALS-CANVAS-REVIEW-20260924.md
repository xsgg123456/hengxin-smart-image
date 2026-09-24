# 执行材料与标注画布独立审查（第一轮）

- 日期：2026-09-24。
- candidateId：`b1d3f37d113c8e1600d01b4d7819a5da75d3d5c3034ffa2bd64e841b4d0c63a8`。
- 范围：当前 Git 脏改和新增的轮次材料后端、前端组件、公共标注画布及相关测试；源需求为 `Product-Spec.md:745`、`Design-Brief.md:145`、`DEV-PLAN.md:872`。排除未跟踪的 `docs/PERFORMANCE*`，不审既有全项目功能。
- 方法：依照 `.agents/skills/code-review/SKILL.md`，独立阅读代码、运行针对性复现与后端专项测试、检查浏览器测试实现及现有截图/测量结果。本轮未启动浏览器重跑，未修改实现、提交或批准快照。
- 结论：**Stage 1 FAIL（1 项 HIGH）；Stage 2 未执行。** 不得对该 candidate 登记两阶段 PASS。
- 快照：报告收尾前 `harness.py review-status` 返回 currentId 仍为上述编号、`approved: false`。主 Agent 已告知将安排后续修复；修复后的代码必须重新固定候选，本报告不覆盖新版本。

## Stage 1：阻断问题

### HIGH · H1：未执行的 exec 源码被当成“实际生图调用”

需求原文：`Product-Spec.md:749` 要求“实际生图工具提示词”“真实执行证据”，历史不能伪造；无法核实必须如实提示。

位置：

- `hengxin-smart-image/backend/app/execution/material_literals.py:69`：`image_calls` 扫描 token，排除有限控制流关键词后，在 `:87` 直接收集字面量调用。
- `hengxin-smart-image/backend/app/execution/material_history.py:81`：解析 exec 提交源码；`:95`、`:98` 将结果加入真实 `toolCalls`，没有该子调用实际发生的证据。
- `hengxin-smart-image/frontend/src/views/hengxin/components/RoundMaterials.vue:47`：把它呈现为“实际生图提示词 · N 次已记录调用”。

可复现条件：会话记录包含当前轮匹配用户请求及以下 exec function_call：

```javascript
exit(); tools.image_gen__imagegen({prompt: "NEVER_EXECUTED"});
```

`exit()` 是 exec 环境提供的立即终止函数，因此后面的工具调用不会执行。独立执行解析器所得原始输出：

```text
([{'prompt': 'NEVER_EXECUTED'}], False)
```

这不是“调用失败不等于生成成功”，而是**调用从未发生**仍被记录为实际调用。仅追加 `exit` 黑名单不能解决：任意前序表达式异常也会阻止后续调用，例如 `JSON.parse('invalid')`；同一脚本中前一个 await 调用拒绝后，后续调用也不保证发生。

修复要求：实际调用需有可靠执行证据；仅可从源码推断的内容必须标未核实或明确缺失，不计入实际调用。若采用受限语法解析，必须正向验证整个允许程序，拒绝未知前序副作用、提前终止和不能证明执行的后续调用，不能只扫描目标调用字符串。补充提前退出、前序异常、多次同 exec 调用的回归。

## Stage 1：逐项核对

下表路径以 `hengxin-smart-image/` 为前缀；“匹配”表示该条在本候选有对应实现和所列证据，不代替整体 PASS。

| 需求条目 | 结论 | 代码与验证证据 |
| --- | --- | --- |
| 按轮次展开、完整用户意见、操作人及错误 | 匹配 | `frontend/src/views/hengxin/components/RoundHistory.vue:5`、`:22`；模板插值和 pre-wrap，轮次懒挂载 `:28`。浏览器检查记录无展开前材料请求。 |
| 系统交给 CLI 的完整提示词单独显示 | 匹配 | `backend/app/execution/material_capture.py:35`、`codex_runner.py:161` 在 execute 前冻结实际 prompt；`material_history.py:41` 读取对应 request 文件；`frontend/.../RoundMaterials.vue:34` 独立系统区，`:147` 可换行滚动、不截断。浏览器测试比较完整长文本。 |
| 实际生图提示词、分次调用及图片引用 | **部分实现，H1** | `material_history.py:80` 支持直接调用与 exec；`:95` 仅展示安全 `/work/` 图片引用，前端 `RoundMaterials.vue:55` 逐次展示。但 exec 的执行真实性不成立。 |
| 基础成品与版本冻结，不用 current 冒充历史 | 匹配 | `backend/app/execution/materials.py:70` 选择冻结基础版本，`:86` 保存 file/version；`backend/app/modules/tasks/round_materials.py:54` 读 manifest，`:72` 旧记录用 base_version_id，缺失明确说明。后端 `test_first_round_outputs_stay_bound_after_revision` 通过；浏览器 V2 与当前 V3 隔离断言通过。 |
| 原始底图、素材、可选标注图 | 匹配 | `materials.py:62`、`:65`、`:101` 冻结文件 ID；`modules/tasks/round_materials.py:54`、`:79` 映射角色；`material_bindings.py:11`、`:23` 旧材料须引用匹配和文件哈希验证，未核实标签不会冒充实际输入。后端历史输入校验测试通过。 |
| 本轮输出及放大查看 | 匹配 | `modules/tasks/round_materials.py:83` 按 ImageVersion.round_id 查本轮输出；`frontend/.../MaterialPictures.vue:8` 使用 PicturePreview；浏览器已检查放大和刷新后 V3 输出。 |
| 历史缺失不能现行模板重建 | 匹配，但受 H1 限制 | `modules/tasks/round_materials.py:34` 明示未采集；`material_history.py:50`、`:102` 有无原文、超限、不支持格式提示；`material_bindings.py:32` 未核实关联文件标签。旧输入会保留任务冻结关联而非新模板。 |
| 执行中刷新、成功/失败/无结果、加载与重试 | 匹配 | `frontend/.../RoundMaterials.vue:11` 刷新、`:14` 运行提示、`:19` 重试、`:70` 按运行/终态区分无结果；`:93` 序号隔离迟到响应、`:117` 状态变化重新加载。浏览器覆盖 503、刷新、迟到响应；运行/失败分支本轮代码检查，未独立浏览器走每种状态。 |
| 共享权限、文件鉴权、纯文本、安全材料字段 | 匹配于已核对路径 | `backend/app/modules/tasks/router.py:16`、`:47` SharedUser；`modules/tasks/round_materials.py:16` 校验轮次属于任务；`material_history.py:15` 凭据/私有路径脱敏，不取推理或命令输出；`frontend/.../RoundMaterials.vue:42`、`:58` 插值。后端未认证/共享用户/跨任务/删除测试通过；浏览器 `<script>` 仅显示文本。完整 Stage 2 安全扫描未执行。 |
| API/CLI 共用、单画布两工具、最大 1380px | 匹配 | `frontend/src/views/hengxin/api-image-edits/RealRevisionDialog.vue:2`、`components/annotation/CliAnnotationDialog.vue:2` 共用 AnnotationEditor；`AnnotationCanvas.vue:4` 两工具。现有 inline 浏览器证据含两入口。 |
| 首笔/后续笔、增删、意见变化、模式切换画布稳定 | 匹配 | `AnnotationEditor.vue:99` 固定工作区及独立滚动；`use-annotation-canvas.ts:236` 仅图片变化重置，不监听 marks 适配；`AnnotationCanvas.vue:216` 弹性固定 stage。`annotation-workspace.browser.mjs:53` 比较 CTM 和矩形，16 组实测证据通过。 |
| 真实鼠标坐标、落笔/收笔、画笔形状与采样 | 匹配 | `use-annotation-viewport.ts:18` 使用逆 CTM；`use-annotation-canvas.ts:183` 合并采样与真实 pointerup 末点；`annotation-model.ts:95` 原图坐标点链。浏览器检查首点，单测覆盖末点。 |
| 鼠标锚点缩放、加减、适应窗口、真实100% | 匹配 | `use-annotation-viewport.ts:41`、`:60`、`:63`；`AnnotationCanvas.vue:18` 各按钮。16 组浏览器 CTM a=1 与锚点双轴断言通过，200×200 小图单独验证居中。 |
| 重叠新框、编号移动、八方向易命中手柄 | 匹配 | `use-annotation-canvas.ts:129` 仅编号/手柄进入移动调整，其余创建；`AnnotationMarks.vue:50` 20 CSS px 命中区，`:92` 八方向；`annotation-model.ts:67` 调整逻辑。浏览器实拖 NW/E/SE，其他方向由单测/代码检查覆盖。 |
| 固定手柄、空格/中键临时平移、输入空格不拦截 | 匹配 | `AnnotationCanvas.vue:77` 固定手柄；`use-annotation-canvas.ts:106` 中键/空格；`use-annotation-shortcuts.ts:15` 排除输入和按钮。16 组浏览器空格、中键和文本空格断言通过。 |
| 取消手势回滚，不破坏意见 | 匹配 | `AnnotationCanvas.vue:61` pointercancel/lost capture；`use-annotation-canvas.ts:207` 恢复几何/平移；`use-annotation-shortcuts.ts:33` blur/resize；`annotation-model.ts:23` 保留最新意见。浏览器取消新增与 blur 通过，移动/调整取消由代码核对。 |
| 草稿、撤销、编号意见、原尺寸导出、上传及幂等 | 匹配于回归证据 | `AnnotationEditor.vue:44` draft、`:81` 原图导出、`:63` 上传；`use-annotation-canvas.ts:64` 撤销。`output/inline-annotation-20260924/checks.json` 包含两入口原尺寸 PNG 和重复提交相同幂等键，已有草稿/历史版本/上传流程；本轮未修改提交协议。 |
| 800方图/790×1500、1920/1280/窄屏与独立滚动 | 匹配 | `AnnotationEditor.vue:106` 窄屏上下分区；16 组 measurements 全部 pass，包含1920×911、1280×720、600×800、390×844。已实际查看1920长图与390方图截图：头尾按钮可见，意见区可滚动，画布未被文字撑大。 |

## UI 对照与 Spec 漂移

已查看 `output/round-materials-20260924/materials.png`、`narrow.png` 和 `output/playwright/annotation-workspace/790-1500-1920-rect.png`、`800-800-390-pen.png`，与 `Design-Brief.md:147`、`:149` 对照：复用 ElCollapse/蓝色操作/白底圆角，提示词滚动、图文左右布局与窄屏上下分区符合规定。素材卡片 `MaterialPictures.vue:29` 为16px间隔，提示词 `RoundMaterials.vue:150` 最大360px可滚动；画布右栏独立滚动可由代码与截图相互佐证。

新增材料 API、DTO、冻结与只读/显式写入的 backfill 对应 `DEV-PLAN.md:874`，未发现超出这两项授权的新业务功能。代码快照未包含生产写入和收费调用。完整邻居页面实机比较属于 Stage 2，**未执行**。

## 验证原始输出及边界

本 reviewer 使用 bundled Python，PYTHONPATH 指向现有 backend venv；指定新建的仓库内临时目录，执行 `pytest tests/test_round_materials.py -q -p no:cacheprovider --basetemp=.../output/review-round-materials-b1d3-temp`。原始摘要：

```text
...................                                                      [100%]
============================== warnings summary ===============================
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
19 passed, 2 warnings in 2.18s
```

首次使用默认 pytest 临时目录受到本机目录权限限制，`15 passed, 4 warnings, 4 errors`；改用上述独立目录后通过。该环境错误不认定产品缺陷。19项通过与 H1 复现同时成立，说明现有测试没有覆盖这一真实性边界。

主 Agent 验证文档记载前端175通过、正式构建 exit0、后端全套去重1004通过/170跳过；本 reviewer 未重新编译，未拿到该次构建的完整原始终端输出，因此**本报告不作独立编译通过结论**。因 Stage 1 HIGH 已阻断，未继续 Stage 2 的质量、完整安全扫描和邻居页面实机对比。

## 返回主 Agent

H1 修复后重新 `review-prepare`，用新 candidate 从 Stage 1 起独立审查。只有新候选两阶段通过，主 Agent 才可 `review-approve`；本报告不授权任何提交或发布。
