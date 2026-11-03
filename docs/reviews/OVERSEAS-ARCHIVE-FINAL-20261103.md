# 成品库字段与图片缓存终审

日期：2026-11-03。独立 fresh code-reviewer，使用 `.agents/skills/code-review/SKILL.md`，遵守 `docs/HARNESS-REVIEW.md`。仅审查及写报告，未修代码、未提交、未部署、未登记批准。

- candidateId：`99cf8747a7f5599cda2c3e70c3eaeabffe57206fabfcd9e24d1597a185125a18`
- Stage 1：**PASS**
- Stage 2：**PASS**
- 未解决 HIGH：0；未解决 MEDIUM：0。
- 本次开始及收尾运行 `review-status`，currentId 均为上述候选，审查过程中未发现代码快照变化。主 Agent 应仅为这个 candidateId 登记两阶段 PASS，不能批准旧候选，也不向 `.needs-review` 写 clean。
- PASS 对象是本地实现与发布工具；生产部署、正式 HTTPS 安装后校验及既有归档只读验收尚待执行，不表示已上线交付。

## 范围与依据

已完整读取实施合同 `docs/OVERSEAS-ARCHIVE-PENDING-20261103.md`，核对 `Product-Spec.md:1398`、`DEV-PLAN.md:1616`，读取 Design Brief 并依据 `Design-Brief.md:86`、`:212` 的既有 Art/Element 与归档视觉基准。审查范围为当前全部 diff 和未跟踪代码：

1. 前端 package 版本、archives API、共享 image-cache、归档字段/页面/详情/图片/查看器、Studio 归档入口及三个归档 composable。
2. 六份修改的前端测试、新增字段浏览器脚本、`scripts/archive-cache/` 五个 fixture/浏览器文件。
3. `scripts/release/archive-runtime.py`、`archive-package.py`、`archive-deploy.py`、两个发布测试文件，以及本轮 Spec/计划/变更/验证文档。

下文 `F/` 表示 `hengxin-smart-image/frontend/`，`B/` 表示 `hengxin-smart-image/backend/`。引用行号均为本次读取版本。R1 报告 `docs/reviews/OVERSEAS-ARCHIVE-20261103.md` 保留旧候选 Stage 2 FAIL；本次重新检查当前源码、测试前提、截图与原始结果，不将旧结论直接覆盖到新候选。

## Stage 1：逐条需求符合性

