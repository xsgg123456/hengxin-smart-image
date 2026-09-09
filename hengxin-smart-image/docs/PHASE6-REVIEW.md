# Phase 6 独立审查（第三轮最终复审）

日期：2026-09-09。使用 `.agents/skills/code-review/SKILL.md`；fresh reviewer 独立读取 AGENTS、Product-Spec、DEV-PLAN、Design-Brief、PHASE6-PLAN、API-CONTRACT、PHASE6-VALIDATION、旧报告、当前 diff 和新增实现。

**Stage 1 PASS；Stage 2 PASS。剩余 HIGH 0、MEDIUM 0。前两轮问题均已闭环。** 结论限 Phase 6 技术范围，用户验收尚待进行。

下文代码路径相对 `hengxin-smart-image/`，上游文档、`scripts/` 与 `output/` 相对仓库根目录。审查者只覆盖本报告，不改代码、不提交、不派生 Agent，不对用户开发数据库执行写入测试。

## Stage 1：Spec Compliance — PASS

依据 Product-Spec.md:100（REQ-003）、:135（REQ-007）、:189（第7节）、:343（第13节），按 DEV-PLAN.md:230 的 Phase 6 交付边界逐项核实。

| 需求 | 结论及证据 |
|---|---|
| 统一稳定用户及归属 | 完整实现。`backend/app/resource_models.py:16,29,46` 定义用户、文件 owner 外键和删除 actor 外键；`modules/files/service.py:14` 从服务端 user 赋 owner。`tests/test_files.py:16` 三格式验证尺寸、哈希、原字节、owner。 |
| 开发身份默认关闭、客户端不可指定 | 完整实现。`core/config.py:14` 默认 false；`modules/auth/dependencies.py:11` 不读取请求身份；`tests/test_auth.py:19,25,42` 验证默认值、伪造头和匿名拒绝；隔离浏览器 `scripts/phase6/files-flow.js:7` 验证 URL 假角色不改变 operator。 |
| production 禁止开发身份 | 完整实现。`core/config.py:34` 启动配置校验；`dependencies.py:14,23` 双重拒绝；`tests/test_auth.py:19,62` 启动校验和历史身份路径通过。 |
| 开发账号不混真实成员，不重置权限 | 完整实现。`dev_identity.py:14` conflict do nothing、:19 拒绝真实来源冲突；`tests/test_auth.py:87` 验证停用/角色不会被种子覆盖。 |
| 四角色共享，停用/待授权/匿名拒绝 | 完整实现本阶段基础策略。`permissions.py:5` 四角色共享、仅超管管理系统、主管/超管全员统计；`dependencies.py:19` 每次读当前账号；`tests/test_auth.py:52,72` 和 `tests/test_files.py:40` 逐角色跨 owner 读、停用后读/上传拒绝通过。 |
| 删除审计和历史对象保留 | 完整实现基础服务。`deletions.py:9` 实际操作者及逻辑删除，不删字节；`tests/test_auth.py:109` actor 不等于 owner、顺序重复只一条审计。调用方事务/资源锁明确由未来业务负责（`deletions.py:1`）。 |
| 三类入口的素材及表单 | 本阶段匹配。`frontend/src/views/hengxin/components/CreateTask.vue:7,20,25` 保留模板、三类型、名称必填、SKU可选和文字意见；`scripts/phase6/files-flow.js:12,57` 三入口真实上传，失败及重试均保留输入。 |
| JPG/PNG/WebP、非空和可读 | 完整实现。`validation.py:40` 读取实际字节、verify 后重新 load 每帧、MIME一致；`tests/test_files.py:16,56` 三格式/空/伪造/截断/不支持格式通过。 |
| 单张10 MiB、安全解码 | 完整实现。`validation.py:11,41,57` 文件上限、像素与帧限制；`tests/test_files.py:72` 准确上限受理、解码安全拒绝。流入口修复见下文。 |
| 每组20张 | 当前分工匹配。`use-image-upload.ts:89` 先同步登记后异步上传；`scripts/phase6/files-flow.js:66` 输入21张、仅20张已接收。`docs/API-CONTRACT.md:123` 明确业务组服务端限制属于 Phase 7/8。 |
| 失败重试、移除、排序 | 完整实现当前素材状态。`use-image-upload.ts:65,101,111,119` 保留 File、重试、移除及排序；`ImageUpload.vue:29` 操作入口；浏览器503故障后真实重试通过。 |
| MinIO私有、随机键、原字节 | 完整实现。`storage/minio_store.py:20,35` 无公共策略才读写；`service.py:13` UUID键；`tests/test_files.py:104` 不覆盖；`infra/verify_phase6.py:106` 实际PG元数据与原字节比较、匿名MinIO403，已读取最终PASS日志。 |
| 上传失败不可形成可用记录 | 完整实现。`service.py:21,33,44` durable staging、失败补偿、ready可见；最终commit不确定不删对象。`tests/test_file_failures.py:18` finalize失败保留不可见staging；`tests/test_files.py:81` 存储故障恢复；真实MinIO停机/恢复日志PASS。 |
| 稳定预览与下载、刷新重启 | 完整实现。`router.py:23,39,44` 稳定fileId及每次鉴权流式内容，:55 文件名编码、no-store/nosniff；`streaming.py:10` finally释放连接。`verify_phase6.py:129` API/PG/MinIO重启后原字节保留；浏览器刷新按fileId读回。 |
| HTTP启动取消全量workspace依赖 | 完整实现。`frontend/src/main.ts:73` 仅mock加载workspace；`CreateTask.vue:4,20,38` 错误重试不禁用上传、生成仍禁用；`scripts/phase6/files-flow.js:5,73` 请求计数为0。 |
| 上传超时、下载及文案 | 完整实现。`api/hengxin/http.ts:10,70` 上传60秒；`ImageUpload.vue:15,29,56` 真实下载与“移除仅取消选择”；mock示例仅mock显示；501有错误提示，无伪造成功。 |
| UI一致性 | 匹配既有先例。实际查看真实上传、1024宽度截图及邻居模板页截图，详见Stage 2。 |
| Spec漂移 | 未发现。用户/文件/删除记录、身份与文件API均属于 `DEV-PLAN.md:233`、`docs/PHASE6-PLAN.md:5` 和 `API-CONTRACT.md:120` 的范围。 |

