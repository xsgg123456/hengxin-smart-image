# 国内调用与执行正式实现审查 · 2026-11-11

## 最终结论与快照

**Stage 1：PASS。Stage 2：PASS。仅批准下述实现范围；生产部署和正式入口验收尚未由本报告完成。** 无未关闭的本轮 HIGH / MEDIUM 问题。

- 最终 candidateId：`28973cba4432bc7dea7b4145c322f871631e8efedb8a1e63fb6abbba1f6006b5`。报告落盘前 `review-status` 实查 currentId 相同，approved=false；主 Agent 负责登记批准，reviewer 未写 clean、未批准、未提交或部署。
- 首次候选 `14ed3b8efa7020ebe6c8bcb41e2dc17080b2b0ff2b3154ee68419df98c768a86` 存在 CLI 发起时间错误，Stage 1 未通过；修复候选 `02ba2748fc75a5f264c3840a16702b00ab0c0da94da7767793572f337d4e53c5` 已复核修复。最终候选仅进一步恢复构建副产物 `src/types/import/components.d.ts` 到 HEAD，已检查其 diff 为空。旧结论不覆盖未经复核的新代码。
- 源合同：`Product-Spec.md:1`、`:17` 本轮两节，`Design-Brief.md:1`，`DEV-PLAN.md:1`，以及已认可的 `frontend/preview-domestic-activity/`；读取 AGENTS、code-review skill 和快照协议后逐项审查。
- 正式范围：backend 的 `app/contracts/activity.py`、`app/modules/management/activity.py`、`activity_records.py`、`app/main.py`、`app/modules/auth/dingtalk.py`、`tests/test_management_activity.py`；frontend 的 `src/api/activity.ts`、`src/types/activity.ts`、`src/views/hengxin/admin/{activity.vue,activity.css,ActivityDetails.vue,use-activity.ts,users.vue}`、`src/router/modules/index.ts`、`src/api/hengxin/session.ts`、`tests/{business-route-access,membership-directories}.test.ts`、`package.json`。
- 下文 `backend/`、`frontend/` 均相对仓库内 `hengxin-smart-image/`，证据输出相对仓库根目录。

## Stage 1 · Spec Compliance

