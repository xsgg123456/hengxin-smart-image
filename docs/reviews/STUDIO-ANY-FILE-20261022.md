# 海外工作台任意格式附件独立审查

- 最终 candidateId：`1f1a7ee0768ade40924a66e9b92ac6557a06a5ea55e4914d65c8df209aa37b01`。
- 初始 candidateId：`010dd18c327f31a6ac9bccbd3b3b8ac32fe52b8988cd1eaf5c39cc3178ffe070`，不以此旧编号批准最终版本。
- 结论：**Stage 1 PASS；Stage 2 PASS**。未发现本轮遗留 HIGH / MEDIUM 问题。
- 范围：Product-Spec.md:1 的 2026-10-22 章节、docs/STUDIO-ANY-FILE-20261022.md:5 的四步验收，以及本轮九个实现/测试文件。既有功能仅检查受影响链路；不是对全部产品历史条目的重新验收。未部署、未提交、未调用真实模型。
- 使用 `.agents/skills/code-review/SKILL.md`。审查人只读取代码、运行隔离检查、写本报告；批准凭据由主 Agent 登记。
- 下文 `backend/`、`frontend/` 均相对于仓库内 `hengxin-smart-image/` 子目录。

## 快照与审查中变更

首次 `review-status` 返回初始候选。独立浏览器复跑发现新测试在调整视口后立即读取布局，存在偶发失败。诊断失败当次为 `bottom=868, innerHeight=800`，300 ms 后为 `bottom=768, right=918, innerWidth=980`；不是持续越界。对应产品尺寸更新在 `frontend/src/views/overseas/studio/OverseasStudio.vue:98` 的 resize / ResizeObserver 回调。

主 Agent 修订 `frontend/tests/studio-any-file.browser.mjs:87`：用有界 `waitForFunction` 等待实际几何条件，不放宽边界，增加正宽高和顶部条件；默认超时由该文件第10行设为20秒。产品代码没有因此改变。已阅读修订并对最终候选独立重跑完整浏览器流程，退出0。结束前 `review-status` 的 `currentId` 等于本报告最终 candidateId。旧测试时序问题已关闭。

## Stage 1：Spec Compliance — PASS

