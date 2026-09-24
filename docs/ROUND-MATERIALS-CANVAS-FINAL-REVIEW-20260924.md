# 执行材料与公共标注画布最终独立审查

- 审查日期：2026-09-24；依照 `.agents/skills/code-review/SKILL.md`。
- 最终 candidateId：`705f639df9cd82a877e006e6aa58580f1bf5961d3a2d929ae27c901e1c045b20`。
- 范围：本轮 Git 脏改及新增的 29 个产品代码/测试文件，涵盖 CLI 轮次材料后端与前端、API/CLI 公共标注画布。源文档为 `Product-Spec.md:745`、`Design-Brief.md:145`、`DEV-PLAN.md:872`；排除两份 `docs/PERFORMANCE*`，不重新验收未修改的整个产品。
- 本报告由独立 reviewer 编写；没有修改实现、提交、部署、收费生成或生产回填。测试使用隔离夹具与真实 Vue 组件。
- **最终结论：Stage 1 PASS；Stage 2 PASS。无未关闭 HIGH / MEDIUM。** 最终正式构建、16/16画布矩阵、三视口精确光标probe均独立通过。

## 快照变化及已关闭问题

本次初始候选 `5ba50002b82b8a2315c4a536a5f27517112ec9f69de17f1d8d8d1a04a4abef89` 已修复上一报告的 HIGH H1。reviewer 独立检查 `backend/app/execution/material_literals.py:92` 的整段正向语法校验：只接纳受限字面声明、一次直接 imagegen 调用和已知显示 helper；前序未知调用、提前退出、重名遮蔽、动态表达式、同 exec 多次调用及不合法尾部均不成为实际调用证据。独立 61 项后端测试通过，另外直接复现输出见后文。不同 exec 的多次调用仍通过 `material_history.py:80`、`:98` 逐次保留。

审查发现 MEDIUM M1：初始 `AnnotationCanvas.vue:50` 加入 grabbing class，但没有相应样式，实际按空格仍为 crosshair。主 Agent 修复至 `b188c04fd82953b43c1c3997d8a6eedb02164ba48e05fe084edd875209fdcb9b`，并增加矩阵光标断言。实跑发现 600px 下全局 `frontend/src/assets/styles/core/app.scss:20` 的 `cursor:default!important` 仍盖过基础画布、编号及手柄；这是确定的样式覆盖，不是 keyup 丢失：失败时 class 已恢复 `annotation-stage`，computed cursor 为 `default`。

随后候选 `eecfa114a15255f39898f9eb39daac3a7b9cd7f3606229e7c2ee42b58f1eadb7` 局部覆盖基础光标；reviewer 静态复核继续指出固定抓手按钮的图标也会被宽泛 svg selector 覆盖。最终候选限定主画布 `> svg` 与后代，抓手单独处理继承，见 `frontend/src/views/hengxin/components/annotation/AnnotationCanvas.vue:234`、`:265`、`:271`，编号与调整方向见 `AnnotationMarks.vue:29`、`:58`。主 Agent 修复，reviewer 重新核对 Stage 1 对应项；所有中间候选均未获本报告批准。最终结论只适用于报告顶端编号。

## Stage 1：逐项 Spec Compliance

下表路径省略共同前缀 `hengxin-smart-image/`；文件行号是代码证据，测试/截图是行为证据。不存在以当前版本冒充历史的豁免。

