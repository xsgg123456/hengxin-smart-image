# 海外图片缓存与执行时限独立审查

日期：2026-10-30。审查者：独立 code-reviewer。依据 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`docs/OVERSEAS-IMAGE-CACHE-IMPLEMENTATION-20261030.md`、Product-Spec / DEV-PLAN 本轮条目；设计继承既有工作台及 Element Plus 查看器。

## 快照与范围

- candidateId：`198d3b3534d6378ac954b26d0f0ad486e5bcdacbed0694e18d512af6e73f63af`。主 Agent 已重新 review-prepare；reviewer 在定稿前运行 review-status，currentId 与此完全相同。
- 初始派发 `35bef635f14aecba3ea52925fb6f9d55ef5341763c51c055e2a46550a0bc1e87` 未批准。首次实查已为 `4b9e99afecd9e67343897c762939e1e09343d1d06dede387081112ef74730fa4`，随后主 Agent 明确告知追加删除受理保护、安装测试依赖闭包与旧预览测试修订。以下审查包含这些差异，不将旧结论套到新版本。
- 范围：10 个海外后端交付/配置源码，图片缓存/缩略图/时限及旧预览回归测试；前端缓存、查看器、预取、共同图片组件、账号生命周期及测试；版本 0.2.55、生成组件声明、海外 Compose 默认值；`scripts/image-cache/` 集成验证及 `scripts/release/image-cache-*.py`、发布测试。
- `AGENTS.md` 的已有用户修改不属于本次实现，保留未提交。本报告不修改实现、不提交、不登记批准、不写 `.needs-review`。

路径简写：`B` = `hengxin-smart-image/backend/`，`F` = `hengxin-smart-image/frontend/`，`R` = `scripts/release/`。下列位置均为本仓库文件及行号。

## Stage 1：Spec Compliance

状态：**PASS（本候选源码与发布工具范围）**。已逐项审查实现，无未解决 HIGH；发布后的真实验收单独列出，不视为已经完成。

