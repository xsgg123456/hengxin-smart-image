# API 换套图交互预览独立审查

审查日期：2026-09-22。使用 `.agents/skills/code-review/SKILL.md`。仅审查本轮本地 Demo；生产中转站、模型调用、数据库、Worker、部署不属于本次验收。

## 快照与范围

- 初始 candidateId：`6387674732f3d6575b35250a92f4244537d69b3d5e3769dd9f1117fcbacc96ae`。
- 最终 candidateId：`96ab34ed68b6fa09a158e9a3b8d6a84b920ad2e2d3bf3ab51ce148a0ca78ab43`。**Stage 1 PASS；Stage 2 PASS**，仅适用于本轮本地交互预览。
- 初审发现上传解码与路由切换竞态，主 Agent 修改 create.vue、ImageSequence.vue、preview-state.ts 后重新固定快照。Reviewer 已逐行复核这三处差异并独立重跑边界浏览器验证；旧快照没有被批准。
- 源依据：`docs/API-IMAGE-PREVIEW-PLAN.md:3`、`Product-Spec.md:7`、`Design-Brief.md:3`、`DEV-PLAN.md:714`。
- 实现范围：`hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/` 实际为 **6 个文件**，以及路由、WorkspaceStatus、示例 SVG、专项测试；审查包含未跟踪文件。
- 下表路径缩写 `F/` 代表 `hengxin-smart-image/frontend/`，`A/` 代表 `F/src/views/hengxin/api-image-edits/`。

## Stage 1：Spec Compliance

| 验收条目 | 实现及证据 |
|---|---|
| 独立 Demo 菜单，生产路由不开放 | 完整实现。`F/src/router/modules/index.ts:18` 在 MODE=demo 时注册新建和记录子路由；`A/preview-state.ts:30` 再限制提交环境。 |
| 继承 Art、Element Plus、既有布局及图片查看器 | 完整实现。`A/create.vue:2`、`:5`、`:7`、`:41`，`A/records.vue:8`，`A/TaskDetail.vue:2`、`:15`。视觉证据见下节。 |
| 名称、同一份提示词及至少两张图片 | 完整实现。`A/create.vue:14`、`:15`、`:46`；`A/preview-state.ts:31` 防御校验、`:34` 冻结同一任务输入。解码跨路由边界已修复复测。 |
| 前 N 原图、末张共用素材；移动、拖动、指定素材、移除 | 完整实现。`A/ImageSequence.vue:10`、`:11`、`:14`、`:15`，move/drop 更新同一个有序数组；`A/preview-state.ts:34` 取末张素材。浏览器实测按钮排序/设素材/删除，拖动路径经事件及数组实现核查。 |
| 本地读取、格式/大小/数量和解码验证 | 完整实现。`A/ImageSequence.vue:29` 起校验 MIME、10 MiB、21 张上限，再创建本地 URL 并解码；`:38` 全局阻塞、`:43` 清理共享草稿。正常损坏 JPG 和跨路由延迟解码均已实测拦截。 |
| 五张示例原图与一张素材 | 完整实现。`A/preview-state.ts:15`、`:19`；浏览器确认 6 张卡片。SVG 为应用内置素材，用户上传限制与内置示例类型区别明确。 |
| 独立内存历史，刷新重置，不写 CLI 数据 | 完整实现。`A/preview-state.ts:11` 模块内 reactive 状态，无持久化/CLI store 引用；`:77` 模块级定时器不依赖详情组件生命周期。`A/PreviewNotice.vue:2` 明确边界。 |
| 串行、自动重试三次、1/2/4 秒指数退避 | 完整实现。`A/preview-state.ts:51` 至 `:75` 每 tick 只推进最早任务的一项，首次之外最多三次重试；`F/tests/api-image-preview.test.ts:9`、`:21` 验证串行和精确 nextAt。 |
| 成功、重试成功、耗尽部分失败，失败后继续 | 完整实现。`A/create.vue:31` 三场景；`A/preview-state.ts:62` 决定模拟失败位置，`:69` 标记失败后继续。浏览器经历三次重试用尽、4/5 成功。 |
| 只重试失败项，成功项保留，按原图顺序输出 | 完整实现。`A/preview-state.ts:43` 至 `:49`；`A/TaskDetail.vue:12` 按 items 顺序；专项测试 `:36` 起断言既有成功结果对象保持一致，浏览器恢复至 5/5。 |
| 任务记录、查询、空态、进度、抽屉、关闭后继续 | 完整实现。`A/records.vue:7`、`:8`、`:29`、`:43`；`A/TaskDetail.vue:7`、`:16`、`:23`。内存列表同步读取无需网络加载，运行态可见。浏览器覆盖查询空态、关闭再打开和恢复演示。 |
| 单张看图、下载示例文件 | 完整实现。`A/TaskDetail.vue:15`、`:18`、`:51`；浏览器实际接收下载事件及中文文件名，打开查看器并操作方向键/Esc。 |
| 删除记录二次确认 | 完整实现。`A/records.vue:45` 至 `:48`；运行任务禁删位于 `:12`。浏览器验证取消保留、确认移除。 |
| 示例提示真实、不联网生成、不保存凭据 | 完整实现。`A/PreviewNotice.vue:2`、`A/TaskDetail.vue:4`、`:18`；结果明确是固定示例文件（`A/preview-state.ts:72`）。源码无请求/凭据存储，主流程网络日志无 `/api/v1` 请求。 |
| 不包含 ZIP、归档、CLI 返工、正式 API 或部署 | 范围匹配。记录和详情仅提供约定操作；新增文件与 diff 没有后端/CLI 修改。暂停按钮明确叫“暂停演示”（`A/TaskDetail.vue:5`），属于本地演示控制。 |