部分实现/未实现的后续项明确排除本次完成声明：REQ-003任务幂等与冻结为Phase8；第7节真实钉钉、模板停用/删除/引用清理及第13节角色分配、统计、监控、Skill与系统管理接口按DEV-PLAN后续阶段接入。现有501不列当前缺陷，也不把基础授权测试算作这些业务验收。服务端fileId留存不等于前端草稿恢复。

### 第一轮 HIGH 闭环：匿名上传先写完整临时体

旧独立复现值保留：

```text
{'status': 401, 'multipart_file_bytes_written_before_401': 12582912}
```

当前 `backend/app/modules/files/router.py:29` 先执行身份依赖，再手动解析Request；`multipart.py:23,34` 同时校验声明长度和累计实收字节，10 MiB+64 KiB封装上限；文件自身由 `validation.py:41` 严格10 MiB。仅一个file、零额外字段，异常或返回后关闭表单。

本轮独立执行 `tests/test_upload_ingress.py:13,32,63` 通过：匿名/声明超限 UploadFile.write 为0；无Content-Length和伪造小长度发送无限64KiB分块，断言提前停止且所有spool关闭；多文件、额外字段和坏multipart拒绝。实际读取锁定环境 `backend/.venv/Lib/site-packages/starlette/formparsers.py:291` 的 BaseException 清理分支。**HIGH 已关闭。**

## Stage 2：Code Quality — PASS

### 第二轮 MEDIUM 闭环：合法JPEG尾随字节下载误拒

旧独立复现值保留：

```text
{'backend_accepts': 'image/jpeg', 'bytes': 632, 'last_2_hex': 'd900', 'frontend_requires': 'ffd9'}
```

`frontend/src/views/hengxin/download-helpers.ts:21` 当前按EOI存在识别JPEG，`readImage:6` 返回完整data，不裁剪尾部；`frontend/tests/download.test.ts:79` 使用真实Pillow fixture比较读回字节。`scripts/phase6/files-flow.js:44` 实际上传并保存浏览器下载；`infra/verify_phase6.py:178` 比较文件原字节。

本轮实际读取38项前端最终测试日志，独立计算fixture及下载文件SHA256，两者均为：

```text
2F00D804D22C8A2183A17E06A2263C0F40DA0D8BDBC23E0B5ABC3891C860E84B
```

**MEDIUM 已关闭。** EOI检查仅为前端格式识别；可信上传的完整解码仍由后端负责，不把该签名检查声明为完整JPEG验证器。