| 合同条目 | 实现与验证证据 | 代码审查结论 |
| --- | --- | --- |
| 原图预览、缩放、下载、标注使用原字节 | `B/app/overseas/image_delivery.py:10` 校验长度/SHA256并返回原字节；`F/src/views/overseas/studio/studio-images.ts:15` 标注读取共享原图；`B/tests/test_overseas_thumbnail_limits.py:36` 覆盖PNG/JPEG/WebP。浏览器下载 SHA256 与原件均为 `c1834f118cd728a0aa2161126711bd971e39e126765fc5de98c42f861006ede4`，naturalWidth/Height=1600×1000。 | 完整实现 |
| 缩略图是独立表示，不能冒充原图 | `B/app/overseas/image_delivery.py:51` 独立 thumbnail ETag及WebP；`F/src/views/overseas/studio/studio-images.ts:7` 原图URL与thumbnail URL分开；`StudioAssetImage.vue:2` 列表只用缩略图。`scripts/image-cache/browser.mjs:29` 验证未点击无原件GET。 | 完整实现 |
| 当前会话整批渐进预取 | `F/src/views/overseas/studio/use-image-prefetch.ts:6` 聚合成品、附件、引用、素材和草稿；`OverseasStudio.vue:81` 以actor/task/activeSession绑定，只取当前会话数据。`F/tests/overseas-image-viewer.test.ts:36` 覆盖切会话和文档排除。 | 完整实现 |
| 最多两个原件请求、点击优先、共用在途 | `F/src/api/overseas/image-cache.ts:72` 双槽队列，`:84` 提升未开始请求优先级并复用同URL Job；`F/tests/overseas-image-cache.test.ts:15`、`:33` 及浏览器6消费者同GET/预取点击共用GET验证。 | 完整实现 |
| 失败重试、会话切换取消无用队列 | `F/src/api/overseas/image-cache.ts:31` abort并拒绝旧Job，`:114` 取消不再需要的预取；`use-image-viewer.ts:30` 切图取消旧读取，`:49` 提供retry；`scripts/image-cache/cache-scenarios.mjs:50`、`:90` 验证失败后重试与未开始旧请求不发送。 | 完整实现 |
| 页面缓存按账号/业务/URL/服务器版本复用 | 海外专属单例 `F/src/api/overseas/image-cache.ts:130`；`OverseasPortal.vue:36` 绑定member+identitySessionId；缓存条目含ETag，`:54` HEAD验证后复用或取新版本。版本变更测试 `F/tests/overseas-image-cache.test.ts:72`。 | 完整实现 |
| 重复打开先验证权限，未改变不再传原件；刷新利用私有HTTP缓存 | `image-cache.ts:44` credentials/include、no-cache、条件HEAD；`:54` 无ETag不盲用。`scripts/image-cache/browser.mjs:78` 实际Chromium刷新后三个原件GET全部304、响应体0字节；未使用Playwright route。 | 完整实现 |
| private/no-cache、ETag、Vary及304前鉴权/存在检查 | `B/app/overseas/image_delivery.py:38` 对象stat在304之前；`:56` private/no-cache + Vary Cookie/Authorization；三个调用方先鉴权/读取记录再交付：`studio/files.py:128`、`materials/files.py:65`、`archives/service.py:114`。`B/tests/test_overseas_image_cache.py:92` 覆盖4种来源×撤权/退出/删除记录/删除对象，均不能304。 | 完整实现 |
| 已受理删除也失效，并保留其它会话/归档引用 | `B/app/overseas/studio/files.py:100`、`:114` 读取TaskDeletion/ConversationDeletion并处理保留图片；`materials/files.py:65` 拒绝所属任务待删。`B/tests/test_overseas_image_cache.py:148`、`:166` 使用真实DELETE接受后、对象尚存在窗口；`:186`、`:200` 覆盖共享材料、归档、清理前/后保留图片与最后消费者删除。最终扩展专项123通过，覆盖这些新增用例。 | 完整实现 |
| 401/403/404清对应页面缓存 | `F/src/api/overseas/image-cache.ts:49`、`studio-images.ts:11`、`StudioAssetImage.vue:44` 分别覆盖读取、缩略图预检、下载预检失效；缓存测试`:72`及浏览器三种状态验证条目清零与恢复后再取。 | 完整实现 |
| 退出/换账号清空、取消、旧响应不回填 | `image-cache.ts:35` epoch递增/撤销URL/取消Job，`:43` 迟到响应校验；`OverseasPortal.vue:165` 卸载清身份；`use-image-viewer.ts:47` 订阅清理关闭显示。`F/tests/overseas-image-cache.test.ts:50` 故意使用不遵守Abort的迟到fetch验证。 | 完整实现 |
| 128MiB/40张LRU、有限解码及超大图策略 | `image-cache.ts:15` 预算，`:24` 按LRU淘汰且保护pin/校验在途，`:94` lease释放；`use-image-viewer.ts:30` 只保留当前图URL；`image-cache-http.ts:3` 32MiB预取阈值及流累计限制。测试`:60`、`:96`、`:119` 覆盖大小/数量/缺长度/HEAD在途不误淘汰。 | 完整实现 |
| 缩略图类型、像素、字节、并发、衍生缓存有界 | `B/app/overseas/thumbnails.py:9` 32MiB输入/2400万像素/384边长/1MiB输出/32MiB及256项LRU/2转换槽；`:43` 异常不写原件并finally释放。测试`test_overseas_thumbnail_limits.py:45`、`:57`、`:69`、`:88`、`:114`、`:139` 覆盖透明、EXIF、资源限制、损坏/动态、429/等候和淘汰。 | 完整实现 |
| 缩略图429恢复而非永久占位 | `F/src/views/overseas/studio/StudioAssetImage.vue:28` 原件HEAD预检、最多4次错峰重试，卸载清定时器；`scripts/image-cache/browser.mjs:26` 实际HTTP首次429后200并恢复。 | 完整实现 |
| 共同预览组件、归档权限和非图片流式 | 工作台共同组件`StudioAssetImage.vue:1`；归档`B/app/overseas/archives/service.py:114` 不重建已删记录，归档独立原件仍可读；`attachment_delivery.py:8` 图片走条件交付，其余`:26` 仍为OwnedStreamResponse。四来源后端用例和浏览器附件/材料query链路覆盖。 | 完整实现 |
| 海外7200/7800、国内不变、旧任务冻结不重放 | `B/app/overseas/config.py:24`；`hengxin-smart-image/infra/compose.overseas.yaml:30`；`B/tests/test_overseas_image_cache_settings.py:13` 国内仍3600/4200、显式配置仍优先；`:27` 同幂等旧轮次3600、新轮次7200、管理覆盖180。 | 完整实现 |
| 版本0.2.55、审后提交/打包审计、真实生产API增量基线 | `F/package.json:3`；`R/image-cache-package.py:18` 要求已提交且批准快照，文件从commit读取并核对，绑定实测API镜像及10文件基线哈希，隐私检查；`R/image-cache-deploy.py:32` 核对当前镜像和旧源码后FROM当前镜像只COPY10文件。 | 发布工具完整实现；提交/制品尚待主Agent执行 |
| 保持账号/授权/Skill、完整Compose链、国内/身份不重启 | `R/image-cache-runtime.py:25` 拓扑包括国内API/worker及账号服务PID；`image-cache-deploy.py:41` 复用完整Compose并比较除image/两环境值外完全相同，`:149` 仅api且no-deps/no-build；复用`R/account-runtime.py:92`、`:113` 核对原环境、mount及command。无迁移、无凭据/Skill数据写入。 | 发布保护完整实现；实际保持情况待发布核验 |
| 安装测试先行、停止接纳/排空再重启、保留原生目录命令 | `R/image-cache-deploy.py:80` 隔离实际派生镜像测试并绑定manifest/image，`:99` 必须有通过凭据；复用`R/account-worker.py:54` cancel_consumer并连续两次核验Celery和DB空闲后停止，忙时恢复接纳。只加EnvironmentFile，原unit文件摘要与cwd保留，`:127` 核验实际环境。 | 发布保护完整实现；生产安装/排空未冒充已完成 |
| 健康/配置/正式页面验收、可回退制品且不恢复DB | `R/image-cache-runtime.py:69` 有界健康等待；`image-cache-deploy.py:160` 验证API/worker/Compose链；`:69` 留恢复指引、旧镜像及配置证据；`image-cache-frontend.py:24` 备份/哈希/原子入口切换，`:70` 显式回退保留两代哈希资产。 | 工具完整实现；生产健康、图片权限与正式页面仍待发布后验收 |

