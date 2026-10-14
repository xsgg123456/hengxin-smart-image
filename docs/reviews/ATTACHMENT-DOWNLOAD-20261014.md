# 附件仅下载独立审查（2026-10-14）

- candidateId：`a77465aaf536cb052a33d2cd3198be27019496f52a0af51b8dcbe37cf9ac1d51`
- 审查范围：本轮工作区相对 HEAD 的全部 diff、新增未跟踪业务/测试文件，以及对应需求、计划和验证文档；覆盖 materials、plans、requirements、studio、前端附件组件/API/页面、pdfjs 依赖移除及隔离测试更新。未对既有完整产品重新验收。
- 依据：`Product-Spec.md:1137`、`DEV-PLAN.md:1403`、`docs/ATTACHMENT-DOWNLOAD-VALIDATION-20261014.md:1`；使用 `.agents/skills/code-review/SKILL.md` 两阶段流程。
- 开始和结束执行 `review-status`，两次 currentId 均与上述 candidateId 一致。期间仅验证文档追加 Linux 结果，未发现代码快照变化。本报告不登记批准，不写 clean，由主 Agent 对同一快照执行 review-approve。

## Stage 1 — Spec Compliance：PASS

以下路径中的 `backend/`、`frontend/` 均相对仓库内 `hengxin-smart-image/`。

