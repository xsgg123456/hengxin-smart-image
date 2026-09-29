# API 逐图尺寸与 PNG 成品独立审查

## 快照与范围

- 初始 candidateId：`b7b960af2189a18fc2e9908a6c366cc03d2c7c59191dc8ab51694eeefa4af1af`。
- 最终 candidateId：`aa75622a0f3752cf480c6958b3a3d82ea97c9c55fa6701f1d4612601875b633f`。reviewer 已运行只读 review-status，currentId 与该编号一致。
- 范围：本轮 git diff、新增 dimensions.py、0021 迁移、尺寸测试、PictureDimensions.vue、浏览器验收脚本。依据 Product-Spec.md:3、DEV-PLAN.md:3、Design-Brief.md:3 及 API-SIZE-20260929-VALIDATION.md。
- 审查期间主 Agent 修复 RealCreate.vue:18 的旧固定规格说明，补充创建页及历史窄屏验收，纠正浏览器列表 fixture；生成 components.d.ts 的无关声明变动已恢复。主 Agent 已重新 prepare，reviewer 复核了这些增量及最终快照；本 reviewer 不修代码、不登记批准、不提交。
- 下文 B = `hengxin-smart-image/backend/`，F = `hengxin-smart-image/frontend/`，P = `F/src/views/hengxin/api-image-edits/`。路径均相对仓库根目录。

## Stage 1 · Spec Compliance

结论：**PASS**。逐条核对如下，未发现 HIGH 问题，进入 Stage 2。