| 合同条目 | 结论、实现位置与验证 |
| --- | --- |
| 单入口、既有导航与旧地址兼容 | 完整实现。`frontend/src/router/modules/index.ts:14` 隐藏 usage/monitor 并注册带组件的 redirect，`:15` 注册合并入口；`frontend/src/api/hengxin/session.ts:25`、`backend/app/modules/auth/dingtalk.py:18` 保留新旧返回路径。`frontend/tests/business-route-access.test.ts:24` 检查实际路由合同，浏览器 `e2e-results.json:1` 两个旧链接均落合并页。 |
| 默认人员、同页执行；字段与20条分页 | 完整实现。`frontend/src/views/hengxin/admin/use-activity.ts:7` 默认 people；`activity.vue:11`、`:26`、`:32`、`:39` 对应两视图、人员及执行表、分页与详情。后端 `activity.py:91` 在全部筛选后分页。真实接口样本32次请求、2条未启动队列：首屏20条，次页14条，非前端演示数组。 |
| 人员、北京时间日期、类型共享；状态与搜索 | 完整实现。`backend/app/contracts/activity.py:12`、`activity.py:33`、`:43`、`:70` 验证并组合筛选；`use-activity.ts:17` 发送全部条件。`tests/test_management_activity.py:78` 验证北京时间边界、24条结果分20/4页、ID搜索及未知身份；浏览器额外4项覆盖类型、日期、加载、快速输入。 |
| 下钻保留/清空条件；页码与汇总范围 | 完整实现。`use-activity.ts:31` 人员下钻保留日期/类型，`:32` 状态下钻调用 reset，`:34` 变化回第一页，`:35` 请求代次避免旧结果覆盖；`activity.vue:21` 显示范围。`activity.py:85` 汇总先于分页，状态/关键词/当前范围下从全部 selected 汇总。24条测试证明两页汇总一致；reviewer 实点顶部排队，得到2条与顶栏2一致、调用数0。 |
| 当前状态按执行条数；进行阶段与历史失败区分 | 完整实现。`activity_records.py:25` 归并 retry_wait/collecting/cancelling；`:61` 建历史记录，`:85` 起覆盖当前 API，`:116` 起按最新 CLI turn 标记 current；`activity.py:56` 仅 current 计 live，历史失败保留在历史列表。测试 `:49`、`:134`、`:174`、`:199` 覆盖队列、旧CLI失败、新重试周期、真实重试后成功及收图不冒充结束；无跨渠道任务套数相加。 |
| 紧凑服务状态、服务/执行详情、真实未知 | 完整实现。`activity.vue:6`、`:8` 使用既有 monitor 心跳，`ActivityDetails.vue:3`、`:15` 展示时间/数量/错误及阶段/并发/心跳；未知数字为“未知”，历史请求图片为“未关联”。`use-activity.ts:15`、`:25` 清旧响应并提供错误重试，`:33` 手动刷新。浏览器17项含503故障后恢复和服务未知；reviewer 看到 API未知、CLI不可用，并未将队列2条当作在线。 |
| 图片、API重试、CLI实际启动独立计数，真实操作者 | 完整实现。`activity.py:25` 复用既有 summarize；`:59` 只筛事实类别，`:62` 按 operator_id 分组；`activity_records.py:65` 以 round 证据计CLI。既有 `api_usage_summary.py:24` 排除采用/恢复重复图片。测试 `test_management_activity.py:109` 得图片3/API2/CLI1，`:199` 走真实执行函数得图片1/API2，未将成功请求当图片。无可靠请求外键的API单条图片保持null；不声称单条未知图片可以精确分摊人员总图数。 |
| 日期事实口径与真实发起/开始时间分离 | 修复后完整实现。`Product-Spec.md:10` 明确API/CLI启动日、未启动发起日、图片产出日；`activity_records.py:19`、`:74` 以内部 statistics_time 保持统计日期，以 submission 修正 createdAt；`activity.py:74` 使用统计时间筛选；`activity.vue:11` 统计说明明示。跨日新增测试 `test_management_activity.py:219` 通过，reviewer 另用真实 ConversationTurn 表独立重验，见下节。 |
| 不伪造历史身份/执行/时间、删除数据、只读与权限 | 完整实现。`activity.py:31` 仅超管/设计主管，`:49` no_autoflush；`activity_records.py:46` 未知身份、`:55` 已删除标记；`tests/test_management_activity.py:35` 四角色200/403，`:49` 捕获SQL仅SELECT，`:158` 保留已删除事实但不计当前。`frontend/src/api/activity.ts:8` 校验响应并复用身份代次检查请求层。 |
| 成员页移除整个历史待核对，成员与申请保持 | 完整实现。`frontend/src/views/hengxin/admin/users.vue:6` 仅两页签，`:32` 类型去除legacy，`:50` 保留历史身份编辑防护；加载仍限定members，申请使用既有组件。`tests/membership-directories.test.ts:33` 验证无legacy查询、切申请不额外读成员、403清敏感表单；浏览器刷新/进入后仅2个页签，申请可切换。后端授权规则未修改。 |
| 使用已认可外观，生产无演示控制/数据 | 完整实现。`activity.vue:2`、`activity.css:1` 继承 hx/art/Element 组件，`use-activity.ts:2` 接实际接口，无预览场景及对照按钮。实际查看桌面和390截图，并独立打开当前页面及原版调用统计基准；设计数值见 Stage 2。 |
| 六人清理为已执行操作，无新增批量删除能力 | 范围符合。正式 diff 无删人API或删除调用。已读取 `output/domestic-member-cleanup-20261111/cleanup.py:12` 的固定6个目标及关联计数、`:28` 的其余行精确对比保护、`:29` 的24人/legacy0约束；`postcheck.txt:1` 各表 matches=0。此项引用既有生产操作回执，没有在审查中再次执行删除或伪称重新实查生产。 |
| 不扩展海外/执行器/清理/配置 | 范围符合。`backend/app/main.py:22`、`:51` 仅加入只读路由；没有新表、迁移、依赖及实际生成逻辑变更。package仅版本0.2.68。已批准预览目录继续独立，未进入生产入口。 |