| 需求 / 验收项 | 结论与实现证据 | 验证证据 |
| --- | --- | --- |
| 任意格式；取消扩展名白名单与选择器过滤 | 完整实现。`frontend/src/api/overseas/studio.ts:48` 只检查非空与大小；`frontend/src/views/overseas/studio/OverseasStudio.vue:29` 无 accept。`backend/app/overseas/studio/files.py:26` 不按格式拒绝，未知类型第32行回退 octet-stream。 | `backend/tests/test_studio_any_file.py:17` 的22种名称覆盖 ZIP/RAR/7z/tar.gz、字体、设计源文件、音视频、DOC/PPT、自定义/无后缀、HTML/SVG/脚本/EXE。真实 multipart、下载、发送均走应用接口。 |
| 取消旧文档转换、Office结构、文本编码上传前置限制 | 完整实现。`backend/app/overseas/studio/files.py:26` 已删除旧DOC/PPT、Office ZIP结构、文本解码和文档签名拒绝分支；保存输入 bytes。 | `backend/tests/test_studio_any_file.py:21` 使用不满足旧格式/编码校验的原始字节，仍上传成功并逐字节下载；`backend/tests/test_overseas_studio.py:95` 覆盖旧文档、坏PNG、含NUL文本。 |
| 点击、拖拽、粘贴共用上传路径 | 完整实现。`frontend/src/views/overseas/studio/OverseasStudio.vue:111` 三个入口调用 receive；`frontend/src/views/overseas/studio/use-studio.ts:178` 共用状态/上传处理。 | 最终浏览器独立实跑：选择6、拖入1、粘贴1；`frontend/tests/studio-any-file.browser.mjs:57` 起检查真实组件与 multipart 请求字节。 |
| 非空、单文件500 MB、每轮100附件 | 完整实现。`backend/app/overseas/studio/files.py:28`、`backend/app/overseas/studio/router.py:78` 保留校验及有界multipart；`backend/app/overseas/studio/schemas.py:17` 保留100上限；前端 `studio.ts:49` 保留500 MB。 | 独立41项回归包括 `backend/tests/test_overseas_upload_limits.py:12` 的500,000,000边界、`:28` 的100/101条、`:38` 的真实multipart流；浏览器第76行空文件拒绝。 |
| 权限、状态、跨任务隔离 | 完整保持。`backend/app/overseas/studio/files.py:74` 权限锁、write access、studio状态；`:96` 下载鉴权；`queries.py:18` 权限及workflow；`:34` 附件所属任务校验；`service.py:17` 状态/审核、`:56` 在途门禁。 | `backend/tests/test_overseas_studio.py:78` 跨任务404、版本409、无权限403；`:95` 原件下载403；`:165` 未审核与旧流程409。未把放开格式解释为放开访问控制。 |
| 原件保存、刷新恢复、素材引用、发送冻结、交付执行目录 | 完整实现。`backend/app/overseas/studio/files.py:79` 记录大小/sha256并存原件；`queries.py:79` 恢复视图；`service.py:68` 从服务端资源冻结输入元数据；`context_assets.py:69` 恢复原件并验长度/校验和。 | `backend/tests/test_studio_any_file.py:32` 至52行逐格式走真实上传→下载→刷新素材→发送→读Job冻结载荷→执行目录字节比对。浏览器第72行刷新恢复8附件、第82行发送8附件。`test_studio_context_assets.py:69` 起覆盖损坏恢复与错误校验和失败。 |
| JPG/PNG/WebP预览；无法安全预览仍保存 | 完整实现。`backend/app/overseas/studio/files.py:34` 检验真实格式、像素/累计帧像素与完整解码，失败仅改为普通文件；`:50` 清理后缀控制字符。 | `backend/tests/test_studio_any_file.py:55` 有效PNG/伪PNG/恶意名称；`backend/tests/test_studio_image_preview.py:38` 覆盖三种格式、GET/HEAD/下载与权限，相关85项回归日志已核对。 |
| 普通附件安全下载，不自动解压/运行、不执行HTML/SVG/脚本 | 完整实现。`backend/app/overseas/attachment_delivery.py:7` 只允许三类图片预览，普通请求 attachment、nosniff；上传及上下文写入路径没有解压/执行调用。`context_assets.py:22` 清理执行目录名称，`:99` 校验后写入。 | 任意格式API测试第37至41行验证逐字节下载、attachment、nosniff、preview 422；输入声明 text/html 不影响服务端判定。未测或承诺所有格式可被模型解析。 |
| UI文案与沿用现有界面 | 完整实现。`OverseasStudio.vue:29` “支持任意格式文件”；`StudioAttachments.vue:5`、`StudioMaterials.vue:10` 将文档改为文件，下载组件保持。 | 实际浏览器检查1366×900及980×800；截图 desktop.png、narrow.png。最终窄窗几何等待通过。素材侧栏覆盖方式是既有CSS，本轮无布局/CSS更改。 |
| 编译、前后端测试、浏览器、独立审查与不部署 | 本轮验收执行完成；具体输出见下文。 | 前端352通过、构建成功；独立后端41通过；相关回归85通过；最终浏览器独立通过。后端全量非全绿，8个同环境HEAD基线失败明确列示，不隐去。 |

部分实现：无。未实现：本轮范围内无。Spec漂移：未新增页面/API/表/服务；未修改国内专用图片入口；未知mime回退与名称清理服务于本轮原件上传与安全下载要求。

## Stage 2：Code Quality — PASS

