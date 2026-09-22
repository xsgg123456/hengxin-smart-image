# 单图历史版本本地预览独立审查

- 日期：2026-09-22；Stage 1 **PASS**，Stage 2 **PASS**。无未解决 HIGH / MEDIUM。
- 最终 candidateId：`cd78df9897e17a8c33744efdf2c2beb8ee3c2de4eb5c8681b07b40c0a124977b`。独立读取 review-state 与运行 review-status，候选和当前编号一致。
- 初次送审编号 `449f9b955d924790c2cad3c20bc4f83142ecb27842b01c798744471f01370222` 已失效：审查中修复初始版本生成时间并增加回归；自动组件声明及本地依赖缓存产生的临时快照差异已清除。已复核最终差异，不以原编号批准。
- 本轮范围：frontend 的 DemoVersionDialog.vue、preview-state.ts、TaskDetail.vue、DemoRevisionDialog.vue、DemoRecords.vue、tests/api-image-version-preview.test.ts。其余此前已审内容承接 docs/API-IMAGE-OPTIMIZATION-PREVIEW-REVIEW.md；独立 review-status 确认相对此前批准快照仅以上六文件变化。未重新批准无关生产后端或历史部署。
- 依据：docs/API-IMAGE-VERSION-PREVIEW.md:3–10 全部条目及 Product-Spec.md:4、Design-Brief.md:4、DEV-PLAN.md:4。本报告不授权提交或上线；主 Agent 负责对同一快照执行 review-approve，不写 clean。

路径缩写：A/ = hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/；T/ = hengxin-smart-image/frontend/tests/；E/ = output/api-optimization-preview/。

## Stage 1：Spec Compliance

| 条目 | 判定、源码位置与验证 |
|---|---|
| 每次成功保存独立版本，含编号、时间、操作人、说明、标注图和基础版本 | 完整实现。A/preview-state.ts:10 定义字段，:170–176 成功追加结果及元数据，:123 初始版本；T/api-image-version-preview.test.ts:5 验证初次成功时间，:15 验证追加说明/标注/基础版。E/version-v4.png 实际显示 V4、基于 V1、时间、操作人及标注。 |
| 当前指向历史一版，恢复不删历史，再修改编号递增 | 完整实现。A/preview-state.ts:126–134 复制选定版本为当前；:171 使用历史最大编号加一，:106 冻结当前基础结果。T/api-image-version-preview.test.ts:15 验证 V3→V1→V4，旧三版序列化内容不变、相邻图片不变。E/versions.cjs:10–15 实际恢复、再修改并得到四版。 |
| 修改失败不新增、不覆盖历史 | 完整实现。A/preview-state.ts:163–165 失败分支只更新执行状态；T/api-image-version-preview.test.ts:42 覆盖三次重试耗尽、旧结果对象与完整历史保持。 |
| 卡片当前 Vn、历史入口 | 完整实现。A/TaskDetail.vue:22、:69；E/versions.cjs:11 验证恢复后卡片当前 V1，:13–14 验证历史计数由三变四。 |
| 左版本列表、右选中与当前并排对比、完整详情 | 完整实现。A/DemoVersionDialog.vue:4–24、:48 按编号倒序，:91、:104 分栏；E/version-1440.png 与 version-1280.png 均可见三版、当前标签、双图及信息区。 |
| 下载该版、确认恢复、不重新生成、不删除、当前不可重复恢复 | 完整实现。A/DemoVersionDialog.vue:64–84 使用选中图片下载，确认文案明确后果，:34 禁止重复恢复；A/preview-state.ts:132 同版本无操作。E/versions.cjs:8–10 真实下载、取消及确认；独立逐字节验证 version-v1.jpg 等于 sample-1.jpg。 |
| 初始单版提示，无删除版本入口 | 完整实现。A/DemoVersionDialog.vue:15、:30 单版/无结果提示；:31–35 只有关闭、下载、设为当前。E/versions.cjs:15 实际打开原图2单版并断言当前按钮禁用。整任务删除沿用 A/DemoRecords.vue:57–60。 |
| 处理中、失败待重试、打包期间禁止恢复 | 完整实现。A/preview-state.ts:129 拒绝未成功修改；A/TaskDetail.vue:31、:71–73 传递打包锁；A/DemoVersionDialog.vue:54、:73、:81 点击前及确认后均检查锁。T/api-image-version-preview.test.ts:26、:54 覆盖处理中/失败拒绝；E/versions.cjs:13 覆盖处理中的真实按钮。打包锁与失败提示未单独浏览器点击，结论依据源码锁链及状态测试，不宣称此两项浏览器覆盖。 |
| 修改弹框显示基础 Vn，成功新增设为当前 | 完整实现。A/DemoRevisionDialog.vue:4 文案及当前图；A/preview-state.ts:105–106、:171–175 执行；E/versions.cjs:12、:14 验证以恢复后 V1 提交并生成 V4。 |
| ZIP 使用每张选定当前版 | 完整实现。A/preview-download.ts:9–15 读取 item.result，:21 防过期；A/TaskDetail.vue:11 明示。审查者独立解包 version-restored.zip，确认 11 条目 CRC 有效，每条内容与该槽当前示例图逐字节一致；首图为恢复后的 sample-1。 |
| 至少三版示例入口 | 完整实现。A/DemoRecords.vue:5、:51；A/preview-state.ts:136–148。E/versions.cjs:4 由实际入口创建三版场景，无手工注入业务状态。 |
| 本地 demo/mock，沿用前端、不改生产 | 完整实现。A/records.vue:5 通过 src/api/api-image-edits.ts:4 的模式开关选择 Demo/Real；A/preview-state.ts:194 仅本地模式定时推进。E/version-evidence.json:15–16 无页面错误和 /api/v1 请求；最终快照差异仅六个预览实现/测试文件。 |
| 类型、全套测试、构建、浏览器、1280/1440、独立审查 | 完整实现，原始日志及独立检查见下方。E/versions.cjs:7 实测两宽度弹框完整落在视口内；审查者亲自打开对应截图复核。 |

