# 工作台图片正式实现独立审查

- candidateId：`35a2cb01ba68898af38effc4f6a20b1d0d29a0c081e22a756a396b094f086da8`
- Stage 1：**PASS**；Stage 2：**PASS**。本轮未发现 HIGH / MEDIUM 缺陷。
- 审查范围：本轮正式前后端图片组件、发送契约、内容接口、测试与 0.2.38 发布入口及其继承调用链；`review-status` 列出的 38 个相对上一批准快照变化文件。另核对 AGENTS 本次需求同步规则及源文档增量。历史独立预览已有独立报告，本报告不重新声称审查所有历史产品功能。
- 需求依据：`Product-Spec.md:1191` 正式实施六项及其引用的最终紧凑预览、`Design-Brief.md:195`、`DEV-PLAN.md:1439`。优先使用正式授权后的要求，历史“仅预览”限制不用于否定已授权正式实现。
- 审查方法：代码逐项核对、独立重跑关键测试、真实隔离浏览器操作、读取原始编译/全量测试/HTTP/数据库/路径证据。未修改实现、未提交、未部署、未调用模型。
- 快照：审查开始及收尾的 `harness.py review-status` 均返回上述 currentId，未发现受控代码漂移。期间仅增加截图、验证结果和 Markdown 说明。报告不写 `.needs-review`，由主 Agent 使用同一 candidateId 登记两阶段 PASS。

下文路径缩写：`F` = `hengxin-smart-image/frontend/src/views/overseas/studio/`；`B` = `hengxin-smart-image/backend/app/overseas/`；`T` = `hengxin-smart-image/backend/tests/`；`R` = `scripts/release/`；`E` = `output/studio-images-20261016/`。

## Stage 1 — Spec Compliance

### 完整实现