| 检查项 | 结论与证据 |
| --- | --- |
| 命名、结构、类型、规模 | 本轮改动集中且无重复新上传链路。实现文件分别109/77/119/25/31行，新增后端测试71行、最终浏览器测试98行，均未超过300行；位置 `backend/app/overseas/studio/files.py:26`、`frontend/src/api/overseas/studio.ts:48`、三个Vue文件如上。前端改动未引入any，`AbortSignal.any` 是既有API名称而非类型。 |
| 错误处理 | `files.py:28`、`:83`、`:102` 分别保留输入、存储及交付错误；图片验证异常仅降级预览，符合本轮需求，不吞存储失败。`attachment_delivery.py:17` 缺文件/存储故障返回503。 |
| 测试真实性 | 22类后端用例调用真实FastAPI multipart路由、数据库服务和发送函数；存储是隔离fixture，模型未调用。`test_studio_any_file.py:50` 的read_source是回调替身，因此它证明真实context落盘/校验，不单独证明生产MinIO网络读取。结合真实下载、冻结payload、`test_studio_context_assets.py:87` 校验和负例，足以覆盖本轮格式放宽链路。浏览器是真实生产构建、API拦截，不能表述成生产全链路或真实模型解析验收。 |
| 安全扫描 | 对五个改动实现文件扫描 eval、innerHTML、dangerouslySetInnerHTML、前端KEY/SECRET/TOKEN、密钥前缀、硬编码密码等无命中。代码人工核对 `files.py:50`、`:81`，对象key由UUID构造，原名不作为存储路径；`attachment_delivery.py:8` 严格预览列表及attachment/nosniff保留；未发现新增注入、任意执行或认证绕过。 |
| 实际视觉对照 | 在同一隔离真实浏览器中查看工作台，再点击“返回任务列表”打开邻居工作流任务页；`output/playwright/studio-any-file/neighbor.png` 为本次截图，非历史截图。与desktop.png对照：同一导航壳、浅色背景、白卡、主题蓝按钮及描边体系；本轮只改文案和过滤属性，`frontend/src/views/overseas/studio/studio.css:17`、`:59` 的间距/字号/附件布局未改。未发现本轮引入的视觉差异。 |
| 新测试的时序缺陷 | 初始候选浏览器第87行偶发失败，已按本报告“快照与审查中变更”定位和关闭；最终候选有界等待保留严格几何断言，独立复跑退出0。 |

安全问题：未发现本轮新增问题。遗留质量阻塞：无。后端Windows平台能力限制保留为验证边界，不宣称全量零失败。

## 原始验证输出与边界

独立复跑命令：`.venv/Scripts/python.exe -m pytest tests/test_studio_any_file.py tests/test_overseas_studio.py tests/test_overseas_upload_limits.py tests/test_studio_context_assets.py -q`。

```text
.........................................                                [100%]
41 passed, 2 warnings in 13.87s
```

两条警告来自 FastAPI/Starlette 对 httpx 与 anyio BlockingPortal 的弃用提示，不是本轮失败。

最终候选浏览器独立复跑命令：设置已有 `PLAYWRIGHT_MODULE` 后执行 `node tests/studio-any-file.browser.mjs`，退出0。原始输出：

```json
{"passed":true,"selected":6,"dropped":1,"pasted":1,"restored":8,"sent":8,"emptyRejected":true,"errors":[],"unexpected":[]}
```

已读取主 Agent 保存的全量前端日志 `output/studio-any-file-frontend-tests.log`：

```text
ℹ tests 352
ℹ suites 0
ℹ pass 352
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8521.2025
```

类型检查 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：主 Agent 执行记录为退出0、无输出；本报告不冒称独立重跑。已读取构建原始日志 `output/studio-any-file-build.log`，摘录：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4666 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 31.86s
```

主 Agent 执行的相关回归 `output/studio-any-file-related.log`：`85 passed, 7 skipped, 2 warnings in 22.30s`。未重跑重复全量。

Windows后端全量及独立HEAD基线日志已读取核对：

```text
# output/studio-any-file-backend-all.log
8 failed, 2031 passed, 357 skipped, 6 warnings in 259.56s (0:04:19)
# output/studio-any-file-head-failures.log
8 failed, 13 passed, 2 warnings in 6.57s
```

两份日志失败集合一致：management_freeze的确认绑定1项、overseas_pictures的3项、pictures_protocol的4项；7项 `OSError: safe open unavailable`、1项 `WinError 1314` 符号链接权限，基线日志对应第61/95/127/159/194/225/264/299行。主 Agent 用git archive HEAD独立源码、同一venv复跑；不是将当前实现移除校验后重测。本轮未改这些模块，不把基线问题认定为新增回归。跳过项和真实生产/模型能力均不视为已验证。

最终批准仅适用于本报告所列 candidateId 和本轮任意格式附件范围；后续代码变化须重新固定快照并复核。
