# 临时平移增量独立审查

日期：2026-09-24；使用 code-review skill。

candidateId：`9336f9dc8140c2ad964d3be3c9f0de4a5950739aeb99c263db2954769a2d85a0`。

范围：`hengxin-smart-image/previews/inline-annotation/{app.js,index.html,style.css}` 的临时平移增量。需求依据 Product-Spec.md:3、DEV-PLAN.md:3、docs/INLINE-ANNOTATION-PREVIEW-20260924.md:3。基线 candidate 为 `99e2b485a5111ca09663ecaabfbaff544a52c8edee7602de41149762ac5ae0b0`，基线报告 docs/INLINE-ANNOTATION-PEN-REVIEW-20260924.md。本报告不重新批准全仓或生产业务。

Stage 1：PASS。Stage 2：PASS。未发现增量 HIGH/MEDIUM 问题。

状态更新：报告完成时主 Agent 通知用户已改为“移除第三个平移模式，仅框选/画笔选择并提供始终可用的拖动手柄”。本报告仅记录上述旧 candidate 对当时需求的审查，已被后续预览需求替代；不得据此批准后续实现，且按主 Agent 指令不登记旧快照批准。

## Stage 1：Spec Compliance

以下源码位置均相对上述预览目录。

| 需求 | 结论、源码及验证 |
| --- | --- |
| 保留框选、画笔、平移三个按钮 | 完整实现。index.html:10；app.js:86、126。combined-check.mjs:10–20 真实鼠标连续框选、画笔及临时平移后继续标注。 |
| 空格+左键与中键临时平移 | 完整实现。app.js:75–80、87–104；combined-check.mjs:13–19 分别验证 viewBox 改变、标注 DOM 不变。 |
| 放开后继续原所选工具 | 完整实现。app.js:89–92 使用独立 gesture，不修改 tool；:118–120 结束手势。combined-check.mjs:14–20 验证 active 按钮及下一次真实绘制。 |
| 不因放大切工具 | 完整实现。app.js:84–85、127 只更新视口。combined-check.mjs:10–15 验证放大后的框选连续流程；基线画笔缩放验证见上一报告。 |
| 常驻提示、手形状态 | 完整实现。index.html:11–12、17，style.css:3，app.js:66–70。实际截图显示工具下常驻说明；combined-review-check.mjs:17 验证 grab → grabbing → crosshair。 |
| 意见输入区空格正常输入 | 完整实现。app.js:72、76；combined-check.mjs:21 验证整体意见，combined-review-check.mjs:16 验证每处意见聚焦且鼠标悬停画布时仍输入空格。 |
| 窗口失焦清除临时状态 | 完整实现。app.js:81–83；combined-check.mjs:22 验证失焦清空 spacePan；补测 blur 中断笔迹后无残留。 |
| 指针取消不留半笔及指针归属 | 完整实现。app.js:99–103、115–124；combined-review-check.mjs:6–15 补测取消、丢失捕获、失焦均回滚半笔，外来 pointerId 的 pointerup 不终止当前笔迹。取消事件通过浏览器派发，非真实操作系统强制中断；实际绘制使用真实 mouse 事件。 |
| 仅本地预览、不部署 | 完整实现。index.html:5，app.js:180 仅更新模拟提交文本；review-status 差异仅三个预览文件，未引入远程调用。 |

部分实现：无。未实现：无。Spec 漂移：未发现。新快捷平移已由最新 Spec 明确覆盖旧限制。

## Stage 2：Code Quality

- 代码质量 PASS：app.js 共181行；临时状态、光标更新、取消入口集中在:66–83、115–124。pointerId 归属判断避免其他指针提前结束手势；先清空 gesture 再释放 capture 避免重复回滚。
- 测试真实性 PASS：combined-check.mjs:10–21 使用真实浏览器键鼠，断言视口变化、原标注不变及继续绘制；原脚本:24 仅验证零长度笔迹，不能独自证明取消路径。本次以 combined-review-check.mjs:6–15 补齐该盲区，全部通过。
- 安全 PASS：app.js:70 用 textContent 更新提示，:72–78 过滤可编辑区域和组合输入；对预览目录扫描 eval、innerHTML、SECRET、TOKEN、fetch、XMLHttpRequest 无匹配。本增量无凭据、代码执行或网络能力。
- 视觉 PASS：独立运行浏览器生成并实际查看 combined-desktop.png，与上一轮真实渲染 pen-desktop.png 对比。index.html:11 和 style.css:3 提示栏继承蓝色、12px 字体、5px圆角；三按钮、白色弹窗、橙色标注未发生风格漂移。combined-check.mjs:26 验证390px无横向溢出。采用本预览的上一轮渲染为直接基准，未访问生产页面，不声称完成生产视觉回归。

## 原始验证输出

`node --check hengxin-smart-image/previews/inline-annotation/app.js`：退出码0，无输出。静态预览没有业务构建步骤，本轮未运行正式业务构建。

`node output/annotation-preview-20260924/combined-check.mjs`：退出码0。

```text
PASS: zoomed box -> Space-pan -> box, pen -> middle-pan -> pen, no added/changed marks, selected tool preserved, text space, blur reset, mobile, errors=0
```

`node output/annotation-preview-20260924/combined-review-check.mjs`：退出码0。

```text
PASS: pointercancel/lostcapture/blur rollback, foreign pointer ignored, note space while canvas hovered, grab/grabbing/crosshair transitions; errors=0
```

`harness.py review-status`：退出码0。

```json
{"currentId":"9336f9dc8140c2ad964d3be3c9f0de4a5950739aeb99c263db2954769a2d85a0","reviewedId":"99e2b485a5111ca09663ecaabfbaff544a52c8edee7602de41149762ac5ae0b0","changedFiles":["hengxin-smart-image/previews/inline-annotation/app.js","hengxin-smart-image/previews/inline-annotation/index.html","hengxin-smart-image/previews/inline-annotation/style.css"],"approved":false}
```

送审代码快照一致；审查未修改源码，仅新增本报告和 output 下补充测试。主 Agent 应用 review-approve 登记同一 candidate 的两阶段 PASS；本报告不代替凭据，不写 clean。