| 正式需求 | 结论及代码证据 | 行为证据 |
|---|---|---|
| 待发 56、消息 72、结果 110、素材 48 / 行 68、上传条 32 | PASS。`F/studio.css:46`、`:47`、`:48`、`:49`、`:50`，图片使用 contain，未裁切原比例 | reviewer 独立 DOM 测量依次为 56×56、72×72、110×110、48×48、68、32；6 个附件时 composer 235.5px |
| 默认 3 项、全部弹窗管理 | PASS。`F/StudioAttachments.vue:10`、`:12`、`:24`，compact 分支 slice(0,3)，弹窗递归完整列表，移除事件回父级 | reviewer 实际引用 6 素材：主区 3 项、查看全部显示 6；弹窗包含 6 项及移除按钮 |
| 四区原图查看、分组切换/缩放/计数/关闭/下载；跳过文档 | PASS。`F/StudioAssetImage.vue:2`、`:6`、`:16`、`:23`；`F/StudioTurns.vue:6`、`:14`；`F/StudioMaterials.vue:8`；`F/StudioAttachments.vue:4`、`:7` | 真实浏览器附件 4 图组 JPG 3/4 → WebP 4/4；发送后消息标注 5/6 → 原图 6/6。下载得到 PNG 790×790；HTTP 原始文件和鉴权见 `E/studio-image-edits-result.json:24`。文档使用 AttachmentDownload |
| 窄屏可滚动，主输入、发送与画布确认可达 | PASS。`F/studio.css:54`、`:56`、`:60`；`F/StudioAnnotationEditor.vue:81` | 已目视 `E/mobile.png`、`E/mobile-canvas.png`：390×844 下输入/发送及确认均可见；主代理 DOM 测量 pageWidth=390、发送 bottom=784、确认 bottom=816 |
| 框选/画笔、编号意见、缩放平移、撤销删除清空 | PASS。`F/StudioAnnotationEditor.vue:5` 复用 AnnotationCanvas；`:11` 编号意见。共享 `frontend/src/views/hengxin/components/annotation/annotation-export.ts:13` 按原尺寸合成 PNG | reviewer 实画矩形；主代理矩形+画笔两处截图 `E/canvas.png`；共享几何/撤销/原图坐标/PNG 导出单测实际重跑通过 |
| 无已有标注上传入口、无整体意见框；每处必填 | PASS。`F/StudioAnnotationEditor.vue:8`、`:55`、`:64`；共享 `annotation-drafts.ts:17` 校验全部 mark.note 和完整长度 | reviewer 空意见点击确认，得到“请填写每一处标注的修改意见”；填意见后可进确认预览；对话框内未出现上传或整体输入框 |
| 确认回填、不自动发送、保留原主文字/附件/Skill | PASS。`F/OverseasStudio.vue:12`、`:57`；`F/use-studio.ts:156`；发送仅在 `:109` | reviewer 确认上传后摘要出现、消息仍 2 条、6 个原附件保留。主代理原主文字与附件保留截图 `E/draft.png`；真实主动发送数据库记录见 `E/browser-send-evidence.json:5` |
| 摘要原图/标注图、描述查看、继续编辑、取消 | PASS。`F/StudioRevisionDraft.vue:3`、`:5`、`:7`；`F/StudioAnnotationDialog.vue:18`、`:21`；`F/use-studio.ts:149` | reviewer 继续编辑修改意见后取消，再查看描述仍为先前已确认值；重开原编号回显。取消修改不删除普通附件的用例通过 |
| imageEdits 可选契约及独立 100 限额 | PASS。`B/studio/schemas.py:9`、`:15`；`frontend/src/api/overseas/studio.ts:20`；`F/use-studio.ts:112`、`:160` | 默认空列表保持旧请求；100 附件和 100 原图分别计数、满额替换不增加数量、超额不上传的前端用例通过 |
| 原图/标注必须属于本任务，原图同时引用、标注同时附件、PNG、非重复关联 | PASS。`B/studio/schemas.py:27`、`B/studio/queries.py:31`、`:45`、`B/studio/service.py:55`、`B/studio/image_edits.py:7` | 新增 HTTP 测试实际重跑：缺少引用/附件、重复图/标注、缺图、跨任务、文档、非 PNG 标注均拒绝，失败不创建 job；`T/test_studio_image_edits.py:62`、`:107`、`:172` |
| 无标注可用主输入意见；有标注必须有描述 | PASS。`B/studio/schemas.py:35`、`F/use-studio.ts:20`、`:164` | `T/test_studio_image_edits.py:123` 纯文字原图修改通过；缺描述/空白意见拒绝。前端相同边界用例通过 |
| 冻结 ID 对应实际路径，不按文件名关联 | PASS。`B/studio/image_edits.py:9`、`:18`、`:40`；`B/studio/execution.py:86` | 同名 result.png 不混淆，索引错配 fail closed；真实 PG/MinIO/生产 context prepare 生成 3 份实际文件，逐份 SHA256 匹配；`E/studio-image-edits-result.json:5` |
| 原图为编辑基础、标注仅定位、编号不进成品；完整描述与主补充 | PASS。`B/studio/image_edits.py:45`、`:54`；`B/studio/execution.py:85` | `E/studio-image-edits-prompt.txt:1` 包含实际 originalPath/annotationPath 与完整指令；7772 字符提示词验证；真实 UI 冻结两处意见及主输入见 `E/browser-send-evidence.json:5` |
| 可读消息保留原图/标注，旧幂等和未知结果完整重试 | PASS。`B/studio/image_edits.py:23`、`B/studio/service.py:17`、`:72`；`F/use-studio.ts:37`、`:83`、`:103`、`:116` | 同 key 同完整 payload 重放，无新增 job；同 key 更改意见 409；旧 fingerprint 不包含空 imageEdits；跨卸载重试 body/key/文件 ID 不变且不重复上传。`T/test_studio_image_edits.py:39`、`:130`；前端专项重跑 |
| 保留任务权限、会话、Skill | PASS。`B/studio/service.py:18`、`:57`、`:62`；`B/studio/queries.py:15`；`F/use-studio.ts:156`、`:168` | 只读无上传；401 清空可见数据；上传中会话变化/卸载拒绝回填；真实冻结 conversationId 和原调用链仍沿用，未新增绕权发送路径 |
| 图片 inline；文档仍下载；原鉴权及生成图 HEAD | PASS。`B/attachment_delivery.py:7`；`B/materials/router.py:40`；`B/studio/router.py:70`、`:87`；`B/studio/files.py:116` | reviewer 重跑 `T/test_studio_image_preview.py`：PNG/JPEG/WebP GET/HEAD/default download、401/403、文档与 SVG/HTML/PDF/GIF 预览拒绝、缺失对象503、HEAD不读取正文均通过 |
| 500 MB 不变，标注计附件数，国内共享导出仍 10 MiB | PASS。`F/StudioAnnotationEditor.vue:65`，共享 `annotation-export.ts:4`、`:11`；`F/use-studio.ts:160` | 新参数显式传海外 MAX_UPLOAD_BYTES，国内缺省值未变；导出边界及双100测试重跑通过 |
| 发布只更新海外执行链与共享前端，不迁移数据库 | PASS（发布实现）。`R/package-studio-images.py:9`；`R/overseas-images-deploy.py:18`、`:44`、`:89`、`:127` | 包固定0.2.38/0029/0016，before_switch 仅 SELECT/备份排空凭据，无迁移或恢复调用；专项49通过，发布完整回归原始XML无失败 |
| 保护生产基线、国内/身份、Skill、会话/原件；安装测试/排空/备份/失败关闭 | PASS（发布实现）。`R/overseas-images-deploy.py:24`、`:50`、`:64`、`:68`；继承 `R/overseas-upload-deploy.py:101`、`:156`、`:183`、`:262`；`R/overseas-upload-resources.py:29` | 已检查完整继承链：国内worker+deletion PID/配置摘要、海外实际cwd/User及99指针、完整Compose叠加、3GiB、代理500MB、安装镜像凭据、两次稳定排空、备份COMPLETE、失败重新关闭入口；故障注入覆盖 preflight/备份/切换/开放后阶段 |

