# 累计生成图片与分页正式实现独立审查

- 审查日期：2026-10-10；执行角色：独立 code-reviewer，依据 `.agents/skills/code-review/SKILL.md`。
- 最终 candidateId：`7b990a99b6a52523b93de71ce899ac2cf6ce36144fff8b0c2a2f99b9adb96b8d`。
- 原交接 candidateId：`e2d19d7f01a148ab05cfaa51405ee38c9dcdbd0a5b7b42e6fa9fddf350f53343`。审查发现漂移并通知主 Agent；主 Agent 逐文件比对后重新固定候选。差异为 Vite 自动生成的 `frontend/src/types/import/components.d.ts`，reviewer 已复核最终相对 HEAD 仅新增 ElDatePicker、ElTabPane、ElTabs 声明（84、113、114 行），未改变业务逻辑。最后 review-status 的 currentId 匹配最终候选。
- 范围：本轮后端 contracts/api_usage、management/api_usage 与 api_usage_summary、test_usage_generated_totals；前端 usage 契约/校验器、ApiUsage/ApiUsageDetail、RealRecords/use-records、相关测试及生成声明。下文 backend/frontend 均相对 `hengxin-smart-image/`。
- 不包括预存 `.agents/skills/dev-builder/SKILL.md` 改动；不对该预存规则改动作批准。未修改实现、未提交、未部署、未调用收费模型。
- 需求依据：Product-Spec、DEV-PLAN 的 2026-10-10 正式授权补充，以及 `docs/USAGE-TOTAL-IMPLEMENTATION-20261010.md:5` 的全部口径条目；设计依据为已确认 `output/usage-total-preview/usage.png` 与独立预览源码。

## Stage 1 · Spec Compliance：PASS