### 初始快照问题及处理

**MEDIUM，上传解码阻塞可被路由切换绕过。** 计划要求“至少两张有效图片……才可提交”（`docs/API-IMAGE-PREVIEW-PLAN.md:11`）。旧 `ImageSequence.vue:29` 的 pending 和旧 `create.vue:43` 的 uploading 属于组件，图片占位却位于全局草稿；离开再返回创建页会重置阻塞，解码未完成的文件可以进入冻结任务。

独立 Chromium 故障注入仅延迟 Image 的失败回调，不修改应用状态或按钮逻辑。`output/api-preview-review-boundary.cjs` 输出：

```text
After route change, undecoded invalid image can submit: true
Task frozen inputs after invalid decode failure: 7
```

这证明旧快照不应批准；不是生产需求扩展。主 Agent 已改为全局 pendingUploads（`A/preview-state.ts:13`）、提交层防御（`:31`），并在卸载后向共享草稿清理失败项（`A/ImageSequence.vue:43`）。创建页在 `:26` 显示读取中提示，`:46` 不因重建组件放行。Reviewer 在新快照独立执行修订后的回归脚本，退出 0，原始输出：

```text
After route change, undecoded invalid image can submit: false
Task frozen inputs after invalid decode failure: 6
Route-change decode guard PASS
```

最终范围内无部分实现或未实现项；没有将 Spec 中明确后置的生产能力计为缺陷。

## Stage 2：Code Quality — PASS

Stage 1 修复复核通过后，复核质量、安全扫描及测试证据：

- 文件职责拆为创建、图片序列、状态机、提示、历史和详情，单文件 6–78 行，无 any；状态机使用联合类型（`A/preview-state.ts:4`）。
- 专项测试使用实际状态机和可达状态，精确断言时间及结果对象保留，未把全部失败伪装成功；交互脚本包含上传失败、重试耗尽、恢复、下载和删除取消，不只测顺畅路径。旧测试遗漏的跨路由解码已通过独立故障注入揭示。
- 扫描新增目录、路由及 SVG：未发现硬编码密钥、eval、innerHTML、注入执行、VITE 凭据或网络生成调用。SVG 仅包含渐变与 path（`F/public/samples/api-material.svg:1`）。
- 视觉：已实际读取邻居 `output/api-preview-baseline.png` 与新建 1440/1280、部分失败和结果图。均保留 Art 侧栏/页头/页签、蓝色操作、白卡浅灰底；共享 `.hx-create-grid` 的 300px 摘要列、22px 列间距及 23px 卡片内距来自 `F/src/views/hengxin/prototype.css:7`、`:8`。输入素材橙色标签为角色区分（`A/ImageSequence.vue:61`）。1280 自动化断言无横向溢出。基准图处于模板加载态，只用于框架布局对比，不能证明旧业务已加载完成。
- LOW，短期预览的资源管理局限：成功创建的 blob URL 在移除图片、填示例或删除记录后未主动回收（`A/ImageSequence.vue:15`、`:35`，`A/preview-state.ts:18`，`A/records.vue:48`）。当前页长期反复上传可能累积内存；刷新会释放。不影响本轮短时交互验收，正式实现应按草稿和历史引用释放，不能直接删除所有任务仍引用的 URL。
- 无额外生产功能漂移；未将真实模型质量、真实 API 重试分类或服务端权限计入本次 Demo 验收。

## 编译和测试原始输出

Reviewer 在初始和最终快照均独立执行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：stdout/stderr 为空，两次 exit_code=0。

主 Agent 提供的日志已实际读取。`output/api-preview-tests.log`：

```text
ℹ tests 128
ℹ suites 0
ℹ pass 128
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 14712.5455
```

`output/api-preview-build-demo.log`、`output/api-preview-build-production.log`：

```text
✓ built in 37.16s
✓ built in 40.86s
```

`output/api-preview-browser.json`：`passed=true`、`errors=[]`、`apiRequests=[]`。审查已检查 `output/api-preview-check.cjs` 断言本体，不能把其中未覆盖的边界宣称通过。最终主流程回归输出：

```text
Browser interaction checks PASS; no business API requests or page errors.
```

记录页原截图捕捉到关闭动画中的抽屉，测试补充精确等待后已重拍；Reviewer 已打开最终 `output/api-preview-records.png`，确认显示独立记录列表、统计、筛选及操作列，与 `A/records.vue:5` 至 `:13` 一致。

最终快照批准由主 Agent 在两个阶段均 PASS 后使用 review-approve 登记，本报告不写 `.needs-review`。
