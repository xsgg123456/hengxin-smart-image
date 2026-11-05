# 参考图自定义用途增量审查

- 日期：2026-11-05；独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`b69796817b9d38516148ccda622bcfba162e6a4e07373f8b45d2d303b7dd50e9`。
- **Stage 1 PASS；Stage 2 PASS**。未发现本轮范围内 HIGH、MEDIUM 问题。
- 范围：`hengxin-smart-image/frontend/preview-batch-annotation/` 中 README.md、state.ts、ReferencePanel.vue、RevisionDetails.vue、App.vue。下文 `P/` 指该完整目录，`O/` 指 `output/batch-annotation-preview/`。
- 需求依据：`P/README.md:3`、`:9`、`:10`、`:11`。这是独立预览增量；正式 Product-Spec、Design-Brief、生产组件未变。其余预览基线采用 `docs/BATCH-ANNOTATION-PREVIEW-REVIEW-20261105.md` 的已审范围，并检查本轮回归证据，不扩大为真实 AI、上传或生产发布验收。
- 审查开始及结束的 `review-status` 均返回上述 currentId；相对已批准 `ed3e2858f2f6c7672905a87834c6faa2177900566b972bb323419642a374b4b5` 仅四个代码文件变化，与交接一致。README 不属于代码快照。审查期间未发现受控代码变化；未修改实现、提交或登记批准。

## Stage 1：Spec Compliance — PASS

| 需求及验收 | 结论、代码位置和证据 |
|---|---|
| 保留本产品实拍、成品效果参考，增加自定义用途 | 完整实现。`P/ReferencePanel.vue:15` 保留原两个 value 并增加 custom；独立重跑 `O/custom-purpose-check.cjs:25` 起实际打开下拉，三项均存在。 |
| 自定义用途自由输入，仅选中时出现 | 完整实现。`P/ReferencePanel.vue:16`—`:18` 条件 textarea，2000字符上限、两行显示、独立标签和 aria-label；实测可输入两行中文，切回预设输入框消失。 |
| 自定义不能为空、不能只有空白；仍需独立参考说明 | 完整实现。`P/state.ts:28`—`:29` 分别校验用途/说明和自定义 trim；`P/EditorDialog.vue:63` 在核对前阻断。浏览器分别提交空串和三个空格，均显示错误；既有35项回归包含缺用途/说明阻断。 |
| 切换预设保留自定义草稿，但按当前用途输出 | 完整实现。`P/ReferencePanel.vue:15` 只改 kind，`:18` 绑定原对象 customPurpose；`P/state.ts:20` 按 kind 选择标签，预设不泄漏隐藏草稿。实测自定义→实拍→核对只显示实拍，返回→自定义仍保留两行原内容。 |
| 批量与单图共用、关闭重开不丢 | 完整实现。`P/state.ts:15`、`:19` 以图片ID存草稿；`P/EditorDialog.vue:52` 共用 draftFor，`:59` 关闭不清理；实测批量填写后关闭并从同图单张入口进入，值完全一致。既有回归验证跨图隔离及关闭保留。 |
| 核对、带回、发送与历史材料保留用途 | 完整实现。`P/state.ts:61` 复制 reference 含新字段；`P/RevisionDetails.vue:8` 渲染当前用途，保持多行换行及长词折行；`P/App.vue:23`、`:39` 支持待发材料查看，`:76`、`:80` 将用途加入发送快照和文本，`:82` 存本轮材料。实测核对、发送预览、用户消息、历史材料均包含完整两行内容。 |
| 历史冻结，不随后续用途编辑变化 | 完整实现。`P/state.ts:61`、`P/App.vue:76` 按引用项复制，customPurpose为字符串；`:82` 保存该次发送独立数组。发送后再次编辑用途，历史仍显示原值且不包含新值；35项回归同时验证图片及说明冻结。 |
| 兼容既有无 customPurpose 的草稿 | 完整实现。`P/state.ts:8` 属性可选，`:20` 默认空字符串，`:29` 可选链；product/effect不要求该属性。新建参考默认空值见`:48`。此兼容结论为类型检查和代码证据，不声称存在跨刷新持久化。 |
| 引导真实性、原流程及范围边界 | 完整实现。`P/ReferencePanel.vue:6`、`:18` 的用途提示对应真实输入和校验，无新死引导。`P/README.md:3` 限定独立预览；四个代码变更仅用途数据及展示，无新API、页面、表或持久化，未发现 Spec 漂移。 |
| 桌面与390窄屏可用 | 完整实现。审看 `O/custom-purpose.png`、`O/custom-purpose-390.png`，新增用途与说明分别显示，标签、输入框、按钮未遮挡；390下滚动可达并实际填写。`P/ReferencePanel.vue:18` 继承既有 ElInput，`P/RevisionDetails.vue:8` 明确换行。 |

