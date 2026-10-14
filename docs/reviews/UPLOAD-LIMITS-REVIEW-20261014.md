# 上传容量与设计人选局部审查

- 日期：2026-10-14；独立 code-reviewer，使用 `.agents/skills/code-review/SKILL.md`。
- 最终 candidateId：`916a6f8d790924cce7a188975791c5f9d14a53add81d8bc200abb8e96dda8e58`。
- 范围：`Product-Spec.md:1129–1133` 与 `DEV-PLAN.md:1393–1396` 对应的本地上传、设计人选、单轮数量限制；相关前后端、测试与海外代理 include。下文代码路径以 `hengxin-smart-image/` 为根。
- Stage 1：**PASS**。Stage 2：**PASS（本次变更范围）**。未发现未解决的本轮 HIGH/MEDIUM 问题。
- 此结论不代表全仓库全量测试全绿、生产500 MB已生效或已部署；后端全量结果见下文。未修改业务代码、未提交、未部署、未写 `.needs-review`；批准凭据由主 Agent 登记。

## 快照与修复记录

初始交接为 `010af50ae09f622b2ba61cd3b6f46a10d67f4f9cd440b4a625a59e3beafd18cd`。主 Agent 排除 Vite 无关生成文件后变为 `6c839d183a98096f080ea1e0fb810a2fb1bbcc841d86d2e962332c68ab32d9aa`。

该版本发现 MEDIUM：恢复101项 pending 后，发送被拒但 pending 永久锁定编辑，提示要求移除而界面无法移除。已由主 Agent 修复为从真实工作台资料/历史图片恢复草稿、释放无效 pending，数量仍超限时禁止发送；缺失引用明确提示。证据：`frontend/src/views/overseas/studio/use-studio.ts:34–45`；`frontend/tests/overseas-studio.test.ts:220` 的真实 sessionStorage 恢复用例。审查者独立执行用例通过。

同时指出旧 mobile 截图被打开的侧栏遮挡，不能证明窄屏可用；现测试通过真实菜单交互关闭遮罩并收起素材，验证实际控件边界、移除/再上传/发送，不修改CSS作弊。证据：`frontend/tests/upload-limits.browser.mjs:88` 起；更新后的 `output/playwright/upload-limits/mobile.png` 已人工查看。测试标题20MiB残留已改为500MB（`frontend/tests/overseas-materials.test.ts:13`）。

上述增量复核后，`harness.py review-status` 返回 currentId 为最终 candidateId；旧结论未直接用于新快照。

## Stage 1：逐条 Spec Compliance

| 条目 | 结果与证据 |
|---|---|
| 两类图需与工作台附件统一500,000,000字节，等于允许 | 完整实现。`backend/app/overseas/upload_limits.py:2`、`frontend/src/api/overseas/upload-limits.ts:1`；资料校验 `materials/parsers.py:35`、工作台校验 `studio/files.py:24`。真实500 MB与+1字节测试 `backend/tests/test_overseas_upload_limits.py:12`；审查者独立28项后端测试通过。 |
| 上传请求、原件读取与文案一致 | 完整实现。两路 router 分别 `backend/app/overseas/materials/router.py:21`、`studio/router.py:62` 传入500 MB上限并读取上限+1；`studio/files.py:75` 读取完整原件并校验大小/校验值；`materials/files.py:54` 重解析读取同上限，`:86` 原件鉴权后流式传送。前端 `api/overseas/materials.ts:25,66`、`studio.ts:44,66` 及 `OverseasMaterialsPanel.vue:4,19`、`studio/OverseasStudio.vue:11` 同步。真实有/无Content-Length multipart边界见 `test_overseas_upload_limits.py:38`。 |
| 保留格式/解析保护，解析失败保存原件并明确下载 | 完整实现。`materials/parsers.py:18–20,48` 保留20MiB输入、2MiB文字、15秒预算；`materials/files.py:28–37` 先存原件再解析；工作台 `studio/files.py:24–71` 保留格式、Office解压及图片像素校验。独立 material-time 浏览器实际呈现“已上传，需下载原件查看”并成功提交。500 MB为文件传输上限，不承诺模型全文上下文。 |
| 负责设计只姓名，移除独立搜索，保留分页/刷新/加载/空态/权限 | 完整实现。`frontend/src/views/overseas/DesignerPicker.vue:3–9` 仅 `person.name`、无搜索输入；`:20–27` 保留分页读取、失败与权限回传。审查者独立 material-time、overseas-tasks-faults 浏览器通过。 |
| 普通附件含图需100个；生成图另100张；重复引用不重复计数 | 完整实现。`frontend/src/api/overseas/upload-limits.ts:2–8` 独立计数；`studio/use-studio.ts:116–138` 去重与预检查；`backend/app/overseas/studio/schemas.py:12–22` 既有100/100与去重限制保持不变。前后端100/101及独立计数用例通过。 |
| 超额批次上传前拒绝，保留草稿，发送前兜底，移除可重试 | 完整实现。`use-studio.ts:16–17,79–86,124–130` 拦截；`OverseasStudio.vue:6,12` 告警和移除。审查者独立浏览器证明101批次上传请求为0、100项成功、移除后再上传、发送100项；恢复草稿见上述修复记录。 |
| UI沿用现有组件与实际可用引导 | 完整实现。DesignerPicker沿用ElSelect/ElPagination/ElAlert，工作台沿用现有告警、附件卡和按钮，无新增样式体系。独立打开图需表单及工作台并查看渲染截图，对照蓝色操作、白底圆角卡片、输入与告警；390×844补证后上传、移除、发送可见可用。 |
| 本地实施，不提交/部署 | 符合。`infra/nginx.overseas-upload.inc:1–8` 仅提供后续海外location合入指令；国内默认multipart上限未改。当前未将其接入实际生产代理，不能宣称线上500MB可用。 |