| 需求 | 结论与证据 |
| --- | --- |
| 每轮按需展开、完整用户原文 | 匹配。`frontend/src/views/hengxin/components/RoundHistory.vue:5`、`:22`、`:28`，`TaskDetail.vue:30`；材料浏览器断言折叠时无请求，用户文本插值且 pre-wrap。 |
| 完整系统交给 CLI 的提示词 | 匹配。`backend/app/execution/codex_runner.py:161` 在 execute 前冻结实际 prompt；`material_capture.py:34` 保存，历史 `material_history.py:41` 读原 request；`RoundMaterials.vue:34` 单独展示；浏览器比较完整 220 行原文，不截断。 |
| 可核实的实际工具提示词，独立 exec 多次调用 | 匹配，H1 已关闭。`material_literals.py:92` 整段允许语法、`material_history.py:80`、`:98` 分次归集；`RoundMaterials.vue:47` 分区且说明调用不代表生成成功。61项后端专项与两次独立调用夹具通过。 |
| 基础成品与历史 V 绑定 | 匹配。`backend/app/execution/materials.py:70`、`:86` 冻结实际 file/version，`backend/app/modules/tasks/round_materials.py:54`、`:72` 使用冻结 manifest 或 base_version_id；后端旧轮输出测试及浏览器 V2 不取当前 V3 断言通过。 |
| 原始底图、素材、标注图 | 匹配。`materials.py:62`、`:65`、`:101`；`modules/tasks/round_materials.py:54`、`:79`；旧输入 `material_bindings.py:11`、`:23` 必须引用和内容哈希一致，未核实保留明确标签。 |
| 本轮输出、图片放大 | 匹配。`modules/tasks/round_materials.py:83` 按 ImageVersion.round_id 查询；`frontend/src/views/hengxin/components/MaterialPictures.vue:8` 用既有 PicturePreview。浏览器独立打开大图、刷新后显示本轮 V3。 |
| 历史缺失如实标清，不按现行模板重建 | 匹配。`modules/tasks/round_materials.py:34`、`:68`，`material_history.py:50`、`:102`；历史夹具显示未保存原文，未将当前图或系统 prompt 冒充工具 prompt。 |
| 执行中刷新、成功/失败/未产出、加载与错误重试 | 匹配。`RoundMaterials.vue:11`、`:14`、`:19`、`:70`、`:117`；浏览器 503 重试和刷新通过，运行/终态文案分支经代码核对。失败并不伪造结果。 |
| 轮次切换与迟到响应隔离 | 匹配。`RoundHistory.vue:29` 轮次 key，`RoundMaterials.vue:93` 请求序号及卸载失效；浏览器延迟旧响应后切换，旧内容未覆盖新轮次。 |
| 共享权限、图片鉴权、纯文本，不泄露内部记录 | 匹配。`backend/app/modules/tasks/router.py:16`、`:47` SharedUser；`modules/tasks/round_materials.py:16` 核对任务归属；`material_history.py:15` 脱敏且仅挑选用户边界和 function_call。前端插值，后端共享用户/匿名/跨任务/删除测试与浏览器脚本文本测试通过。 |
| API/CLI 共享单画布、两工具、1380px弹窗 | 匹配。`frontend/src/views/hengxin/api-image-edits/RealRevisionDialog.vue:2`、`components/annotation/CliAnnotationDialog.vue:2` 共享 AnnotationEditor；`AnnotationCanvas.vue:4` 两工具。原入口回归证据见 inline checks。 |
| 首笔/后笔、增删、意见、模式切换保持画布 | 匹配。`AnnotationEditor.vue:99` 固定工作区；`use-annotation-canvas.ts:236` 不按 marks 重新适配。矩阵比较 CTM 和画布矩形各字段，容差0.1 CSS px；已有1920首笔实测差值0。 |
| 右栏独立滚动、窄屏上下分区、控件可达 | 匹配。`AnnotationEditor.vue:100` aside overflow、`:106` 窄屏网格；矩阵验证意见滚动及模式切换无几何变化，1920/1280/600/390截图保留控制区。 |
| 准确落笔收笔、画笔形状及采样 | 匹配。`use-annotation-viewport.ts:18` 逆CTM映射；`use-annotation-canvas.ts:183` 合并采样和 pointerup；`annotation-model.ts:95` 点链。矩阵检查原图坐标首点，单测覆盖不足一原像素末点。 |
| 滚轮锚点、加减、适应、真实100% | 匹配。`use-annotation-viewport.ts:41`、`:60`、`:63`，`AnnotationCanvas.vue:18`；矩阵检验 CTM a=1 和锚点双轴，200×200小图居中且无溢出时不平移。 |
| 重叠新框、编号移动、八方向易命中手柄 | 匹配。`use-annotation-canvas.ts:129` 仅编号/手柄启动移动调整；`AnnotationMarks.vue:50` 20 CSS px命中区域、`:92` 八方向；`annotation-model.ts:67`。矩阵实拖NW/E/SE，纯函数测试核对全部八方向的对边固定及边界。 |
| 固定抓手、空格/中键临时平移、输入空格 | 匹配。`AnnotationCanvas.vue:77`；`use-annotation-canvas.ts:106`；`use-annotation-shortcuts.ts:15` 排除输入/按钮。矩阵实走两种平移与输入空格；最终局部样式覆盖窄屏全局cursor规则。 |
| 光标与动作一致 | 匹配，M1已关闭。`AnnotationCanvas.vue:223`、`:234`、`:239`、`:271`；`AnnotationMarks.vue:29`、`:58`。最终精确probe实测canvas、编号、方向手柄、固定按钮及图标；1440/600/390三个视口默认/空格准备/拖动/恢复四阶段均通过，详见 review-cursors.json。 |
| 取消手势回滚、保留意见 | 匹配。`AnnotationCanvas.vue:61` cancel/lostcapture；`use-annotation-canvas.ts:207` 几何和平移回滚；`use-annotation-shortcuts.ts:33` blur/resize；`annotation-model.ts:23` 保留最新意见。矩阵实测pointercancel/blur，移动/调整分支静态核对。 |
| 草稿、撤销、编号意见、原尺寸导出、上传与幂等 | 匹配。`AnnotationEditor.vue:44`、`:63`、`:81`，`use-annotation-canvas.ts:64`；`output/inline-annotation-20260924/checks.json:3` 记录API/CLI历史版、关闭重开草稿、PNG原尺寸、同key/body重试且仅一次上传；相关提交协议未改变。 |
| 两图片尺寸及四视口验收 | 矩阵覆盖800×800/790×1500 × 1920×911/1280×720/600×800/390×844 × 框选/画笔，共16组；另200×200小图。证据在 `output/playwright/annotation-workspace/`。 |

