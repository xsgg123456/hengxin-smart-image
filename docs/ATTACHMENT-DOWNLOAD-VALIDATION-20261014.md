# 2026-10-14 附件仅下载：实施与验证

## 授权与范围

用户取消全部附件在线预览方案，确认删除海外图需和工作台上传附件的预览功能，保留上传、信息展示、原件下载和Codex引用。此次为本地实现，不提交、不部署、不清空生产数据。

## 实现

- 删除PDF/文本/表格阅读器、预览弹窗、解析版本与重试入口，以及前端pdfjs-dist和专属构建资源插件。
- 图需使用两类附件卡片；工作台任务素材、历史对话附件使用文件信息与下载按钮。长文件名换行。工作台生成图片和生成图片引用的查看保留。
- 新上传不再执行文档解析。metadata只返回原件信息，旧解析记录不再进入浏览器；提交不再依赖ParseVersion。历史表和原件保留，无数据库迁移。
- 旧legacy分析仍依赖文本提取，因此只在旧分析需要时校验并读取原件、内部解析，保留既有成功结果和历史记录。工作台冻结原件、完整性校验和Codex输入不变。
- 两入口使用HEAD预检与同源原生下载；实际GET再次鉴权。后端stat验证存在及大小，文件按64KiB流式传输，传输前释放数据库会话，连接断开后释放存储连接。
- 401/403上抛身份/权限处理；404/503/网络/超时错误留在附件卡片，保留当前页面和草稿，可重试。提示只称“已发起下载”，不称完成。
- 500,000,000字节上传上限、图需不限扩展名、工作台11种扩展名及100附件上限保持。

浏览器下载行为依据：[MDN anchor下载说明](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a)、[Content-Disposition](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Disposition)。下载使用同源地址与attachment响应头，不暴露存储签名链接。

## 验证方式

- 前端：`pnpm typecheck`、`pnpm test`、`pnpm build`；本轮单测363通过，包括实际SFC取消/卸载/迟到响应、失败保留页面、权限传播、HEAD失败不触发下载。
- 后端：专项108项通过。正确Linux隔离环境完整回归2301 passed、188 skipped、15 warnings（288.67s）；命令为`docker run --rm --init --network none -e PYTHONDONTWRITEBYTECODE=1 -v <项目代码>:/workspace:ro -w /workspace/backend hx-overseas-delete-skills-test:local /app/.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider`，日志`output/attachment-backend-linux-init.log`。条件跳过主要为外部服务测试，另用真实隔离拓扑验证PG/Minio/身份链路。Windows安全文件系统/符号链接失败及首次Linux遗漏--init导致PID1监管失败，均在正确环境通过，未以改产品代码绕过。
- 正式dist通过Vite preview分别服务3015（拦截API）和3017（真实隔离API）。Playwright使用一次性Chromium上下文，不使用用户浏览器。
- `attachment-download.browser.mjs`：实际本地HTTP服务先发64KiB，延迟2.5秒发送剩余内容，证明浏览器下载事件早于正文完成；下载字节与文件名一致。覆盖任务资料、历史对话上传附件、取消HEAD、存储故障、无图片附件预览、生成图片保留、长名换行与390px布局。样本2MiB为测试数据，86.1MB显示值仅为布局fixture，不能作为真实86MB公网速度证据。
- `overseas-materials-real.browser.mjs`：真实PostgreSQL/Minio/身份服务下任意原件上传、提交、移除确认、原生下载字节/文件名、多角色GET/HEAD权限、改派后权限撤销及长名窄屏。
- `overseas-studio-real.browser.mjs`：真实图需和工作台新上传附件均下载并逐字节核对；引用/移除、发送、刷新、停止、展开与窄屏。没有启动模型worker或收费调用。
- 故障/回归脚本：`overseas-materials-faults.browser.mjs`、`overseas-tasks-faults.browser.mjs`、`material-time.browser.mjs`、`studio-native.browser.mjs`、`studio-refresh-skills.browser.mjs`。
- 真实隔离拓扑：`IDENTITY_TEST_IMAGE=hx-overseas-delete-skills-test:local python infra/identity-test/run.py --delete-skills --serve --origin http://127.0.0.1:3017`。需要delete-skills标志准备安装Skill目录；旧测试镜像缺openpyxl或未初始化目录均不代表产品缺陷。

## 证据与边界

截图位于`output/playwright/attachment-download/`及`output/playwright/phase20/`，命令输出与单测日志位于本地output和frontend忽略文件。最终审查报告另存docs/reviews。

本轮不新增预览转换器、资源队列、Range/断点续传，不改变原件或重新编码。浏览器进度改善不等于增加公网带宽；生产下载速度及正式发布验收留待部署时完成。

## 独立审查

两阶段均PASS，candidateId `a77465aaf536cb052a33d2cd3198be27019496f52a0af51b8dcbe37cf9ac1d51`。独立复跑后端31项、前端7项、原生流式下载及真实材料浏览器流程均通过；报告见[附件仅下载审查](reviews/ATTACHMENT-DOWNLOAD-20261014.md)。主Agent已登记同一快照批准凭据。未Git提交、未部署。

后续用户授权发布：已随0.2.34提交上线，实际镜像安装、生产下载完整性及正式页面验收见[发布记录](ATTACHMENT-RELEASE-20261014.md)。上文“未提交/未部署”为本地实现阶段状态。