| 条目 | 结论及证据 |
| --- | --- |
| 累计、首次、修改、生成任务四项；默认全量；去库存 | 完整实现。`frontend/src/views/hengxin/admin/ApiUsage.vue:45` 空日期/人员/类型初值，48 行发 outputsOnly 查询，51 行四卡，72 行重置。模板无库存展示。真实页面首次请求不带日期/人员/类型，卡片为 741、570、171、57。 |
| 10 + 3 = 13；全部 API 修改 kind 与 CLI 候选计入 | 完整实现。`backend/app/modules/management/api_usage_summary.py:7` 列出四类 API 修改；22 行只计 succeeded 的正式版本/候选，38 行分项、83 行求和。`backend/tests/test_usage_generated_totals.py:32` 真实业务入口执行 10 次首次、2 次 API 修改和 1 次 CLI 候选，独立复跑通过。121 行覆盖所有 API kind。 |
| 采用、恢复、失败、纯文字、上传不加数；未采用候选已计入 | 完整实现。上述 generated_images 白名单排除请求、轮次、动作与创建事件；业务流程测试在采用前断言 13，重复采用和恢复后 summary 不变（同测试 48–60 行），121 行反向断言失败不算；没有素材上传计数分支。 |
| 生成任务按筛选范围去重 | 完整实现。`api_usage_summary.py:31` set 与40行 task_id 去重；同专项 76 行用跨日跨人同任务验证总量2而任务1。 |
| 幂等、删除和七天清理累计不缩 | 完整实现。继承 `backend/app/modules/management/api_stats/projection.py:62` 按唯一 key 合并、持久事实覆盖历史投影，`facts.py:29` 冲突幂等。专项32行通过真实 preserve 两次、七天 expire、任务删除验证相同 summary；已删除事件标记全部为真。 |
| 日期按产出事实及北京时间，按操作者/历史登记人；未知不猜 | 完整实现。`backend/app/modules/management/api_usage.py:91` 按 occurred_at 转上海日期、operator_id 筛选；`api_stats/facts.py:78` 正式版本 created_at，100行候选 finished_at；`projection.py:47` 保留不可证实来源。专项76行跨UTC 16:00验证北京换日和人员筛选；105行未知历史 count=0、unverifiedVersions=1，回填后不变。 |
| 历史待核实提示、inventory兼容保留 | 完整实现。`api_usage.py:102` 单独累计不可证实版本、118行保留提示计数，`frontend/src/views/hengxin/admin/ApiUsage.vue:21` 展示未计入累计说明；`backend/app/contracts/api_usage.py:105` inventory 字段保留，未冒充累计。 |
| generationType、旧 category、outputsOnly 兼容；执行消耗全事件 | 完整实现。`backend/app/contracts/api_usage.py:11` 新字段可选且保留 category，`api_usage.py:97` 依次筛选；`api_usage_summary.py:10` 仅按已知 kind 分类 API 请求、CLI三种事件归 cli_edit。`ApiUsage.vue:48` 业务开启 outputsOnly、执行关闭；73行切页签保留 applied。前端UI测试 `api-management-usage-ui.test.ts:112` 验证未提交筛选不影响切页签。 |
| 日报、汇总、详情对账与分页无关 | 完整实现。`api_usage.py:108` 全量分组，113行以后才切事件页；事件64行携带 generatedImages/generationType；`ApiUsageDetail.vue:32` 按日/人/生成类型/outputsOnly 同范围请求。真实浏览器详情3事实为10+2+1=13，日报57行与741总数一致。 |
| 权限与删除导航 | 完整实现。`api_usage.py:75` 服务端按角色判定全员/个人，80行解析UUID，83行越权403；`ApiUsageDetail.vue:8` 已删除任务无跳转。专项76行验证降权后只剩本人和403；真实浏览器验证已删除任务无链接。 |
| 换图记录20/50/100；切首页保筛选；删除纠页 | 完整实现。`RealRecords.vue:17` 页大小选项与双向绑定；`use-records.ts:24` 默认20、33行传真实pageSize、35行按该值纠正越界页、67行同步回首页，保留search/filter。`frontend/tests/records-pagination.test.ts:11` 挂载真实组合函数覆盖筛选、删除纠页、乱序响应及失败重试；后端专项145行覆盖56条真实记录的20/50/100返回；真实浏览器网络请求确认 page=1 且保留search/status。 |
| 日报20/50/100且总数不变 | 完整实现。`ApiUsage.vue:31` 分页选项和回首页、49行仅切日报显示数组。前端UI测试112行和真实浏览器20→50→100断言通过。 |
| 加载、错误、空态及重试 | 完整实现。`ApiUsage.vue:14`、`ApiUsageDetail.vue:4` 的互斥状态；`use-admin-query.ts:6` 序号防过期响应。UI测试65行和真实浏览器390px延迟、503、重试、空范围验证通过，等待/失败隐藏旧卡片。 |
| 预览UI与真实引导一致 | 完整实现。reviewer 实际打开3028调用统计、查看渲染截图，并打开邻居执行监控对照：四列卡片、蓝色筛选/标签、字体、间距和摘要面板一致；保留正式历史说明，移除模拟预览标识。`prototype.css:42` 标题17px，48行四列/16px间距，52行数值27px，59行摘要padding16px18px/圆角10px；与预览复用同一套样式。窄屏证据为 usage-narrow、loading-narrow、error-narrow、empty-narrow 与 records-narrow 截图。 |

部分实现：无。未实现：无。HIGH/MEDIUM 缺陷：无。Spec 漂移：未发现新增无需求页面、接口或数据表；查询新增字段和兼容旧字段符合实施合同。真实业务采集、采用/恢复/下载实现未改。

## Stage 2 · Code Quality：PASS