| 要求 | 结论与实现证据 | 验证证据 |
|---|---|---|
| 图需取消在线预览，保留上传、两类信息、名称、大小、下载及移除/更换 | 完整实现。`frontend/src/views/overseas/OverseasMaterialsPanel.vue:4`、`:9`、`:12`、`:49`、`:59`、`:70`；阅读器、缩略图、文本表格页及预览弹窗文件已删除 | 审查者独立运行真实材料浏览器脚本 PASS；任意原件提交、删除确认、下载字节及名称通过 |
| 工作台任务素材、待发和历史上传附件仅下载，保持引用 | 完整实现。`frontend/src/views/overseas/studio/StudioMaterials.vue:7`、`:12`，`OverseasStudio.vue:12`，`StudioTurns.vue:6` | 独立原生下载浏览器脚本 PASS；图片上传附件没有 img、没有隐式 GET、没有预览弹窗；任务素材及历史附件均下载 |
| 生成图片、生成图片引用及成品查看保持 | 完整实现。`frontend/src/views/overseas/studio/StudioTurns.vue:6`、`:14` 与 `OverseasStudio.vue:12` 保留 ElImage 预览；`backend/app/overseas/studio/files.py:124` 保留生成图片 inline；成品模块无改动 | `backend/tests/test_overseas_attachment_downloads.py:77` 验证生成图 inline；浏览器断言生成图节点存在，桌面截图目视生成图卡片保留 |
| 移除解析版本/重试 UI、公共 retry API、pdfjs 和专属构建资源 | 完整实现。`frontend/src/api/overseas/materials.ts:4` 精简类型；`backend/app/overseas/materials/router.py:28` 至文件末尾仅 metadata/delete/content/list/submit；删除 vite.pdf-assets.ts；package.json/锁文件已移除 pdfjs | `backend/tests/test_overseas_materials.py:82` 与真实浏览器脚本验证 retry 404；搜索当前正式源码未发现旧阅读器/pdfjs 引用 |
| 新上传不解析；原件 metadata；历史失败可绑定/下载 | 完整实现。`backend/app/overseas/materials/files.py:34`，`materials/service.py:40`、`:59` | `backend/tests/test_overseas_materials.py:102` 历史失败记录仍 ready、可绑定；`:233` 未解析原件可提交和下载；独立后端专项通过 |
| 旧工作流文本解析按需内部保留，历史不删除 | 完整实现。`backend/app/overseas/plans/snapshot.py:29` 按需读取并解析，已有成功文本复用；`materials/service.py:47` 追加 ParseVersion；router/requirements 将 store 传入 | `backend/tests/test_overseas_attachment_downloads.py:89` 校验缺失/损坏/不支持格式不会排队；`:152` 验证失败历史保留且内部重试生成正确任务文本 |
| Codex 原件冻结和校验保持 | 完整实现。`backend/app/overseas/studio/service.py:60` 冻结对象及 checksum，`studio/execution.py:58` 调用 read，`studio/files.py:77` 校验大小及 SHA256，相关逻辑未改变 | Linux 全回归 2301 passed；本轮真实 studio 下载与引用验证见交付验证文档；没有启动收费模型 worker，不声称完成真实模型调用 |
| 同源原生下载、不整份 Blob、预检失败可见、GET 再鉴权 | 完整实现。`frontend/src/api/overseas/attachment-download.ts:9` 白名单/HEAD/cookie/禁止跳转，`:23` 原生 a.download；`backend/app/overseas/materials/router.py:40`、`:46` 及 `studio/router.py:69`、`:75` 分别独立鉴权 | 独立浏览器脚本使用 2 MiB 慢 HTTP，下载事件早于正文结束、全字节及文件名一致；真实材料脚本验证五角色 HEAD/GET 和改派撤权 |
| 轻量 HEAD，GET 流式、连接释放 | 完整实现。`backend/app/overseas/attachment_delivery.py:14` stat，不读取正文；`materials/files.py:60`、`studio/files.py:120` 捕获数据后关闭会话；`backend/app/modules/files/streaming.py:8` 64 KiB、`:11` finally close/release_conn | `backend/tests/test_overseas_attachment_downloads.py:18` 双来源 HEAD 不 open、GET 分块上界；`:115` 断连释放；`:136` 存储读取前无 DB 事务 |
| 404/503/网络失败留卡片、保留草稿；401/403上抛；不误报完成 | 完整实现。`frontend/src/views/overseas/AttachmentDownload.vue:22` 仅身份/权限失败 emit；`:6` 文案“已发起下载”；取消及卸载中止 HEAD | 独立实际 SFC 测试 7 passed，覆盖错误/重试、取消/卸载/迟到成功、超时、不读取 Blob；浏览器存储失败不产生 GET |
| 全部附件长名换行，不挤压操作 | 完整实现。`frontend/src/views/overseas/OverseasMaterialsPanel.vue:80`，`studio/studio.css:18`、`:37`、`:43` 使用 min-width/换行/独立操作区域 | 独立运行并目视桌面与 390px 工作台、真实图需审核页截图；浏览器检查页面/卡片/标签 scrollWidth、scrollHeight；文件名完整，下载操作可见 |
| 500 MB、格式与100附件规则保持 | 完整实现。`frontend/src/api/overseas/upload-limits.ts:1`，`backend/app/overseas/upload_limits.py:2`，`studio/files.py:21`、`:26`，`studio/schemas.py:12`；既有校验未变 | 前端 363 单测及 Linux 全回归通过；浏览器故障用例含500,000,001字节拒绝，既有100/101及两类独立计数回归保留 |
| 不清空生产原件/历史表，不迁移，不自动部署 | 完整实现。当前 diff 无迁移/数据清理/发布操作；`materials/files.py:18` 继续存原件，`materials/service.py:47` 保留历史追加模型 | git diff/status 核查；执行仅隔离环境和本地正式 dist |

部分实现：无。未实现：无。引导真实性：上传文案现为保存/下载，取消解析引导，见 `OverseasMaterialsPanel.vue:4`、`:23`；未发现死引导。Spec 漂移：无；HEAD 和共享下载模块是本轮明确实现要求。

## Stage 2 — Code Quality：PASS