| 合同条目 | 结论及实现位置 | 行为证据 |
| --- | --- | --- |
| 归档弹窗和详情共用 SKU、目标平台、品牌、任务名称、品名、语言，同序同名同样式 | 完整实现。`F/src/views/overseas/OverseasArchiveFields.vue:10` 至 `:15`；`studio/StudioArchiveFields.vue:2` 与 `OverseasArchiveDetail.vue:7` 直接复用。 | `F/tests/studio-process-component.test.ts` 同一真实 SFC 的标签、值及两入口相等断言；正式 dist 浏览器日志 `output/archive-fields-browser.log:1` PASS。 |
| 整套 SKU 展示，单 SKU 自动归属，历史多 SKU 另选本批图片归属 | 完整实现。`OverseasArchiveFields.vue:24` 汇总 SKU；`studio/OverseasStudio.vue:44` 多 SKU 独立选择及禁用确认；`:114` 自动选唯一 SKU、剔除已失效选择。 | lifecycle 测试覆盖单/多 SKU、修改 SKU 后清选择；`F/tests/archive-fields.browser.mjs:112` 附近实际点击归档并检查 SKU、pictureIds。 |
| 来源会话与所选图片数量保留 | 完整实现。`studio/OverseasStudio.vue:44` 说明区显示会话与选中数，继续调用原归档行为。 | 1366/390 正式 dist 截图及浏览器实际归档请求。 |
| 独立快照、历史语言缺失不猜测、中文语言名与空值一致 | 完整实现。`OverseasArchiveFields.vue:11` 至 `:15`；详情只用归档记录。既有 `B/app/overseas/archives/snapshot.py:12` 仅初始化时捕获元数据，本轮未修改后端。 | SFC 覆盖四语言、空语言/空任务名；390-multi 明确“未设置”。独立来源删除场景保留归档。 |
| 封面和详情小图走独立缩略接口，保留等比、失败提示及重试 | 完整实现。`F/src/views/overseas/use-archive-image.ts:6` 默认缩略模式、`:23` 请求 true；`F/src/api/overseas/archives.ts:75` 拼接 thumbnail query；`OverseasArchivePicture.vue:2` contain、`:6` 重试。 | `scripts/archive-cache/browser.mjs:27` 起实际 HTTP：封面首次失败重试，240×150 缩略图；详情六张缩略图。 |
| 列表不预取每套原图 | 完整实现。预取只接入 `OverseasArchiveDetail.vue:50` 与 `OverseasArchiveViewer.vue:23`，封面沿用缩略 hook。 | `output/archive-cache/result.json:5` 列表原件 GET=0。 |
| 查看器接现有原图缓存，预览、缩放和下载保持原件字节、格式、尺寸 | 完整实现。`use-archive-image.ts:25` acquire、`:31` MIME/大小校验；`use-archive-download.ts:12` acquire、`:15` 校验、`:19` saveBlob，无转码。 | HTTP 浏览器 naturalWidth/Height=1600×1000，滚轮及切回有效；下载 SHA256 实际与预期均 `a17a7b22637a636c8f0ae43697ba73c432435419962579556310c6bdc76b9f77`。 |
| 详情下载不依赖缩略完成 | 完整实现。`OverseasArchivePicture.vue:8` 独立按钮，`use-archive-download.ts:8` 独立状态与异常。 | `scripts/archive-cache/browser.mjs:57` 缩略图延迟3500ms，下载完成时缩略尚未出现。 |
| 当前套图渐进预取，最多2并发、点击优先、在途去重 | 完整实现。`F/src/api/overseas/image-cache.ts:79` active<2；`:81` 优先级出队；`:93` 同 URL 合并并晋升前台。 | 真实 HTTP 六原件最大并发2；共享缓存单测/工作台18项实际 HTTP 证据覆盖去重与点击优先。 |
| 128 MiB/40张、淘汰、超大图按需 | 完整实现。`image-cache.ts:15` 预算、`:26` 淘汰无租约项、`:139` 过滤大预取；既有 `image-cache-http.ts:3`/`:17` 有32MiB预取及流读取保护。 | 缓存测试覆盖数量/字节淘汰、未知长度超限、按需大图释放；当前正在使用的租约可暂超预算，释放后回收。 |
| detail/viewer/工作台多个预取 owner 互不误取消 | 完整实现。`image-cache.ts:18` owner表、`:49` 合并需要、`:122` 仅取消无人使用项、`:144` 独立owner；`use-archive-prefetch.ts:6` 每实例独立建立。 | 新测试实际挂三个 owner、共享两并发，销毁详情保留工作台与查看器，最后 owner 离开才取消。 |
| 关闭、离开及筛选取消无用队列，保留已完成缓存 | 完整实现。`use-archive-prefetch.ts:10` dispose；`OverseasArchiveDetail.vue:49` 筛选图片，`:51` 关闭查看器；`OverseasArchivePage.vue:62` 搜索/翻页关闭详情和查看器。 | HTTP 延迟请求被 abort、旧组第三张未启动，列表筛选关闭直接查看器；单测验证已完成项保留。 |
| 私有条件缓存、权限与版本校验 | 完整实现。`image-cache.ts:52` credentials/no-cache/redirect:error，`:64` HEAD/ETag，版本变化重新GET；`archives.ts:76` 缩略图no-cache。既有 `B/app/overseas/image_delivery.py:55` private/no-cache/Vary。 | Chromium 刷新后六次原图GET均304/0正文；热预览只HEAD；版本变化测试重取新字节。未使用 request routing 模拟该缓存结论。 |
| 退出、换号、撤权、删除、失效清理 | 完整实现。`F/src/views/overseas/OverseasPortal.vue:37` 身份会话变化同步，`:178` 卸载清空；`archives.ts:17`/`:18` 前缀失效，`:73` 删除清理；`OverseasArchiveDetail.vue:56` 收起权限/删除失效内容。 | HTTP403清整套、删除立即清理、退出换号；后台预取撤权测试保留工作台缓存，仅清该归档。 |
| 独立归档URL，不按同名跨任务复用；原任务删除后仍可看 | 完整实现。`archives.ts:16` 编码归档ID/图片ID；`image-cache.ts:17` 完整URL为键；后台快照保持。 | 前缀a与ab隔离测试；HTTP fixture 明确 taskId=null/sourceDeleted=true，仍查看/下载独立原件。 |
| 冷/热请求数、字节、耗时及失败重试覆盖 | 完整记录。`scripts/archive-cache/browser.mjs:33` 冷热分别记录；`:69` 附近原图500后显式重试。 | `output/archive-cache/result.json`：冷6GET/4,574,682bytes/144ms，热组合操作新增0GET/0bytes/631ms。操作不同，不计算加速倍数，不推断生产带宽。 |
| 前端0.2.61→0.2.62，无后台重启/迁移 | 完整实现。`F/package.json:3`、`scripts/release/archive-runtime.py:11` 版本及`:15` 入口范围；当前diff无后端、锁文件或迁移变化。 | 发布工具只有前端静态写入；`archive-runtime.py:92` 只读记录API镜像/容器、服务PID及启动时间、schema和配置摘要。 |
| 已审、已提交、clean门禁；重build、隐私、哈希 | 完整实现。`archive-package.py:20` clean，`:24` reviewed_status，`:31` 重build，`:35` 快照复查，`:43` 隐私，`:53` 提交身份复查，`:56` dist竞态校验；继承 collect_assets 的资源审计。 | 包测试拒绝dirty/未审/源码变化/dist变化/隐私失败；当前尚未提交，未越过该门禁产出正式发布包。 |
| 保留哈希资源、备份入口、正式HTTPS哈希/后台不变、失败回退 | 完整实现。`archive-deploy.py:33` switch先检查碰撞并备份；`:82` rollback保留资源；`:107` 自动回退；`archive-runtime.py:106` 最终安装路径与HTTPS字节检查。 | 真实临时目录发布测试覆盖两代资源保留、错误基线、碰撞、备份篡改、后来部署保护、HTTP失败和服务漂移；R1修复及新26项独立复跑通过。 |