完整实现见上表；部分实现/未实现：无。Spec漂移：未发现新增超授权业务；材料DTO、查询API、只读默认/显式--write的回填工具均对应 `DEV-PLAN.md:874`。`material_backfill.py:17` 没有生成调用或任务状态重放。

## Stage 2：Code Quality、安全与测试真实性

- 结构与类型：查询/采集/安全解析/历史校验分模块；前端 DTO runtime guard 在 `frontend/src/api/hengxin/round-materials.ts:28`、`:74`，响应ID不一致拒绝。前端新代码未见显式 any；送审源文件不超过300行，最终 `AnnotationCanvas.vue` 为300行，手势/视口/快捷键已拆分。正式 vue-tsc 构建验证类型。
- 错误处理：`material_capture.py:25`、`:44` 捕获观测异常，不将已完成生成变成可重试失败；`:21` 每30秒采集。`RoundMaterials.vue:93` 并发隔离、重试、卸载失效；后端专项覆盖采集异常和节流。
- 安全扫描：本轮相关源码检索 eval、innerHTML、dangerouslySetInnerHTML、VITE敏感变量和密钥前缀未检出新增危险用法。`material_literals.py:92` 只解析不执行；`material_history.py:15` 脱敏、`:35` 文件数/总量/单文本限制；复用 `diagnostics.py:83` _safe_read 拒绝危险链接/路径。业务接口不返回命令、stderr或推理块，SQLAlchemy参数查询不拼接SQL。
- 真实性：`backend/tests/test_material_literals.py:11` 从实际exec形态反例覆盖退出/失败/遮蔽/语法；`test_round_materials.py:42` 使用多exec与时间/用户边界夹具，不将一次程序中的多个源码片段算真实多次调用。API权限测试调用真实路由；文件核对使用实际字节哈希。
- 前端交互测试使用真实浏览器鼠标/键盘及DOM矩阵，并测503、迟到响应、pointercancel/blur、模式切换、输入空格；不是只有纯函数顺畅路径。`annotation-workspace.browser.mjs:53` 检查坐标与CTM，`:79` 检查空格cursor恢复。八方向只有NW/E/SE浏览器实拖，其余通过同一分支的八方向几何单测与代码核对；不宣称八方向全部独立鼠标实测。
- 视觉对比：reviewer 打开邻居API结果详情及新的标注弹窗，实际截图 `output/playwright/annotation-workspace/review-neighbor.png`、`review-canvas.png`；并打开重新生成的材料 `output/round-materials-20260924/materials.png`、`narrow.png`。蓝色主操作、白底圆角、灰底预览、边框及字体沿用邻居。材料图卡16px间隔（`MaterialPictures.vue:26`）、提示词360px滚动（`RoundMaterials.vue:147`）、弹窗24px栏间距与窄屏12px（`AnnotationEditor.vue:99`、`:106`）对照设计规则匹配。