| 维度 | 结论与证据 |
|---|---|
| 命名/职责/大小 | 匹配。本轮实际计数：新增后端模块0–70行，迁移60行、verify_phase6.py196行、files-flow.js76行、ImageUpload.vue85行。身份、multipart、图片验证、存储和响应生命周期各自独立（各文件:1）。 |
| 类型与异常 | 前端本轮未引入any；`ImageUpload.vue:57` Picture/number、`resource_models.py:22` Mapped、`validation.py:17` dataclass字段明确。内部Python接口仍有动态参数（`service.py:12`），未发现由其引发的当前错误。业务异常使用稳定HTTP状态；资源finally释放有断连测试（`test_file_failures.py:51`）。 |
| 安全扫描 | 实际rg扫描新增模块、storage、models、ImageUpload、download-helpers、验证脚本：eval/innerHTML/dangerouslySetInnerHTML/前端密钥变量/API_KEY/硬编码用户绝对路径/any无命中。`minio_store.py:15` 密钥来自服务端配置；`verify_phase6.py:31` 为随机隔离凭据。 |
| 注入与路径 | `service.py:16` 对象键由服务器UUID构造；`validation.py:27` 清理路径与文件名；`router.py:55` 编码下载名；`dependencies.py:20` ORM查询。集成脚本SQL只使用UUID验证后的fileId及受控测试值（`verify_phase6.py:108,115`），不接用户SQL。 |
| 测试真实性 | `tests/files_helpers.py:61` 明确SQLite/MemoryStore单测；真实PG/MinIO另有隔离脚本与匿名访问/重启证据。入口测试断言实际写入和资源关闭，不仅HTTP码。浏览器503是显式注入，重试放行真实POST。finalize故障仅模拟提交前失败，不冒称提交成功后响应丢失已实测。 |
| 视觉实际对比 | 已实际view_image打开 `output/playwright/phase6-real-upload.png`、`phase6-narrow-upload.png`、`phase6-review-neighbor-template.png`。白卡、灰底、蓝色操作、标题层级、卡片圆角和文本按钮与邻居一致。数值来自 `prototype.css:2,7,8` 页面18px/8px/32px、网格22px、卡片23px；`ImageUpload.vue:78` 延续素材布局。1024宽下载/移除不重叠，脚本:72另断言无横向溢出。此次直接查看已渲染截图，没有宣称重新打开实时浏览器。 |
| 验证边界 | 未进行用户真实开发库写入测试；未宣称生产容量、100人并发、钉钉容器或后续业务权限已经验收。`DEV-PLAN.md:244` 的本阶段基础权限及上传下载已具证据。 |

## 编译与测试原始证据

本轮审查者独立运行后端 `uv run pytest -q`：

```text
................................................ssss....                 [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
52 passed, 4 skipped, 2 warnings in 4.37s
```

4 skipped 因本轮未设置TEST_DATABASE_URL，不算通过。独立 `uv run python -m compileall -q app migrations`：**exit 0，原始stdout/stderr为空**。

实际读取最终 `output/playwright/phase6-integration.log`，关键原始输出如下（完整输出含上述两类弃用警告）：

```text
PASS explicit development identity
PASS private object, original bytes, metadata and server ownership
PASS empty/corrupt/truncated/oversized input leaves no file rows
PASS file persists across API/PG/MinIO restart
PASS second server-owned identity
PASS anonymous denied after disabling development identity
PASS restore isolated operator
PASS storage recovery
PASS cross-user sharing, disabled/pending/anonymous denial, storage failure retry
56 passed, 2 warnings in 3.08s
PASS isolated frontend
"PHASE6 BROWSER PASS: real upload/preview/download, failure retry preserves input, reload persistence, three modes, 20-image limit, no fake identity, pageerror=0"
PHASE6 INTEGRATION PASS (isolated volumes)
```

实际读取 `phase6-queue-regression.log`：

```text
PASS PG/Redis/MinIO ready
PASS repeat migration
PASS accepted job survives API/outbox restart without Worker
PASS real Celery execution
PASS duplicate messages preserve single completion
PASS Redis outage durable recovery
PASS Worker received delayed job
PASS Worker crash rollback and recovery
56 passed, 2 warnings in 11.27s
PASS only three isolated test volumes mounted
PHASE5 INTEGRATION PASS
```

实际读取最终 `phase6-frontend-test.log`、`phase6-frontend-build.log`：

```text
ℹ tests 38
ℹ suites 0
ℹ pass 38
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1640.1206
> hengxin-smart-image-frontend@0.0.0 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 44.16s
```

原始构建日志另有npm项目配置弃用提示，未产生类型或构建失败。集成与前端完整执行exit 0来源为 `docs/PHASE6-VALIDATION.md:8` 的执行记录；本轮重新读取原始完成输出，未重复运行整套容器/浏览器测试。审查结论：两阶段PASS，交主Agent进入用户验收。
