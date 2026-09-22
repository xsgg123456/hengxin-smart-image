# API 优化本地预览独立审查

- 日期：2026-09-22。
- candidateId：`7e287ec9df2bbfdc2bf0422014db6ea91d5a49bbf9b1789f1e41b6ea10b781de`。
- 结论：Stage 1 **PASS**；Stage 2 **PASS**。本轮范围内无 HIGH / MEDIUM 问题。
- 范围：前端 api-image-edits 下 DemoCreate.vue、DemoRecords.vue、DemoRevisionDialog.vue、TaskDetail.vue、PreviewNotice.vue、preview-state.ts、preview-download.ts，以及 tests/api-image-preview.test.ts、tests/api-image-preview-download.test.ts。未审查或批准本轮以外的后端、Real 页面、历史部署改动。
- 依据：docs/API-IMAGE-OPTIMIZATION-PREVIEW.md:7–11 的五条验收与 :22 本地边界；Product-Spec.md:3、DEV-PLAN.md:3、Design-Brief.md:3 本轮条目。按 code-review skill 两阶段执行。
- 快照：独立执行 review-status，currentId 与送审 candidateId 相同；审查期间未修改实现。旧批准快照不代表本轮通过，主 Agent 应对本编号执行 review-approve。本报告不写 clean，不授权部署或提交。

下方源码路径缩写：`A/` = `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/`，`T/` = `hengxin-smart-image/frontend/tests/`；证据目录 `E/` = `output/api-optimization-preview/`。

## Stage 1 — Spec Compliance：PASS

| 需求条目 | 判定及代码证据 | 验证证据 |
|---|---|---|
| 1：沿用框架、表格、卡片、抽屉、弹框与图片查看器 | 完整实现。A/DemoRecords.vue:2、:9、:25；A/TaskDetail.vue:2、:7、:18；A/DemoRevisionDialog.vue:2、:28。沿用现有 Art / Element Plus 与主题变量。 | 独立查看 E/baseline.png 与 final-records-1440.png、final-records-1280.png、final-detail.png、final-revision.png：侧栏、页头、页签、蓝色按钮、白卡片和边界一致。 |
| 1：52px 完整缩略图、紧凑行、操作者 | 完整实现。A/DemoRecords.vue:9、:10、:13、:46、:66；共享 components/PicturePreview.vue:3 使用 contain。 | E/browser-evidence.json:3 三个缩略图均为 52×52；最终两种宽度截图操作人不换行、图片完整，列表无横向裁切。 |
| 2：重复场景与 demo/mock 隔离 | 完整实现。A/preview-state.ts:59、:65 创建 11 张场景，初始化幂等；A/DemoRecords.vue:5 场景入口；src/api/api-image-edits.ts:4 与 A/create.vue:5、records.vue:5 隔离入口；A/PreviewNotice.vue:2 明示模拟边界。 | T/api-image-preview.test.ts:76 初始化/重复 ID；E/browser-evidence.json:18 无生产业务请求。 |
| 2：10+1 分批，首调之外 3 次、1/2/4 秒退避，保留成功项及手动恢复 | 完整实现。A/preview-state.ts:114–153 冻结当前批次，:123–129 退避耗尽，:86–93 仅重新排入失败项。 | T/api-image-preview.test.ts:12、:26、:45 覆盖边界时刻与成功结果对象保持；E/failure-evidence.json:9–22 十张处理中、第十一张等待。 |
| 2：静默更新保留输入、弹框、滚动 | 完整实现。A/preview-state.ts:142、:155 原地推进；A/DemoRecords.vue:9 无全表 loading，:32 弹框独立状态；A/DemoRevisionDialog.vue:36 仅开关时清理草稿。 | E/exercise.cjs:31–32 等待后输入不变、无 mask；E/edge-evidence.json:11–14 scrollTop 400→400；交互弹框未被 tick 关闭。 |
| 3：三列网格、批次、重试、操作人及记录 | 完整实现。A/TaskDetail.vue:5、:16、:22、:27、:81；A/preview-state.ts:26、:118、:126、:138。 | final-detail.png 实际三列；failure-evidence.json 真实交互走到修改失败与恢复；处理日志包含操作者。 |
| 3：成功 ZIP，顺序编号、打包状态、失败重试及禁止过期下载 | 完整实现。A/TaskDetail.vue:5–6、:51、:64–67；A/preview-download.ts:5–21、:24–37；共享 download-helpers.ts:55 按输入顺序编号。 | T/api-image-preview-download.test.ts:12、:37、:56 覆盖 CRC、顺序、最新结果、失败及打包途中变化；E/failure-evidence.json:6 失败恢复。审查者独立解包 results.zip、revised-results.zip，11 个条目 CRC 全部有效、01–11 顺序正确；逐字节比对真实示例 JPG，修改后首图等于 sample-2，其余 10 张不变。 |
| 4：当前生成结果 + 可选单张标注图 + 文字，至少一种，不内置修改业务提示词 | 完整实现。A/DemoRevisionDialog.vue:4、:7–16、:22；A/preview-state.ts:95–102 保存当前结果 base、原始文字和标注图。填入示例按钮的示例提示词属于显式示例填充，不会附加到修改输入。 | E/exercise.cjs:24–35 图文提交；E/edges.cjs:5–7 纯图提交、空态禁用与双击仅产生一条记录。 |
| 4：标注预览、移除、格式大小与真实图片校验 | 完整实现。A/DemoRevisionDialog.vue:10–13、:37–54 校验扩展名/MIME、10 MiB、文件头、decode，并隔离关闭后的异步读取结果。 | E/exercise.cjs:23–26 无效 PNG 被拒，真实 JPG 可读；代码逐条核对格式和大小拒绝分支，未将未实测的超限文件称为浏览器已测。 |
| 4：单图修改重试、成功替换、失败保旧图、不影响原图与相邻图、记录操作人 | 完整实现。A/preview-state.ts:100–109、:120–138；原图保存在 item.source，仅 item.result 更新；A/TaskDetail.vue:21–22 可继续重试。 | T/api-image-preview.test.ts:54 校验旧结果、相邻图对象及操作者；E/failures.cjs:12–16 修改耗尽仍有旧图、恢复成功；独立 ZIP 字节验证确认最新结果。 |
| 5：空态、加载、错误、筛选、重复提交、关闭重开、双宽度、ZIP 与编译验证 | 完整实现。A/DemoRecords.vue:8–9、:35、:52；A/DemoCreate.vue:26、:48–54；A/DemoRevisionDialog.vue:36、:56–61；A/TaskDetail.vue:64–67。 | E/browser-evidence.json、failure-evidence.json、edge-evidence.json 均 passed=true；empty.png、最终稳定截图及下方编译结果。关闭重开清空草稿和图文至少一项行为对应实际入口。 |