### 部分实现 / 未实现 / Spec 漂移

本次正式范围未发现部分实现或未实现条目。发布执行尚未发生，属于审查后的阶段，不把脚本通过当成部署成功；生产安装镜像测试、备份切换和部署后目视必须由主 Agent 实际完成并留证。

未发现未授权产品扩展。`infra/identity-test/provider_app.py:24` 的登录 helper 只挂在隔离测试 app；正式 `app/identity/main.py` 未导入它，打包 allowlist `R/package-overseas.py:89` 排除 `infra/identity-test`。仅为验收支撑，不是生产免密登录入口。AGENTS.md:82 的讨论/预览范围规则符合本轮采纳要求。

## Stage 2 — Code Quality

- **结构与类型 PASS**：新增图片预览、附件、摘要、画布、确认弹窗分别封装；`F/StudioAssetImage.vue:11`、`F/studio-revisions.ts:1`、`F/use-studio.ts:10` 使用显式类型。新增/修改生产模块均不超过300行（继承发布模块恰300行；新增最大发布入口136行）。本轮未引入 TypeScript `any`。
- **错误与异步生命周期 PASS**：`F/StudioAssetImage.vue:18` HEAD失败反馈；`F/StudioAnnotationEditor.vue:42` generation防迟到回写、`:73`撤销URL；`F/use-studio.ts:156` 上传先成功再替换摘要，`:168`核对会话；dialog独立编辑副本取消不覆盖已确认稿（`:18`、`:21`）。这些边界有专项用例及实际取消交互证据。
- **测试真实性 PASS**：抽查不是只有纯函数顺畅路径。后端TestClient经过真实发送路由/SQLAlchemy事务并检查job数量；跨任务测试真实换任务归属；真实独立PG/MinIO检验冻结字节及持久路径。前端mounted composable覆盖未知结果、401、超限、迟到上传；真实浏览器补充组件事件、两级确认、取消和最终发送。发布测试使用故障注入验证调用顺序，另验证新入口确实继承原全阶段测试（`R/test_overseas_images.py:25`、`:49`、`:68`）。
- **安全扫描 PASS（本轮增量）**：对变更模块扫描eval、innerHTML、危险渲染、前端KEY/SECRET/TOKEN及硬编码密钥，未发现新增命中；`AbortSignal.any`是方法名，不是类型any。`B/attachment_delivery.py:8`限定安全栅格类型、`:14`no-store/nosniff、文件名quote；`B/studio/queries.py:15`、`:31`、`:45`先鉴权和任务归属。冻结索引不接收客户端路径（`B/studio/image_edits.py:40`）。打包真实选中文件隐私扫描测试通过（`R/test_package_studio_images.py:33`）。
- **发布防护 PASS**：`R/overseas-images-deploy.py:133`拒绝Python优化模式，避免assert失效；`:95`为每次curl及整体reload等待设置期限。新发布入口不执行父模块旧迁移hook（`:127`覆盖）；历史包默认版本和schema仍有回归断言（`R/test_package_studio_images.py:65`）。
- **视觉对比 PASS**：reviewer 实际打开正式工作台和邻居“工作流任务”列表，检查蓝色主按钮、白底圆角卡片、细边框、文本密度与共享侧栏。截图 `E/reviewer-workspace.png`、`E/reviewer-neighbor.png`；正式紧凑尺寸的DOM测量见Stage1。已独立目视主代理 `canvas.png`、`draft.png`、`mobile.png`、`mobile-canvas.png`，未见裁切导致输入/确认不可达。
- **既有边界**：依赖审计仍有 high70/moderate48/low5，critical0，本轮未改依赖或锁文件；不能将本报告表述为所有历史依赖漏洞已修复。构建存在既有pnpm配置提示。该记录不等同于本轮新增安全缺陷。