| Spec 条目 | 实现与证据 | 结论 |
| --- | --- | --- |
| 方图请求 1024；非方图在两边 100%～102% 枚举 16 倍数，仅无候选边扩界 | B/app/modules/api_image_edits/dimensions.py:12；测试 B/tests/test_api_image_dimensions.py:43 覆盖四示例、1×2、16×17、17×1600 | 完整实现 |
| 优先绝对比例差，再相对增幅和宽高 | dimensions.py:23 使用 Fraction 精确比较；测试同文件 test_api_image_dimensions.py:47 独立构造候选排序 | 完整实现 |
| 首次、重试、历史修改始终锚定最初 source_id | B/app/modules/api_image_edits/execution.py:30；test_api_image_dimensions.py:109、142 覆盖混合图及两种历史 revision 输入 | 完整实现 |
| 动态 size，其他模型参数及 prompt 不变 | execution.py:32、relay.py:86、relay.py:112；test_api_image_dimensions.py:200 断言实际载荷并拒绝其他参数变化，:123 断言 prompt | 完整实现 |
| 每次请求/实际返回/最终文件尺寸分别记录 | claims.py:107 写 request；outcomes.py:71 写解码后的 return；files.py:27 写最终 ApiFile；test_api_image_dimensions.py:109、171 验证三组尺寸及转换失败时返回证据 | 完整实现 |
| 0021 历史 nullable、不伪造旧请求 | B/migrations/versions/0021_api_image_dimensions.py:11；models.py:85；test_api_image_dimensions_migration.py:13 验证 SQLite/PG 历史 NULL、重复升级、证据保留 | 完整实现 |
| 解码后整图 Lanczos 调整，PNG，不裁切/补白/比例拦截 | dimensions.py:30；test_api_image_dimensions.py:60、77 实测极端比例及逐像素 Lanczos 对照 | 完整实现 |
| 同尺寸 PNG 不重采样，其他同尺寸格式转 PNG | dimensions.py:34、41；test_api_image_dimensions.py:68 让 resize 调用立即报错，PNG 返回同一对象 | 完整实现 |
| 文件大小/像素/解码保护及容量准入保留 | execution.py:76、95；dimensions.py:32、50 复用 B/app/modules/files/validation.py:41；test_api_image_dimensions.py:88 验证大小/像素拒绝 | 完整实现 |
| 转换/收图失败不再次调用模型；补收、发布幂等 | execution.py:82、91、119、152；test_api_image_dimensions.py:171 注入编码和对象存储失败，最终一次模型调用、同 staging id、一个版本 | 完整实现 |
| 冻结旧 staging 无新请求证据时保留旧字节 | execution.py:66、70、79、104；test_api_image_dimensions.py:214 验证旧 JPEG 字节与 staging id 不变，request 保持 NULL | 完整实现 |
| 历史完成图不重写；后续修改按新 PNG 策略 | execution.py:59 仅进入执行中的收图；versions.py:111 新修改清 staging；test_api_image_dimensions.py:142 验证旧 JPEG 仍为原字节、新结果原图尺寸 | 完整实现 |
| 预览、下载、ZIP、后续修改使用同一最终文件 | files.py:13、versions.py:40、97；test_api_image_dimensions.py:109 比较预览/下载/ZIP 的实际字节 | 完整实现 |
| API DTO 返回真实文件 width/height，历史未知兼容 | files.py:13；F/src/types/api-image-edits.ts:3；F/src/api/api-image-edits-validate.ts:7；F/tests/api-image-dimensions.test.ts:33、44 | 完整实现 |
| 当前与历史标题显示真实尺寸、未知及不一致提示，随版本切换 | P/PictureDimensions.vue:11；P/SourceComparison.vue:4；P/RealVersionDialog.vue:17；F/tests/api-image-dimensions.test.ts:114、134、154 执行真实 SFC 和选择事件 | 完整实现 |
| 窄屏换行、既有布局与图片/关闭交互不变 | SourceComparison.vue:24；RealVersionDialog.vue:111；scripts/api-size/browser.mjs:60、83；查看 matching-wide、mismatch-narrow、historical-mismatch、historical-narrow 截图 | 完整实现 |
| 创建页不再声称所有请求固定 1024 | P/RealCreate.vue:18；Product-Spec.md:15；create-specification.png 实际显示“按原图尺寸 · PNG” | 完整实现，审中修复已复核 |
| 仅增加受控 base_url 精确域名，保持 HTTPS/公网 IP pinning/禁重定向/不发密钥 | B/app/modules/api_image_edits/downloads.py:16、35、45；B/tests/test_api_image_relay.py:148 验证相似恶意域、私网、凭据、端口和 302 | 完整实现 |
| CLI 不变，不部署、不新增付费生成 | git diff 范围没有 CLI 业务代码；source comparison 引用仅在 API 目录；脚本 browser.mjs:21 拦截外域及业务请求；本轮真实图片仅离线 normalize | 符合本轮范围 |

部分实现：无。未实现：无。Spec 漂移：未发现新增无来源页面、接口、表或业务行为；仅新增已有 attempts 表四列及尺寸显示组件。

## Stage 2 · Code Quality

结论：**PASS**。无未解决的 HIGH / MEDIUM 问题。

- 结构/类型：PASS。尺寸算法与转换集中在 B/app/modules/api_image_edits/dimensions.py:12、30，UI 展示集中在 P/PictureDimensions.vue:11；本轮变更与新增代码文件均低于 300 行，无新增生产 `any`。错误处理保留 execution.py:82 的收图失败路径。
- 测试真实性：PASS。后端用真实 HTTP/SQLite fixture 走任务创建、版本修改、收图、下载与 ZIP；注入存储故障后重复收图验证冻结对象；前端编译真实 SFC，通过真实 onClick 切换所选版本，不仅检查源码字符串。证据：B/tests/test_api_image_dimensions.py:109、142、171、214，F/tests/api-image-dimensions.test.ts:83、154。
- 安全扫描：PASS。新增生产代码无硬编码密钥、eval、innerHTML、危险 SQL 拼接。F/tests/api-image-dimensions.test.ts:91 的 new Function 仅编译仓库固定 SFC 测试源码，不执行 API/用户输入；迁移测试的 schema 仅由 UUID 构造。下载精确域名新增未改变 TLS hostname 校验及请求头，证据 downloads.py:35、38、45。
- 视觉对比：PASS。实际查看主 Agent 隔离浏览器打开页面产生的 baseline-detail.png 与 current/history 宽窄弹窗截图；沿用蓝色按钮、白色圆角、次级灰蓝文字、现有警示标签。新增次级字号 12px（PictureDimensions.vue:23），标题保持 14px 与 8px gap（RealVersionDialog.vue:111），未另建视觉体系。390px 两类弹窗标题可滚动完整查看；创建页文案与规范一致。
- 权限/幂等回归：PASS。execution.py:74、92、122 均经 owned 校验；新记录不绕过容量或发布流程；已有权限、迟到 worker 栅栏、收图失败手动重试覆盖位于 B/tests/test_api_image_domain.py:41、83 与 test_api_image_execution.py:103、123、165，全后端回归已通过。