- 结构/类型：`api_usage_summary.py:10`、22行统一供 summary/event 使用，未复制计数口径；契约 `backend/app/contracts/api_usage.py:8` 为 Literal，前端 `types/api-management-usage.ts:1` 联合类型，`api/api-management-usage-validate.ts:7`、17行校验新增计数和枚举。新改源码/测试均未超过300行（最长新测试170行）；未新增 any。
- 错误处理：`use-records.ts:30` 序列守卫、37行catch、67行同步重置避免重复错误页；`use-admin-query.ts:6` 防止过期结果覆盖；`api_usage.py:27` 日期格式和70行起权限/参数错误明确。相关错误、乱序、筛选保留测试确实挂载生产组件/组合函数，不是仅断言源码字符串。
- 测试真实性：`test_usage_generated_totals.py:32` 通过 create/execute/revise/submit/adopt/restore/expire/delete 真实业务代码验证；收费模型用替身。API类型矩阵121行属于聚合单测，不能单独证明生产采集，故结合真实流程32行审查。76行模拟事实用于精确北京时间与权限矩阵；145行真实数据库记录用于API分页。浏览器使用真实隔离PG和本地API，种入的统计事实只证明展示/筛选/对账，未冒称真实模型生成证据。
- 安全：本轮生产改动未检出 eval、innerHTML、dangerouslySetInnerHTML、前端密钥变量/硬编码密钥或字符串拼接SQL；`api_usage.py:43`、115行为SQLAlchemy条件表达式，126行CurrentUser鉴权保留；`ApiUsageDetail.vue:8`、16行用户名称/任务名以Vue文本插值显示。测试 `api-management-usage-ui.test.ts:35` 与 `records-pagination.test.ts:20` 的 new Function 仅编译本地固定源码，无产品输入到该调用。
- 视觉邻居实查：reviewer 独立IAB依次打开调用统计与执行监控实际渲染，确认品牌侧栏、标题、卡片、按钮和间距一致；两页复用 `prototype.css:42` 起的管理样式。没有仅凭“复用组件”判定视觉通过。

## 编译与验证原始输出

reviewer 独立执行 `backend/.venv/Scripts/python.exe -m pytest tests/test_usage_generated_totals.py -q`：

```text
.......                                                                  [100%]
7 passed, 2 warnings in 3.43s
```

2项为现有Starlette/httpx与anyio别名弃用警告。全套日志 `output/playwright/usage-total-real/backend-tests.log` 原始终态：

```text
1649 passed, 17 skipped, 15 warnings in 310.31s (0:05:10)
```

全套启动时新增测试收集6项，末尾追加的记录分页第7项由上述独立专项补验，不声称全套重跑包含该新增项。

前端全套原始输出 `output/playwright/usage-total-real/frontend-tests.log`：

```text
ℹ tests 238
ℹ suites 0
ℹ pass 238
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 5479.7673
```

类型检查 `typecheck.log` 原始输出（主 Agent exit 0；reviewer 在最终候选上另行复跑也 exit 0，无类型错误；主 Agent 的 `typecheck-final.log` 亦 exit 0）：

```text
> hengxin-smart-image-frontend@0.2.20 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

正式构建原始末行 `build.log`（主 Agent exit 0）：

```text
dist/assets/index-D3UydALD.js                                                       562.42 kB │ gzip: 191.29 kB
dist/assets/index-CMgexOgT.js                                                       670.46 kB │ gzip: 230.78 kB
dist/assets/echarts-DSKumXTW.js                                                     748.03 kB │ gzip: 244.46 kB
dist/assets/index.vue_vue_type_style_index_0_lang-D82PisoR.js                       813.93 kB │ gzip: 275.57 kB
dist/assets/index-3OWe9E-h.js                                                       963.15 kB │ gzip: 307.72 kB
✓ built in 38.47s
```

构建发生在生成声明漂移前；声明差异已单独复核，不改变运行代码。pnpm提示现有package.json的overrides/onlyBuiltDependencies字段位置弃用；没有本轮新增构建错误。

浏览器脚本原始结果位于 `browser-usage.log:1` 与 `browser-records.log:1`，两者 `passed:true`。记录页可见图片加载失败来自隔离种子没有建立MinIO对象；该证据不用于宣称缩略图或真实对象存储下载验证通过。下载真实业务路径由上述后端流程测试的zip响应200验证。本轮不认证生产数据完整性、生产部署或收费模型画质。

## 快照登记交接

Stage 1 PASS、Stage 2 PASS 仅适用于本文最终 candidateId 的业务审查范围。由主 Agent 按协议登记同一候选与本报告路径；reviewer 未调用 review-approve，未向 `.needs-review` 写 clean。