**部分实现：无。未实现：无（本轮合同）。Spec 漂移：无。** 已修复问题关闭后才进入 Stage 2。

### 已关闭 MEDIUM：CLI 启动时间冒充发起时间

旧实现 `activity_records.py` 直接把 round.occurred_at 用作 createdAt。reviewer 独立建立真实 ConversationTurn：北京时间11月10日23:59提交，11日00:01启动。旧响应 createdAt、startedAt 都是 `2026-11-10T16:01:00+00:00`，与真实提交不符。

主 Agent 修复并同步日期说明后，同一独立复现得到：

```text
createdAt: 2026-11-10T15:59:00+00:00
startedAt: 2026-11-10T16:01:00+00:00
2026-11-10: total=0, summary.cli=0
2026-11-11: total=1, summary.cli=1
```

按启动事实日筛选与人员CLI统计一致，展示时间不再混用。脚本 `output/playwright/activity-cli-date-repro.py:1`，旧/新原始响应分别 `activity-cli-date-repro.log:1`、`activity-cli-date-fixed.log:1`。初次独立脚本未启用API导致前置创建失败；补与既有fixture一致的API_IMAGE_ENABLED后才执行有效复现，未用该前置失败判定产品问题。

## Stage 2 · Code Quality

### 代码、错误处理、安全与测试真实性

- PASS：新文件分为契约、事实投影、查询、API适配、交互状态、详情组件；主要实现分别为73/101/133行（后端）及26/8/62/42/36行（前端），测试237行，均低于300行。依据 `backend/app/contracts/activity.py:1`、`modules/management/activity.py:1`、`activity_records.py:1`，`frontend/src/views/hengxin/admin/use-activity.ts:6` 与 `ActivityDetails.vue:27`。无新增 TypeScript any。
- PASS：`use-activity.ts:15`、`:21`、`:25`、`:35` 用代次、卸载标志和计时器保护异步响应，失败清除旧数据并提供重试；`frontend/src/api/activity.ts:8` 校验关键字段，`src/api/hengxin/http.ts:10` 保留已有认证/超时/身份切换隔离。
- PASS：扫描本轮文件未发现 eval、innerHTML、dangerouslySetInnerHTML、硬编码密钥、敏感前端环境变量或用户绝对路径；SQL使用 ORM select，没有输入拼接SQL。`activity_records.py:37` 只返回固定安全错误文本，原始诊断不进入响应；`ActivityDetails.vue:11`、`:18` 使用Vue文本插值，既有 `api_monitor.py:116` 的暂停原因也来自固定白名单。后端故意放入Bearer/private URL测试仍不泄露（`test_management_activity.py:49`、`:174`）。
- PASS：测试使用隔离真实业务表、FastAPI和实际 execute_next，不只mock汇总函数。`test_management_activity.py:199` 真实重试两次请求仅产一图；`:49` 捕获SQL证明只读；`:78` 精确验证两页汇总；reviewer跨日复现直接建真实turn，补足新增回归使用事实表的边界。浏览器通过真实前端及隔离API验证21项，故障注入仅用于错误分支，正常数据源为服务端表。
- LOW 可维护性：`activity.vue:11`、`ActivityDetails.vue:4`、`use-activity.ts:7` 和 `src/types/activity.ts:2` 的单行较长，阅读成本高；不影响本轮功能，可后续格式化。`activity.py:53` 和 `activity_records.py:59` 沿用全量事实读取并增加当前表扫描，当前未做大规模数据性能验证，不宣称已验证任意历史规模。
- 依赖审计边界：`output/domestic-activity-release/audit.json` 原始结果 critical=0、high=39、moderate=35、low=5。锁文件和依赖声明未更改，本轮没有引入新依赖；这些既有告警仍存在，不能把本报告描述为全项目无漏洞或审计全绿。