## 测试与编译原始输出

reviewer 独立执行尺寸全测试：

```text
.......................                                                  [100%]
23 passed, 2 warnings in 2.63s
```

reviewer 独立执行尺寸纯算法/归一化、relay、迁移子集：

```text
..............................................s                          [100%]
46 passed, 1 skipped, 5 deselected, 2 warnings in 1.60s
```

此处跳过 PG 是本次 reviewer 进程未设置隔离数据库变量，5 deselected 是先行排除集成场景；随后上面的 23 项完整尺寸测试已全部执行。主 Agent 双数据库迁移日志 output/api-size-migration.log:1：

```text
..                                                                       [100%]
2 passed in 0.61s
```

reviewer 独立前端全测试 `pnpm exec tsx --test --test-reporter=dot tests/*.test.ts` 退出 0，202 个通过点：

```text
....................
....................
....................
....................
....................
....................
....................
....................
....................
....................
..
```

读取主 Agent 全量后端最终原始日志 output/api-size-backend-full-init.log:51：

```text
1415 passed, 78 skipped, 15 warnings in 136.02s (0:02:16)
```

首次未用 Docker --init 导致旧进程管理测试的 PID1 环境问题，不作为最终通过记录；最终使用 --init 通过，未修改相应业务代码。78 项环境条件跳过不等于已验证这些环境，API/迁移专用 PG 专项另由主 Agent 转述 worker 记录 132 passed；后者未在本报告定稿前取得原始日志，因此不冒充 reviewer 独立执行证据。

读取最终编译原始日志 output/api-size-build-final.log:3、output/api-size-typecheck.log:3（命令退出 0）：

```text
> hengxin-smart-image-frontend@0.2.12 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 29.75s

> hengxin-smart-image-frontend@0.2.12 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

存在既有 pnpm 字段弃用、TestClient 弃用等 warning，不影响本轮执行结果。浏览器 result.json 为 6 项 checks、errors=[]；当前/历史宽窄、版本刷新、未知回退及创建规格均有真实页面截图。

## 证据边界

- 本轮未新增收费生成；旧实测图片的 11/11 离线转换只证明新后处理输出 PNG/原图尺寸，不证明新请求尺寸算法已在真实中转站整批生成成功。证据 output/api-size-normalized/verification.json，入口 dimensions.py:30。
- 本轮未部署；发布前须先执行迁移 0021，再更新读取 ApiAttempt 的服务。审查结论不代表生产已生效。
- 初始浏览器 fixture 的列表响应使用完整 task，曾使背景列表出现契约错误；最终 scripts/api-size/browser.mjs:35 已返回合法 ApiTaskSummary，:51 增加列表行就绪及无契约错误断言。reviewer 对照 F/src/api/api-image-edits-validate.ts:35 核验契约，并重新查看 baseline-detail.png，确认背景列表正常显示 1 套。6 项浏览器验收重跑成功。

## 最终结论

**Stage 1：PASS；Stage 2：PASS。** 结论仅绑定最终 candidateId `aa75622a0f3752cf480c6958b3a3d82ea97c9c55fa6701f1d4612601875b633f`。仅主 Agent 可据本报告运行 review-approve；初始候选已被后续修正替代，不得用旧编号登记。