部分实现：无。未实现：无（仅就本次本地模拟范围）。Spec 漂移：无；暂停/示例控制均明确标注演示，未新增正式业务接口或生产能力。模拟预览并不证明真实收费生成、后端并发、持久化或上线可用。

## Stage 2 — Code Quality：PASS

| 检查 | 结论与证据 |
|---|---|
| 类型、结构、文件大小 | 通过。送审实现均小于 300 行（最长 A/preview-state.ts:156）；状态、ZIP、修改弹框分离；A/preview-state.ts:6–16 明确领域类型，A/preview-download.ts:18、:24 明确 Promise 返回类型；扫描范围无 any。 |
| 错误和并发保护 | 通过。A/DemoRevisionDialog.vue:35–54 防止关闭后读取回写，:57 防重复提交；A/preview-state.ts:98 防正在修改时再次请求；A/preview-download.ts:4、:21、:25、:35 防重复打包、拒绝过期结果并释放锁。 |
| 测试真实性 | 通过。T/api-image-preview.test.ts:26 精确验证毫秒时刻和第十一项等待，:57 校验结果身份，前提与实际状态机一致。ZIP 单测的最小 JPEG 字节用于容器及 CRC 测试，未用它宣称真实图片解码成功；另以浏览器下载 ZIP 和真实 JPG 字节比对覆盖实际文件。故障交互由 E/failures.cjs:12–24 覆盖，非只测纯函数顺畅路径。 |
| 安全扫描 | 通过。对全部送审实现扫描 eval、innerHTML、dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN、硬编码密钥、用户目录路径均无命中。A/preview-download.ts:11–13 限制示例/同源 blob；A/DemoRevisionDialog.vue:41–51 校验标注文件。未出现生产凭据或业务请求。 |
| 实际视觉对比 | 通过。审查者亲自打开邻居任务中心基准截图及四张最终稳定截图；共享页头/侧栏/页签、主题色、按钮形状和卡片成立，1280/1440 记录布局未裁切；A/TaskDetail.vue:81 为三列，A/DemoRevisionDialog.vue:65、:74 两列及窄屏堆叠。旧 records.png、动画中 detail.png / revision-1280.png 不作为最终样式证据。 |

## 编译与执行证据

独立运行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`，退出码 **0**，原始 stdout/stderr 为空。

主 Agent 全套测试日志 E/tests.log:147–154 原始输出：

```text
ℹ tests 146
ℹ suites 0
ℹ pass 146
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3484.1256
```

构建日志原始末行 E/build-demo.log:381、E/build-production.log:381：

```text
✓ built in 29.20s
✓ built in 35.67s
```

审查者独立 ZIP 验证原始输出：

```text
ZIP_REAL_BYTES_ORDER_PASS 11
ZIP_REVISED_REAL_BYTES_ORDER_PASS 11
```

浏览器证据由主 Agent 执行，审查者读取实际脚本、JSON、截图和下载产物复核；未将其表述为审查者亲自点击执行。报告只批准上述送审范围和同一快照的两阶段结果。