## 编译与测试原始证据

reviewer 已读完整构建首尾及测试日志/XML；以下为原始输出节选，不以“应该通过”代替结果。

生产构建 `E/frontend-build.log`：

```text
> hengxin-smart-image-frontend@0.2.38 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4739 modules transformed.
✓ built in 1m 20s
```

reviewer 独立重跑：

```text
python -m pytest -q tests/test_studio_image_edits.py tests/test_studio_image_preview.py
36 passed, 2 warnings in 8.69s
python -m pytest -q scripts/release/test_overseas_images.py scripts/release/test_package_studio_images.py
49 passed, 24 subtests passed in 1.98s
pnpm exec tsx --test tests/overseas-studio-images.test.ts tests/annotation-canvas.test.ts
ℹ tests 18
ℹ pass 18
ℹ fail 0
ℹ skipped 0
```

全量原始记录：

```text
output/studio-image-frontend-tests-20261016.log
ℹ tests 378
ℹ pass 378
ℹ fail 0
E/backend-final.log
2551 passed, 195 skipped, 15 warnings in 325.27s (0:05:25)
E/backend-final.xml
tests=2746 failures=0 errors=0 skipped=195
output/studio-images-release-tests.xml
tests=763 failures=0 errors=0 skipped=1
```

发布XML计数含subtests，对应549 passed、213 subtests passed、1 skipped。首轮缺少docker `--init` 的Linux运行确有8失败；既有监督器拒绝PID1父进程，修正容器执行环境后同文件26 passed/1 skipped，最终上述全量2551通过。没有为消除失败修改业务监督逻辑，195跳过不计为通过。

## 验收边界与交接

真实发送验证到浏览器→HTTP→数据库冻结→生产沙箱prepare→实际文件及prompt；`E/browser-send-evidence.json:4` 和 `E/studio-image-edits-result.json:32` 均记录modelCalls=0。排队任务随后通过UI停止；没有声称真实模型已完成图片修改。上线后真实收费生成质量、生产安装镜像与实际切换结果不属于此刻已取得的证据。

两阶段PASS只授权上述同一快照进入主Agent的review-approve/提交/发布流程；若受控代码再变，须重新prepare并复核差异。