### UI、引导真实性与漂移

`F/src/views/overseas/studio/StudioAssetImage.vue:6` 继续使用 ElImageViewer 的计数、前后切换、缩放/旋转、关闭与下载；新增“正在加载原图”“重新加载”“下载原文件”均有对应状态/处理函数，不是死引导。原工作台尺寸样式文件未修改；仅增加错误状态样式。查看器原图加载失败时不会展示旧缓存冒充成功。

已逐图查看 `output/studio-images-20261016/production-viewer.png`、`output/workbench-production-studio.png` 与本轮 `output/image-cache/01-thumbnails.png`、`02-original-preview.png`、`04-denied.png`：查看器原有工具栏、进度与关闭位置保持，拒绝状态有可见重试。本轮fixture外框刻意独立，不能证明完整正式工作台布局或生产链路；正式页面验收保留到发布后。证据生成代码：`scripts/image-cache/browser.mjs:20`、`:41`、`:93`。

没有新增产品页面/表/迁移/Redis；新增query参数、缓存模块及发布脚本均在合同范围。`scripts/image-cache/fixture.vue:1` 的测试按钮仅由独立fixture入口加载，未接正式产品路由。材料新上传图片MIME验证是接通合同既有图片预览，坏图仍保持私有附件下载（`B/app/overseas/materials/files.py:19`；`test_overseas_image_cache.py:137`）。

## Stage 2：Code Quality

状态：**PASS（同一candidateId）**。Stage 1通过；质量、安全、测试真实性和可比视觉证据未发现新增阻断项。