## 独立执行的原始验证输出

后端命令：bundled Python，backend cwd，`PYTHONPATH=.venv/Lib/site-packages;.`，运行 `pytest tests/test_material_literals.py tests/test_round_materials.py -q -p no:cacheprovider --basetemp=.../output/review-final-5ba-temp`。后续变化仅前端光标CSS/样式变量及浏览器断言，不影响该结果。临时目录已清理。

```text
.............................................................            [100%]
61 passed, 2 warnings in 1.96s
```

两条警告为既有 Starlette httpx 和 AnyIO BlockingPortal 弃用；独立 H1 原例/前序JSON失败/正常单次调用依次输出：

```text
([], True)
([], True)
([{'prompt': 'actual'}], False)
py_compile exit=0
```

`git diff --check` exit0，无差异格式错误，只有既有CRLF归一提示。正式构建完整原始日志：`output/review-final-build.log`，命令头：

```text
> hengxin-smart-image-frontend@0.2.5 build
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4469 modules transformed.
✓ built in 28.90s
```

最终构建exit0；存在既有npm配置提示及dingtalk-login静态/动态混用分包提示，完整原始内容保留于日志。

材料浏览器 reviewer 独立运行输出：

```json
{"passed":true,"checks":["按需加载、503可重试、历史基础V2不取当前V3、完整长文本、多次调用与纯文本防注入、原图预览","刷新发布结果、旧记录明确缺失、切换轮次忽略迟到响应、窄面板无溢出、折叠停止材料读取"]}
```

前端TS单测 reviewer 独立重跑在tsx初始化即受本机环境阻断，原始错误：`SystemError [ERR_SYSTEM_ERROR]: uv_os_get_passwd returned ENOMEM`；不能把这次报成单测通过，也不是用例断言失败。主Agent已提供175项通过及后续8专项记录，reviewer已检查本轮关键测试的前提和断言，另以独立正式编译与真实浏览器交互补证。本轮未重复后端1004项全套，使用主Agent记录并独立运行61项核心专项。

曾有一次浏览器probe误在并发构建中读到未就绪dist而超时，未作为产品结论；后续稳定构建后精确复现的窄屏cursor失败已按上述M1修复闭环，未以“环境问题”掩盖。

最终705候选的画布浏览器原始输出（exit0）：

```json
{"passed":true,"cases":16,"checks":"首笔/后笔/意见/滚动/模式切换无跳动；100%、滚轮锚点、空格/中键平移、blur取消、输入空格"}
```

精确光标probe（exit0）在1440/600/390各视口均得到：默认canvas=`crosshair`、badge=`move`、SE handle=`se-resize`、pan/panIcon=`grab`；空格准备canvas/badge/handle均`grab`；拖动均`grabbing`；释放恢复`crosshair`。完整JSON见 `output/playwright/annotation-workspace/review-cursors.json`，可重放probe在 `output/review-cursor.mjs`。最终16组的 `checks.json`、`measurements.json` 与 `small-image.json` 已刷新；小图CTM a=1、居中及禁用平移通过。

收尾 `harness.py review-status` 的 currentId 精确等于最终候选705f639d…，approved=false（reviewer不登记批准）；后端未发生新改动。主Agent依据本报告登记，不可将旧5ba/b188/eec结论冒用为最终批准。

## 交付边界

当前仅本地代码验收。生产API尚无worker私有运行目录权限；新轮次落库和发布后codex身份受控历史回填见验证文档，`material_backfill.py:20` 默认只读，`:40` 仅--write写入。本报告不声称线上材料已显示，也不授权部署或生产回填。不向.needs-review写clean；主Agent应在最终两阶段PASS且review-status匹配时，用本报告路径登记review-approve。
