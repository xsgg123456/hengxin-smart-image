# 海外工作台任意格式附件

用户已授权实施，不只放开ZIP/字体白名单。沿用既有工作台布局、文件卡片、草稿恢复、素材移除和执行上下文，不新增服务或数据库迁移。

## 顺序与完成标准

1. 取消前端扩展名校验及文件选择accept过滤，文案改为支持任意格式；点击、拖拽、粘贴共用上传链路。保留非空、500 MB及100附件限制。
2. 后端保存原件，不以文件扩展名、文档结构或文字编码拒绝上传。已验证图片保留预览，无法安全预览的图片和未知格式作为普通附件；下载仍鉴权、attachment与nosniff，不自动解压或执行。
3. 覆盖压缩包、字体、设计源文件、音视频、旧文档、未知后缀、无后缀、Unicode/路径文件名及文本编码；验证原始字节下载、刷新后的素材、发送快照和执行目录，检查跨任务/权限/大小限制及图片预览回归。
4. 前端类型检查、全量单测、生产构建，后端回归与浏览器隔离验收，固定快照并完成独立两阶段审查。记录实测结果；生产部署另行执行。

本次为现有上传能力调整，既有DEV-PLAN阶段划分与技术栈不变；本文件补充本轮有序实施和验收标准。

## 验证记录

- `backend/.venv/Scripts/python.exe -m pytest tests/test_studio_any_file.py tests/test_overseas_studio.py tests/test_overseas_upload_limits.py tests/test_studio_context_assets.py -q`：41 passed，2依赖弃用警告。包括真实500 MB边界、未知格式、下载字节、发送冻结和执行目录保真。
- 前端 `node --import tsx --test tests/*.test.ts`：352 passed、0 failed；日志 `output/studio-any-file-frontend-tests.log`。
- 前端 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 退出0；`node node_modules/vite/bin/vite.js build` 退出0、31.86s，日志 `output/studio-any-file-build.log`。
- `node tests/studio-any-file.browser.mjs`：真实本地生产构建，浏览器独立上下文、API拦截，无生产数据/模型调用；选择6、拖入1、粘贴1、刷新恢复8、发送8，空文件阻止，无页面错误或意外请求。截图 `output/playwright/studio-any-file/desktop.png`、`narrow.png`；980宽继承现有素材覆盖面板，不改布局。
- 图片预览、修改、素材列表、上下文与任意格式相关回归：85 passed、7 skipped、2 warnings（22.30s）；日志 `output/studio-any-file-related.log`。Windows下依赖POSIX的用例跳过。
- Windows后端全量：2031 passed、357 skipped、8 failed、6 warnings（259.56s）；日志 `output/studio-any-file-backend-all.log`。8失败来自未改的旧工作流 `test_overseas_management_freeze.py`、`test_overseas_pictures.py`、`test_overseas_pictures_protocol.py`：7项 `OSError: safe open unavailable`、1项 `WinError 1314` 符号链接权限。
- 通过 `git archive HEAD hengxin-smart-image/backend` 建立独立原始源码副本 `output/studio-any-file-head`，相同venv/环境重跑以上三个模块，完全相同8项失败，另13 passed（6.57s）；确认导入模块路径来自HEAD副本。日志 `output/studio-any-file-head-failures.log`。本次不修改或跳过旧测试，不将全量结果写成零失败。
- 独立复跑发现窄屏切换后立即取rect的断言偶发失败：审查诊断当次note.bottom=868超过800视口，300ms后bottom=768、right=918≤980，属于resize异步布局时序。改为有界等待真实note布局进入视口，保留原边界并补充正宽高和顶部条件，不改产品布局。修订后浏览器全流程再次通过。
- 最终独立审查候选 `1f1a7ee0768ade40924a66e9b92ac6557a06a5ea55e4914d65c8df209aa37b01`：Stage 1 PASS、Stage 2 PASS；与初始 `010dd18c327f31a6ac9bccbd3b3b8ac32fe52b8988cd1eaf5c39cc3178ffe070` 的代码差异仅为上述浏览器断言。审查者独立复跑后端41项和最终浏览器脚本通过，报告见 [独立审查](reviews/STUDIO-ANY-FILE-20261022.md)。

上传仅保存并传递原件。没有新增自动解压、字体安装、任意格式自动解析，也没有触发真实Codex出图。已于2026-10-22以0.2.48发布，实测结果及浏览器上传验收限制见 [生产发布记录](STUDIO-ANY-FILE-PRODUCTION-20261022.md)。