- 结构与类型：本轮新增/修改源码均未超过300行；TypeScript新模块无显式any。缓存HTTP读取、调度/lease、viewer生命周期、prefetch分别独立，职责可追踪（`F/src/api/overseas/image-cache-http.ts:8`、`image-cache.ts:13`、`use-image-viewer.ts:7`、`use-image-prefetch.ts:6`）。释放/取消/异常路径有finally及代次检查。
- 测试真实性：后端关键用例通过真实隔离登录与路由依赖检查，而非直接伪造304；删除用例实际提交DELETE并确认原对象尚未清理（`B/tests/test_overseas_image_cache.py:148`、`:166`）。浏览器禁用route拦截，真实HTTP服务器记录304/0body及下载哈希（`scripts/image-cache/browser.mjs:1`、`:59`、`:78`）。缓存异常、权限、容量、取消和组件重试均有可达前提。
- 安全扫描：对本次变更的Python/TS/Vue/JS/MJS执行硬编码secret、eval、innerHTML/dangerouslySetInnerHTML、VITE敏感前缀扫描，无新增匹配。新增固定主机路径仅用于已授权发布保护；动态package路径要求在source内且非symlink（`R/image-cache-runtime.py:46`），客户端请求禁止重定向并携带现有身份（`image-cache.ts:44`）。
- 发布质量：安装证据绑定镜像和manifest（`R/image-cache-deploy.py:15`），scope/基线变化拒绝切换，静态回退拒绝覆盖之后发生的未知变更（`image-cache-frontend.py:70`）。reviewer独立执行4个发布测试及4个发布脚本py_compile通过。实际Linux安装验证仍是代码门禁后的必要步骤。
- 无未解决 HIGH/MEDIUM 发现。上述结论只针对本次代码范围，不等价于全仓库无缺陷，也不把历史Windows平台不适用用例算成通过。

## 编译与测试原始输出

前端 `output/image-cache-frontend-typecheck.log`：

```text
> hengxin-smart-image-frontend@0.2.55 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

前端 `output/image-cache-frontend-tests.log`：

```text
ℹ tests 424
ℹ suites 0
ℹ pass 424
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
```

最终构建 `output/image-cache/frontend-build-final.log`：

```text
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4700 modules transformed.
✓ built in 37.73s
```

reviewer独立发布测试：

```text
test_frontend_rollback_retains_both_asset_generations (test_image_cache_release.ReleaseTests.test_frontend_rollback_retains_both_asset_generations) ... ok
test_manifest_cannot_escape_release (test_image_cache_release.ReleaseTests.test_manifest_cannot_escape_release) ... ok
test_scope_only_overseas_and_no_dependency_recreation (test_image_cache_release.ReleaseTests.test_scope_only_overseas_and_no_dependency_recreation) ... ok
test_worker_switch_refuses_changed_identity_before_drain (test_image_cache_release.ReleaseTests.test_worker_switch_refuses_changed_identity_before_drain) ... ok
Ran 4 tests in 0.059s
OK
```

`python -m py_compile scripts/release/image-cache-runtime.py scripts/release/image-cache-deploy.py scripts/release/image-cache-package.py scripts/release/image-cache-frontend.py`：exit_code=0，原始stdout为空。

后端首次完整Windows回归 `output/backend-image-cache-regression.txt` 的真实结果：

```text
14 failed, 2494 passed, 405 skipped, 6 warnings in 500.13s (0:08:20)
```

其中6项旧预览测试使用过时no-store断言，或更换材料字节但未更新checksum；已核对`B/tests/test_studio_image_preview.py:49`同步真实校验和及`:69`更新private/no-cache、ETag、Vary，最终扩展专项覆盖并通过。另8项涉及POSIX safe open或Windows符号链接权限限制；`output/backend-image-cache-platform-check.txt`保留原始异常，实际Linux安装命令已包含相关3个既有测试文件（`R/image-cache-deploy.py:89`），未运行前不能宣称全量回归通过。405项skip同样不计通过。

最终后端扩展专项 `output/backend-image-cache-targeted-final.txt`：

```text
........................................................................ [ 58%]
.....................................s..............                     [100%]
123 passed, 1 skipped, 2 warnings in 67.72s (0:01:07)
```

1项平台跳过不计通过；图片缓存新增用例、旧预览及删除相关适用用例已通过。最终完整回归 `output/backend-image-cache-regression-final.txt` 在审查定稿时仍在执行，必须检查结果并处理任何新失败后再交付；本报告没有把未完成运行记成PASS。浏览器 `output/image-cache/result.json` / `browser-final.log`：18项通过，errors=[]；测试范围为隔离HTTP+生产组件+Chromium，不替代生产后端和正式页面验收。

## 发布后必须补齐的验收

实际包隐私与哈希审计、派生镜像安装测试（含Windows不适用项的Linux补验）、切换当时排空证据、生产API/worker实际7200/7800、国内/身份/账号服务保持、生产图片鉴权/304/原件哈希、正式页面预览下载与视觉、回退证据。合同第4步和发布脚本明确安排这些检查；本审查报告不宣称它们已发生。
