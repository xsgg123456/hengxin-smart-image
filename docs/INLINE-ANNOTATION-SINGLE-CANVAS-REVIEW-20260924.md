# 单画布拖动手柄增量独立审查

日期：2026-09-24。使用 code-review skill。

candidateId：`e4154cf9fb2164d045000cd7eed515fbdd7f8e749ad25d6fba0611ac25b1d70e`。

范围：hengxin-smart-image/previews/inline-annotation/{app.js,index.html,style.css}，仅相对旧 candidate 9336f9dc8140c2ad964d3be3c9f0de4a5950739aeb99c263db2954769a2d85a0 的单画布手柄增量；不重新批准全仓或生产业务。需求依据 Product-Spec.md:3、DEV-PLAN.md:3、docs/INLINE-ANNOTATION-PREVIEW-20260924.md:3。旧报告仅作为已审基线。

Stage 1：PASS。Stage 2：PASS。未发现本增量 HIGH/MEDIUM 问题。

## Stage 1：Spec Compliance

下列源码路径均相对 hengxin-smart-image/previews/inline-annotation/。

| 当前需求 | 结论与证据 |
| --- | --- |
| 一个画布、一张图，仅框选/画笔两个工具 | 完整实现。index.html:10、13，仅两个工具按钮与一个编辑 SVG；single-canvas-check.mjs:5 验证旧 pan 按钮不存在、工具数量2、画布数量1。 |
| 固定拖动手柄，无快捷键完成框选→移动→框选 | 完整实现。index.html:14、style.css:4、app.js:90–94、115–117。single-canvas-check.mjs:10–12 使用真实鼠标拖动，断言视口变化、标注不变、框选仍选中并继续框选。 |
| 画笔→移动→画笔，保持缩放、标注、工具 | 完整实现。app.js:90–94、117 未修改 zoom/tool/boxes；single-canvas-check.mjs:13–14 实际拖动后继续第二笔，标注DOM不变。 |
| 100%不能移动时提示先放大 | 完整实现。app.js:70–73、91，single-canvas-check.mjs:5、19 验证100%禁用。 |
| 平移边界与辅助方向键 | 完整实现。app.js:95–98、117，single-canvas-check.mjs:17–18 验证方向键位移及超大拖动不越界。 |
| 失焦、取消后不残留拖动 | 完整实现。app.js:84–86、128–137；独立新增 single-canvas-review-check.mjs:5–9 在真实手柄拖动中派发 blur/pointercancel，后续移动不再改变视口、不增加标注、不改工具、清除拖动样式。取消事件为浏览器派发，未模拟操作系统强制中断。 |
| 草稿及合成预览 | 完整实现。app.js:166–167、178–188；补测 single-canvas-review-check.mjs:10 验证取消拖动后画笔可用、关闭重开标注及意见保留；single-canvas-check.mjs:16 实际打开合成并解码图像。 |
| 常驻引导、原辅助快捷键保留 | 完整实现。index.html:11、14、18，app.js:70–73、78–83、102–105；页面主引导为手柄拖动，实际两条主流程未按键。 |
| 仅预览、无生产修改 | 完整实现。index.html:5，app.js:193 仅模拟文本；快照差异仅三个预览文件。 |

部分实现：无。未实现：无。Spec 漂移：无，本次手柄与两个工具均有明确需求。UI 一致性：实际查看本次独立运行生成的 single-canvas.png；手柄位于画布右上角、工具仅两项，未增加第二画布。

## Stage 2：Code Quality

- 质量 PASS：app.js 194行、index.html 32行、style.css 6行；app.js:66–74 集中更新手势UI，:90–99 独立手柄处理，:128–137 复用原有结束/取消处理。无新增重复状态源。
- 测试真实性 PASS：single-canvas-check.mjs:7–14 实际浏览器鼠标拖动，断言不是仅检查按钮存在；本次补齐手柄失焦/取消及草稿回归。没有把主Agent的通过声明作为独立执行证据。
- 安全 PASS：对三个预览文件执行 eval、innerHTML、SECRET、TOKEN、fetch、XMLHttpRequest 扫描无匹配。app.js:70、73 用 textContent；新增交互无远程调用或动态代码执行。
- 视觉 PASS：实际查看独立生成 single-canvas.png，与此前真实渲染 desktop.png 对比，白色弹窗、蓝色按钮、字号间距、橙色标注体系保持；style.css:4–6 仅增加手柄及窄屏样式。combined-desktop.png 已被新实现重跑覆盖，不把它误当旧版基准。single-canvas-check.mjs:20 验证390px无横向溢出且仍能拖动。视觉对比采用上一轮保存渲染；未访问生产邻居页面，不声称生产视觉回归。

## 原始验证输出

`node --check hengxin-smart-image/previews/inline-annotation/app.js`：退出码0，无输出。静态预览无独立编译步骤；未执行正式业务构建。

`node output/annotation-preview-20260924/single-canvas-check.mjs`：退出码0。

```text
PASS: one canvas/two tools/no pan mode; no-keyboard handle drag with box and pen selected; continue marking; unchanged marks/zoom/tool; export; boundaries; keyboard handle; mobile; errors=0
```

`node output/annotation-preview-20260924/single-canvas-review-check.mjs`：退出码0。

```text
PASS: handle blur/pointercancel ends drag without marks or tool change; subsequent pen and close/reopen draft preserved
```

`harness.py review-status`（使用已安装 Python 的绝对路径）：退出码0。

```json
{"currentId":"e4154cf9fb2164d045000cd7eed515fbdd7f8e749ad25d6fba0611ac25b1d70e","reviewedId":"99e2b485a5111ca09663ecaabfbaff544a52c8edee7602de41149762ac5ae0b0","changedFiles":["hengxin-smart-image/previews/inline-annotation/app.js","hengxin-smart-image/previews/inline-annotation/index.html","hengxin-smart-image/previews/inline-annotation/style.css"],"approved":false}
```

送审快照与实查一致；审查未修改源码，仅添加补测与报告。主Agent须用 review-approve 登记同一 candidate 两阶段 PASS，不写 clean。