### 实际视觉对比

reviewer 独立浏览器 `release-review` 打开正式合并页和3041预览中的真实原版调用统计组件，实际查看截图：`output/playwright/activity-review-final.png`、`activity-review-baseline.png`。同时查看主 Agent 的1920/390截图和已确认预览1920截图。两个页面在同一1280视口实测：

| 项目 | 正式合并页 | 原版基准 |
| --- | --- | --- |
| 标题左坐标 | 259px | 259px |
| 标题字号/字重 | 28px / 650 | 28px / 650 |
| 卡片内边距 | 23px | 23px |
| 卡片圆角 | 16px | 16px |

实现位置：`activity.vue:2`、`activity.css:1`、`:5`、`:8` 及既有 `frontend/src/views/hengxin/prototype.css:2`。标题、品牌、白底卡片、操作色、筛选密度沿用现有系统；去掉预览条和因真实异常新增警示条符合合同。390宽筛选堆叠，表内横滚，按钮可达；现有浏览器断言文档宽度不超过视口。不是声称不同信息结构逐像素相同。

### 编译与测试原始输出

reviewer 独立运行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：

```text
exit_code: 0
stdout: （空）
stderr: （空）
```

reviewer 首轮独立运行 `.venv/Scripts/python.exe -m pytest tests/test_management_activity.py -q`（在跨日回归加入前）：

```text
.....................                                                    [100%]
21 passed, 2 warnings in 3.51s
```

已检查主 Agent 最终证据，不冒充 reviewer 重新执行全套：

```text
# backend-targeted-final.log
......................................................                   [100%]
54 passed, 2 warnings in 9.05s

# frontend-tests-final.log
ℹ tests 542
ℹ suites 0
ℹ pass 542
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 12524.0973

# production-build.log
✓ built in 45.03s

# backend-full.log
9 failed, 2949 passed, 446 skipped, 6 warnings in 747.01s (0:12:27)

# backend-baseline-failures.log（HEAD隔离源）
9 failed, 43 passed, 2 warnings in 9.90s
```

最终 `typecheck-final.txt` 只有两个既有npm配置警告，主 Agent 命令退出0。54项后端日志包含 httpx/BlockingPortal 弃用警告，没有测试失败。完整后端不是全通过：对照HEAD归档的五个相关测试文件，9个失败nodeID全部相同；日志调用栈明确位于 `output/domestic-activity-release/baseline/hengxin-smart-image/backend/app/`。其中海外路由集合断言1项、Windows safe open unavailable 7项、Windows symlink权限1项。它们不因本轮改变产生，且本轮不发布海外实现；据此不将这些旧失败记成本轮阻断，也不把446项跳过宣称已覆盖。

## 全仓候选中的独立范围复核

- 预览代码：引用 `docs/reviews/DOMESTIC-ACTIVITY-PREVIEW-20261111.md` 两阶段PASS。本轮按其表内10个归一化SHA256逐个重算，10/10一致；不是仅按文件名沿用旧结论。
- 其他会话维护文件：引用 `docs/reviews/INTRANET-1PANEL-INSTALL-20261111.md:3` 的最终两阶段PASS（仅安装脚本准入）。本轮实查原始SHA256：install_panel.py=`8E37AA7E10830A736932ACF093B50222E5E0FA41AE32D7317FD70EEEC3F17BE8`；test_install_panel.py=`1DC88CA8F9317CE88CFDB7CB2D905A27A5CF858201396C2602ECC34D2F871205`，与原报告一致。它们不属于本轮提交范围；不据此宣称1Panel生产安装完成。

本报告批准代码实现供主 Agent 继续既有发布流程；生产镜像安装验证、排空/切换、8080正式入口与六人清理后状态复核仍需发布阶段据实完成。