部分实现：无。未实现：无。Spec 漂移：无；三版模拟图片及原有演示场景属于已批准本地预览，不代表真实生成效果或持久化能力。

审查中已解决问题：初始 V1 的“生成时间”原先使用任务受理时间（A/preview-state.ts:123），与展示语义不符，定为 MEDIUM。主 Agent 在 :176 初次成功分支写入 stamp()，增加 T/api-image-version-preview.test.ts:5 回归；复核通过。该修复是最终快照的一部分。

## Stage 2：Code Quality

| 检查 | 结论及证据 |
|---|---|
| 类型、文件大小、职责 | 通过。A/preview-state.ts:10–19 显式类型；新增版本对话框 117 行、状态文件 195 行，所有本轮实现少于 300 行。状态与弹框、原有 ZIP 分离；限定文件扫描无 any。 |
| 异步与错误处理 | 通过。A/DemoVersionDialog.vue:53–59 上下文令牌，:73 防重复提交，:80–82 确认后检查关闭、上下文、打包/修改锁及当前版变化，:85 显示错误。A/preview-state.ts:128–132 拒绝无效/未完成状态和不存在版本。 |
| 测试真实性 | 通过。T/api-image-version-preview.test.ts:15 从三版实际状态恢复、发起修改和 tick 推进；断言历史内容、相邻结果与基础版，不仅断言新增数量。:42 使用真实重试状态机走失败路径。E/versions.cjs 使用页面按钮、输入和上传实际 JPG 验证交互；ZIP 的真实下载另独立校验，未用最小测试字节冒充真实图片。初始时间回归只断言不等于受理时间，精确写入逻辑另由 :176 源码核验。 |
| 安全扫描 | 通过。对本轮五个实现文件扫描 eval、innerHTML、dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN、硬编码密钥及用户目录，无命中。A/DemoVersionDialog.vue:23 Vue 文本插值展示说明，:68 下载由本地状态机产生的图片；A/DemoRevisionDialog.vue:41–51 保留标注格式/大小/解码校验。 |
| 实际视觉对比 | 通过。审查者亲自打开 E/baseline.png、final-revision.png、version-1440.png、version-1280.png、version-v4.png：沿用蓝色主按钮、白底圆角弹框、灰色说明、共享图片查看器，双宽度无内容/操作按钮裁切。A/DemoVersionDialog.vue:91 为 190px 左栏/24px 间距，:104 双图/16px 间距，:106 图高320px，:98 8px圆角及 :101 主题变量与实际渲染相符。没有额外设计稿数值可对照。 |

## 编译与验证原始输出

审查者独立运行 vue-tsc --noEmit：退出码 0，stdout/stderr 为空。主 Agent 最新全套日志 E/version-tests.log 末尾：

```text
ℹ tests 149
ℹ suites 0
ℹ pass 149
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 20653.3126
```

E/version-build.log 原始末行（主 Agent 最终生产构建）：

```text
✓ built in 41.97s
```

独立读取浏览器真实下载文件、解包并逐字节比对原始输出：

```text
VERSION_V1_DOWNLOAD_AND_RESTORED_ZIP_11_REAL_BYTES_PASS
```

审查者尝试独立 tsx 复跑时，运行器在进入测试前因环境错误退出；不记为产品测试失败或独立测试通过。原始关键输出：

```text
SystemError [ERR_SYSTEM_ERROR]: A system error occurred: uv_os_get_passwd returned ENOMEM (not enough memory)
syscall: 'uv_os_get_passwd'
Node.js v24.19.0
```

测试通过依据为主 Agent 保存的最新 149 项原始日志。此前并行运行原有 demo-state 定时器用例偶发失败，最终串行全套通过；本报告不声称已解决全套并行稳定性。浏览器由主 Agent 执行，审查者复核脚本、JSON、截图和实际下载产物，不将其表述为本人点击。