部分实现：无（本轮本地范围）。未实现：无（本轮本地范围）。Spec 漂移：未见新增无依据页面、API或数据库；容量常量、恢复兜底与代理说明均服务本轮要求。

## Stage 2：Code Quality

- 结构/类型：新增常量集中，数量提示复用纯函数；本轮业务代码文件均不足300行，未新增 `any`。证据：`api/overseas/upload-limits.ts:1–9`、`studio/use-studio.ts:1–142`、`backend/app/modules/files/multipart.py:19–55`。
- 错误处理：超限提前返回，既有未知请求幂等恢复保留；仅超过后端固定schema、确定不可能被接受的pending恢复可编辑。证据：`use-studio.ts:34–45,79–104`，恢复及未知结果原用例均通过。
- 安全扫描：本次diff未发现新增硬编码密钥、eval、危险HTML执行、SQL拼接或公开凭据前缀；上传仍先鉴权，multipart按实际流限制、仅1文件0字段；原件继续授权读取、完整性校验与安全响应头。证据：`materials/router.py:20`、`studio/router.py:61`、`modules/files/multipart.py:35–54`、`studio/files.py:75–122`。未发现需要列出的安全问题。
- 测试真实性：500 MB用例使用真实bytes而非伪造len；流测试真实分段写multipart并覆盖缺少Content-Length；前端浏览器使用真实File及真实事件、仅隔离API，明确不等同500 MB生产端到端压测。证据：`backend/tests/test_overseas_upload_limits.py:12–79`、`frontend/tests/upload-limits.browser.mjs:73–111`。
- 视觉：独立重跑新上传页面与邻居图需表单，查看 `output/playwright/upload-limits/desktop.png`、`mobile.png`、`output/material-time-upload.png`。颜色、按钮、卡片与告警继承原组件；本轮不更改布局。移动截图补证前的问题已关闭。

## 编译与测试原始输出

主 Agent 最终构建日志 `output/upload-limits-build.log:4,769`（已直接读取）：

```text
> vue-tsc --noEmit && vite build
✓ built in 34.03s
```

最终前端全回归日志 `output/upload-limits-frontend-tests.log`：

```text
ℹ tests 360
ℹ suites 0
ℹ pass 360
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8106.4407
```

审查者独立执行后端上传边界、资料、工作台三组：

```text
28 passed, 2 warnings in 9.35s
```

审查者独立执行资料/工作台前端单测（含恢复用例）：

```text
ℹ tests 28
ℹ pass 28
ℹ fail 0
ℹ duration_ms 465.8796
```

审查者独立浏览器原始输出（新候选的upload-limits已再次重跑）：

```text
PASS: 101 blocked before upload; 100 upload/send; remove/retry; 500 MB text; desktop/mobile
PASS: America/Los_Angeles browser renders Beijing list/review time; unparsed PPTX uploads and submits to review
PASS task browser: candidates empty/failure/page; multi-SKU; uncertain retry; detail; assignment 409; list pagination/search/error/empty; narrow ancestor clipping; revoke
PASS material browser faults: size/type/empty; real XHR progress; cancel and route late response; network/malformed; parse retry; safe text; deletion conflict/cancel; unparsed upload can submit; no upload no submit; narrow clipping; revoked content clears state
```

## 全量回归与交付边界

Windows全量日志 `output/upload-limits-backend-all.log` 原始结果：

```text
8 failed, 2152 passed, 314 skipped, 15 warnings in 217.35s (0:03:37)
```

失败在既有 overseas_management_freeze、overseas_pictures、overseas_pictures_protocol；日志显示POSIX安全打开不可用/符号链接环境差异（`backend/app/execution/diagnostics.py:85`），这些实现不在本轮diff。

Linux容器全量日志 `output/upload-limits-backend-linux.log` 原始结果：

```text
8 failed, 2280 passed, 188 skipped, 15 warnings in 256.61s (0:04:16)
```

Linux失败项为既有 `test_phase11a_environment.py` 两项、`test_phase11a_supervisor.py` 六项；错误为隔离进程命令失败（`infra/phase11a_processes.py:14`），这些实现不在本轮diff。已定位首次容器未启用init，pytest作为PID1，触发 `infra/phase11a_supervisor.py:29` 的父进程保护（`parent == 1`）。主 Agent 仅用 `docker run --init` 修正测试宿主方式、原样复跑包含全部8个失败的两个文件，未改代码。审查者读取 `output/upload-limits-linux-supervisor.log` 确认：

```text
...............s...........                                              [100%]
26 passed, 1 skipped in 45.21s
```

因此Linux首次失败已通过环境修正后的针对性复验；不将首次全量结果重写成一次性全绿，也不累加重复测试数。跳过项仍未验证。报告完成时再次运行 `review-status`，currentId仍为上述最终candidateId。

本次没有真实生产代理/500MB网络端到端/并发内存容量验证，没有生产写入、收费模型调用或部署。后续发布须将 `infra/nginx.overseas-upload.inc:3` 的500065536字节请求体限制应用到每层实际海外代理并验证，不能改变国内限制。