部分实现/未实现：本地产品实现未发现缺项。尚未进行的正式生产部署与只读验收按 DEV-PLAN 第4步保留为后续交付工作，未伪造为已验证。

Spec 漂移：未发现新增业务页面、API或数据库表。新增查看器下载按钮服务于合同原件下载；fixture 与测试只在隔离脚本入口，未接入产品路由。基础卡片compact展示维持原布局，六字段统一作用于授权的弹窗和详情。

## Stage 2：质量、安全、视觉及R1复核

### R1-01 已修复

旧报告唯一 MEDIUM 为 `atomic_copy` 内部 replace 失败后留下固定临时文件，阻塞回退。当前 `scripts/release/archive-deploy.py:18` 至 `:30` 用 `owned=False`，仅在 `open('xb')` 成功后取得所有权，并在 finally 删除本次临时文件。读取、chmod、replace 的异常都走清理；预先存在的文件因未取得所有权不会被删除。

独立检查及执行新增用例：

- `scripts/release/test_archive_release.py:167`：在真实内部 `os.replace` 第一次失败，保留原始异常，自动回退、原入口恢复、零残留；新备份重新部署后再回退成功。
- `scripts/release/test_archive_release.py:187`：预先存在的未知临时文件保留且原入口不变。
- `scripts/release/test_archive_release.py:196`：创建临时文件后源读取失败，清理后可重试。

此处故障在函数内部注入，不是调用前提前抛错，补上R1指出的测试盲区。新候选的26项发布测试本 reviewer 独立执行全部通过。未做进程kill/断电级恢复实验，不将 Python finally 的覆盖范围夸大。

