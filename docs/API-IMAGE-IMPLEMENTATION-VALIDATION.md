# API 换套图验证记录（2026-09-22）

## 已执行

- 后端完整回归：`TEST_DATABASE_URL=<独立回归库> .venv/Scripts/python.exe -m pytest -q`，840 passed / 112 skipped。跳过包含 Windows 不支持的 Linux 进程隔离、符号链接和额外环境用例；不将跳过项计作通过。
- 新模块领域/执行测试 18 passed；适配器测试 19 passed；真实 PostgreSQL 多线程幂等/认领/fencing 测试 2 passed。迁移 0015 升级→回退0014→再次升级成功。
- 前端：`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 零错误；Node 全套测试 137/137；production 和 demo 构建成功。
- Compose：基础配置叠加 `compose.api-image.yaml` 后 `config --quiet` 成功。
- 真实接口浏览器测试：上传格式错误、真实上传、原图/素材调整、跨路由草稿保留、失败收图恢复、双图展示、真实下载、搜索空态、删除取消、1280宽度与无页面异常，通过。证据在 `output/api-live/browser-evidence.json`。

## 真实中转站闭环

使用专用 PostgreSQL/Redis/MinIO、本地 FastAPI、独立 Celery worker/outbox，关闭 CLI 执行器。提交两张合成原图和一张素材，重复同键提交返回相同任务。

上游请求次数 **2**，生成重试 **0**；最终两张结果均落本平台存储、按原图顺序展示并下载。CLI 的 files 和 task_records 表均保持0条。本测试没有运行真实 CLI 图片生成，不能据此宣称已测过双通道同时生成。

本机代理最初将 CDN 解析至 198.18.0.6（保留网段），生产下载安全检查正确拦截，收图重试耗尽后保留了原结果地址。仅在临时测试 worker 进程内使用公共 DNS 返回的公网地址，移除该收图进程的 API 密钥，再由页面手动重试收图，两张恢复成功且生成请求数仍为2。未放宽正式代码的地址校验，未修改系统代理。

请求固定规格为1024×1024，但本次中转返回实际图片为1254×1254，系统保存原始返回图片，不进行隐式缩放。部署环境应保证 CDN 正常公网解析；出现假IP代理时需配置该域名的真实解析。

原始证据和截图：`output/api-live/evidence.json`、`real-results.png`、`real-upload.png`、`result-1.png`、`result-2.png`。测试资源为临时环境，不代表已上线。

## 首轮审查后修复

补充限长/限时错误JSON分类：明确额度不足、模型配置错误优先暂停通道，普通429仍退避。生成前本地预检密钥、参数和格式，未发起网络尝试不计数；补名称/编号搜索。页面改为请求规格、网络尝试和生成重试，展示排队/生成耗时并保留一位小数。

修复后完整后端回归 **851 passed / 112 skipped**（包含独立 PostgreSQL 用例），前端类型检查及 **137/137** 再次通过；真实浏览器交互回归再次PASS，没有新增生成请求。最终审查结论见独立报告。

正式构建1分2秒、demo构建44.06秒，均exit0。恢复Vite自动改写的既有组件类型声明后，类型检查再次exit0；`git diff --check`通过。专用API/worker/outbox/3011前端进程和临时三个容器均已清理，既有服务未停止。新代码、测试、运行示例与文档扫描未发现真实密钥字面量。

第二轮审查追加：单项等待重试提示不再将累计次数显示为“4/3”；worker入口屏蔽原始异常/数据库参数，固定错误码记录后由持久租约恢复，禁止盲目重发。追加异常脱敏测试及领域/执行/适配器回归 **44 passed**。前端再次类型检查并构建 production/demo，均exit0，完整日志在 `output/api-live/final-build.log`、`final-demo-build.log`。独立审查员另复跑137项前端测试及类型检查通过。

最终边界修复：urllib3 在响应读取阶段也可能抛 TLS 异常，适配器统一保守标记uncertain，不释放通道自动重发。新增成功响应读取TLS失败复现，API核心回归 **45 passed**；最终代码快照以独立审查报告中的编号为准。