部分实现：无。未实现：无。旧范围 README 第1、2、4、5项未被本轮改变；独立重跑原35项真实浏览器回归，覆盖批量目标筛选、框选/平移/缩放、单图精细编辑、参考图替换删除失败重试、回填不自动发、历史材料、主输入校验、取消及窄屏。旧审查保留的刷新重置与异步过期读取等结论仍为原报告证据，不冒称本轮新增验证。

## Stage 2：Code Quality — PASS

| 项目 | 结论、代码位置和证据 |
|---|---|
| 类型、规模与职责 | PASS。`P/state.ts:8` 使用明确联合类型和可选字符串；`:20` 统一用途格式化，两处展示共用，无重复分支。ReferencePanel只负责输入，RevisionDetails只读，App负责发送。修改代码文件分别69、34、17、87行，均小于300。独立 vue-tsc exit 0，扫描新增范围无 any。 |
| 校验与快照 | PASS。`P/state.ts:24`—`:30` 验证后，`P/EditorDialog.vue:66` 才生成核对快照；`P/state.ts:61`、`P/App.vue:76` 的复制覆盖新字符串，无嵌套共享可变自定义对象。失败仍保留草稿。 |
| 安全扫描 | PASS（本预览范围）。扫描 .vue/.ts 中 eval、innerHTML、v-html、dangerouslySetInnerHTML、密钥前缀及用户绝对路径均无匹配。`P/RevisionDetails.vue:8` 使用文本插值；发送文本由 `P/App.vue:80` 拼接后交给 `P/PreviewTurns.vue:6` 文本插值，不作HTML解析。 |
| 注入实测 | PASS。reviewer在原真实交互脚本中将用途改为 `<img src=x onerror=window.__reviewXss=1>` 与 script 标签两行文本，重走核对、发送、历史及草稿修改；文字完整显示，执行标志未设置，目标DOM未生成script。结果 `O/reviewer-custom-purpose-injection-validation.json:2`，17条通过、errors为空。未修改应用代码或原测试文件。 |
| 测试真实性 | PASS。`O/custom-purpose-check.cjs:19` 起真实鼠标标注、文件上传、下拉切换、表单输入和点击确认；断言DOM文字及 inputValue，覆盖空值/空白失败路径和历史编辑隔离。独立重跑16条全部通过。原35项脚本真实打开baseline与新页面，结果35条通过，无pageerror及业务请求。 |
| 视觉对比 | PASS。reviewer实际浏览器打开同1920视口baseline和新单张，实测均1380×926；审看稳定基准 `O/reviewer-baseline-stable.png` 与 `O/single-empty.png`，共用外壳、工具栏、画布和底部按钮视觉一致，右侧参考卡沿用原输入风格。新增自定义字段桌面/390截图未出现越界；`P/ReferencePanel.vue:18` 与`:21` 相同控件，`P/RevisionDetails.vue:8` 用pre-wrap避免多行合并。 |

证据局限：原 `browser-check.cjs` 的 baseline截图可能截到开场过渡动画，本轮发现后关闭动画重新截图为 `reviewer-baseline-stable.png`，据稳定截图作视觉判断；不是产品缺陷。构建与514项生产回归读取主Agent日志，不冒称reviewer重跑；生产回归也不替代新增预览交互测试。

## 编译与测试原始输出

reviewer独立执行：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-batch-annotation/tsconfig.json
[stdout/stderr为空]
exit_code: 0
```

`P/build.log:3`、`:5`、`:72` 原始输出（主Agent构建）：

```text
vite v7.1.7 building for production...
✓ 4614 modules transformed.
✓ built in 24.19s
```

`P/regression.log` 末尾原始输出（主Agent既有生产回归）：

```text
ℹ tests 514
ℹ suites 0
ℹ pass 514
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 13622.0303
```

reviewer独立浏览器关键原始输出：

```text
PASS 空自定义用途阻止提交
PASS 空白自定义用途阻止提交
PASS 切回预设按当前用途提交
PASS 切换选项保留自由输入草稿
PASS 单张与批量共享自定义用途
PASS 确认材料显示完整自定义用途
PASS 发送预览保留自定义用途
PASS 发送文本保留自由用途
PASS 发送材料保留自由用途
PASS 历史用途不受草稿后续修改影响
PASS 窄屏可以填写自定义用途
PASS 无浏览器运行错误
PASS 自定义用途HTML作为文本显示且未执行
Baseline/new boxes { width: 1380, height: 926 } { width: 1380, height: 926 }
COMPLETE 35 checks
```

最终 `review-status` currentId仍为本报告candidateId，approved为false。由主Agent使用本报告为同一快照登记两阶段PASS；本报告不批准其他候选，不向 `.needs-review` 写clean。