- 职责与类型：共享下载 helper、SFC、后端 delivery 各自独立；所有本轮修改/新增业务源码文件不超过300行（最长 `frontend/src/views/overseas/OverseasDetail.vue:1` 起296行；新 helper28行、SFC38行、delivery21行）。扫描未发现新增 TypeScript any；AbortSignal.any 与 Python any 为函数名。错误类型收敛在 `AttachmentDownload.vue:22`，不把存储故障升级成父页面清空。
- 安全：`attachment-download.ts:11` 限定同源两类内容路由，拒绝外域、路径穿越与生成图片路径；`attachment_delivery.py:10` 文件名百分号编码、防嗅探、private no-store；`:20` 不回传存储内部异常。读取前权限检查位于 `materials/service.py:29`、`studio/files.py:115`。扫描本轮业务源码未发现硬编码密钥、eval、innerHTML、危险HTML注入或字符串拼SQL。新测试中的 `new Function` 仅在 SFC测试加载器执行本地编译产物，`frontend/tests/attachment-component.test.ts:22`，不进入产品。
- 测试真实性：审阅双来源分块测试、HEAD不open、断连和关闭session测试；实际SFC挂载测试并非只检查源码字符串；慢HTTP测试以真实浏览器下载事件和读取下载流对比 bytes，避免仅用拦截响应证明“流式”。2 MiB样本与86.1 MB布局标签不同已明确标注，不将fixture当性能结论。关键依据 `backend/tests/test_overseas_attachment_downloads.py:18`，`frontend/tests/attachment-component.test.ts:16`，`frontend/tests/attachment-download.browser.mjs:24`、`:87`。
- 视觉对比：审查者实际运行工作台及真实图需审核页浏览器流程，打开并目视 `output/playwright/attachment-download/studio-desktop.png`、`studio-mobile.png` 和 `output/playwright/phase20/materials-real-mobile.png`。与同页既有生成图片卡片、图需审核信息卡/返回按钮对照：使用相同 Element 按钮、蓝色和边框，长名无截断、控制仍可访问。390px工作台素材侧栏为既有覆盖式布局，本轮没有新增该交互。样式依据 `OverseasMaterialsPanel.vue:78`、`studio/studio.css:16`、`:37`。
- 质量/安全问题：未发现本轮需修复的 HIGH、MEDIUM 或 LOW 问题。pnpm配置警告及依赖弃用警告为原有环境提示，未导致本轮测试/编译失败。

## 验证原始输出

审查者独立执行（均 exit 0）：

```text
.venv/Scripts/python.exe -m pytest tests/test_overseas_attachment_downloads.py tests/test_overseas_materials.py -q
...............................                                          [100%]
31 passed, 2 warnings in 6.14s

pnpm exec tsx --test tests/attachment-component.test.ts tests/attachment-download.test.ts
ℹ tests 7
ℹ suites 0
ℹ pass 7
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1065.2229

node tests/attachment-download.browser.mjs
PASS native attachment download starts before body completes; exact bytes/name; both sources/history; no uploaded image preview; generated images retained; HEAD error/cancel; long name wraps

node tests/overseas-materials-real.browser.mjs
PASS real materials: arbitrary originals retained/submittable; no preview/retry; native download bytes/name; delete confirmation; frozen binding; GET/HEAD five-role and reassignment authorization; long-name narrow UI
```

读取主 Agent 提供的同一快照原始日志；按派发要求未重复正式构建或 Linux 全套：

```text
# frontend/attachment-typecheck.log
> hengxin-smart-image-frontend@0.2.33 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit

# frontend/attachment-production-build.log（末行）
✓ built in 33.41s

# frontend/attachment-tests.log
ℹ tests 363
ℹ suites 0
ℹ pass 363
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9420.6824

# output/attachment-backend-focused.log
108 passed, 2 warnings in 21.77s

# output/attachment-backend-linux-init.log
2301 passed, 188 skipped, 15 warnings in 288.67s (0:04:48)
```

Linux 188项跳过不计作通过；第一次未配置 --init 导致 supervisor 条件失败，不用于结论，最终按正确 Linux 容器环境全量重验。完整构建输出保留于上述日志。本轮结论覆盖本地实现与隔离验证，不代表生产公网速度、500 MB真实公网传输或收费模型调用已验收。

最终结论：Stage 1 PASS，Stage 2 PASS，可由主 Agent 登记此 candidateId 审查凭据。