### 代码质量与测试真实性

- 已扫描全部送审代码行数，无文件超过300行；新增生产TS未发现any。`image-cache.ts:13` 保持唯一共享缓存；缩略/查看、下载、预取分别由三个composable负责，没有重复缓存系统。
- `use-archive-image.ts:17` epoch与AbortSignal阻止迟到回填，租约在卸载/换图释放；`use-archive-download.ts:20` finally释放租约；`image-cache.ts:117` 单个消费者取消不会误杀其他消费者。
- 抽查新owner、SKU、归档请求、发布故障用例输入均可由正式路径到达。图片 HTTP fixture 用真实Chromium条件缓存，断言服务端304/正文、自然尺寸及下载字节；正式dist字段测试用隔离API验证请求载荷与裁切。二者不能冒充生产写入/真实后端权限验收。
- R1独立33项前端通过记录可追溯；本次未无理由重复全量486项。直接读取全量、类型、构建日志，并专门重跑变更涉及的26项发布测试。
- `git diff --check` 返回0；仅见CRLF归一提示。无新增质量阻断项。

### 安全扫描

对全部修改/未跟踪代码检查密钥前缀、敏感VITE变量、eval、dangerouslySetInnerHTML/innerHTML、用户绝对路径、any：命中只有 `AbortSignal.any` 和 Python `any` 等非危险调用，未发现本轮硬编码密钥、注入或新增不安全动态执行。

`archives.ts:16` 编码资源路径；`image-cache.ts:52` 禁重定向并重新鉴权；`archive-runtime.py:34`/`:59` 拒绝链接、越界和清单外文件并校验哈希；`archive-package.py:43` 及既有 `package-overseas.py:115` 继续做源码/资源隐私检查。`archive-runtime.py:13` 是授权的生产固定部署路径，不是泄露个人路径。

依赖审计记录critical=0、high=39、moderate=38、low=5为历史告警，本轮只改package版本，未改依赖或锁文件。本报告不宣称整个仓库无历史漏洞。

### 实际视觉对照

已打开并目视本轮1366-single、390-multi正式dist截图，以及 `output/archive-cache/02-detail.png`、`03-viewer.png`、`05-narrow-detail.png`、`06-narrow-download.png`；同时打开既有邻居基准 `output/archive-preview/review-detail.png`、`output/materials-archive-release/archive-single.png` 比较实际渲染。

`OverseasArchiveFields.vue:27` 的14px、双列、12/24px间距、56px标签与`:35`窄屏单列在截图中一致；长名称换行，确认与多SKU选择完整可达；白底弹窗、蓝色按钮与既有主题一致，等比原图与下载可达。图片HTTP fixture没有完整Art Shell主题，所以仅用于组件图像/布局/窄屏行为，不用其默认Element主题差异推定正式页面退化。正式主题判断使用dist截图。未发现新的视觉不匹配。

## 原始验证输出与边界

读取 `output/archive-all-tests-final.log`、`output/archive-typecheck-final.log`、`output/archive-build-final.log` 原始输出：

```text
ℹ tests 486
ℹ suites 0
ℹ pass 486
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 11909.3641

> hengxin-smart-image-frontend@0.2.62 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit

✓ built in 32.40s
```

类型检查exit 0由主Agent执行记录提供；日志本身只有命令头，不虚构独立执行退出码。构建及类型日志有既有pnpm配置迁移warning，不声称无警告。

本 reviewer 独立执行 `python -B -m unittest discover -s scripts/release -p 'test_archive_release*.py' -q`，工具返回exit_code=0，原始输出：

```text
----------------------------------------------------------------------
Ran 26 tests in 1.223s

OK
```

另已核验字段正式dist浏览器PASS、图片HTTP13项、工作台HTTP18项的脚本断言和结果文件。生产只读基线已有记录，尚未部署；安装后必须完成本候选既定HTTPS哈希/后台不变和正式页面只读验收，不创建/删除生产测试数据，不触发生图。本报告不替代这些后续操作。
