# 累计改动提交前集成审查 · 最终复审

- 日期：2026-09-16。
- **最终 candidateId：`51ddff66e68983d6de0e13ddaf073549d9141df58a205531747809fdaeb6229d`。**
- **Stage 1：PASS；Stage 2：PASS。前次 HIGH-01、HIGH-02 均关闭，无剩余提交阻断。**
- 范围保持原派发：git diff HEAD + 未跟踪项目文件及根 Spec/CHANGELOG/Plan/Brief/README，排除 .codegraph、.cursor、output；沿用已交付历史专项证据，不重复产品全量验收。
- 本结论只批准该累计提交范围。真实钉钉双端终验、monitor/settings、尺寸治理、备份容量及正式上线验收仍未由本报告确认通过。
- 本轮起止 review-status 的 currentId 均匹配上述编号。前次 keeper 末尾空行差异已复核；本轮重新读取 router 和新增路由测试，未观察到审查期间代码变化。下方旧 FAIL 报告仅为历史记录，当前结论以本节为准。

## Stage 1：PASS

| 条目 | 最终结论与证据 |
| --- | --- |
| HIGH-01 浏览器绑定 | 关闭。backend/app/modules/auth/router.py:55–60 设置短期、限定路径、HttpOnly、SameSite=lax 的 state Cookie，HTTPS 配置下 Secure；:75–80 在消费前比较 Cookie 与 state 的 UTF-8 bytes，使用 compare_digest，不匹配立即拒绝。backend/tests/test_dingtalk_auth.py:164–173 通过真实 HTTP 路由验证无 Cookie、错误浏览器 Cookie 均不调用 provider、不消费 state。 |
| HIGH-02 失败回调重放 | 关闭。router.py:82–84 在原有 SELECT FOR UPDATE 消费后立即单独 commit，再执行 provider；:92–100 的 rollback 不再撤销已提交消费。test_dingtalk_auth.py:142–190 参数化 success/provider/enterprise/pending，检查数据库持久 consumed_at，强行携带原 Cookie 重放仍 denied 且 provider 总共只调用一次。 |
| 回调 Cookie 生命周期 | router.py:64–67、91–102 所有受控成功/错误重定向清同一路径 Cookie，成功再签发系统会话；不宣称框架参数校验 422 或数据库意外 500 也必然清 Cookie。新测试 :182–186 检查删除响应和持久消费。 |
| 身份和退出集成 | 企业 unionId→userId→企业详情检查仍在 dingtalk.py:142–180；退出接口 router.py:140–148、sessions.py:35–55，与前端 HengxinLogout.vue:18–36 对接。先前退出/回调专项行为证据保留。 |
| 全 Spec 覆盖与未完成项 | 下方逐项处置表继续适用；REQ-008/AC-019–020 的本次代码缺陷现已关闭，真实双端实测仍待验收。其余条目按历史已交付切片和明确后续阶段区分，不把未完成的 Phase13/14 算成新增缺陷。 |
| UI 与引导真实性 | 本轮独立打开 localhost:3008 登录 denied 页，看到错误说明和重新授权；打开模板库与任务中心，对照真实渲染，退出入口可见，任务新建和详情入口存在。对应 dingtalk-login.vue:24–40、HengxinLogout.vue:2、use-task-list.ts:1。没有点击真实授权或创建任务。 |
| Spec 漂移 | 新认证表/接口对应 Phase12，真实 usage 替换原 501 对应 Phase13.1（backend/app/main.py:41、contracts/router.py:25、management/router.py:14）；品牌、路由、观测与 Skill 变更分别有根 Spec:3、159、261、476 依据。未发现本次需要新增产品授权的范围扩展。 |

## Stage 2：PASS

| 维度 | 证据及边界 |
| --- | --- |
| 测试真实性 | 新测试调用真实 HTTP 路由、真实数据库事务和真实用户映射，只桩外部 provider；独立复跑认证两文件 16 passed。测试手工构造 Cookie 模拟不同浏览器，不声称实际钉钉浏览器 Cookie 端到端通过。缺少独立双浏览器自动化和真实 PG 并发重放的新增用例是 LOW 覆盖余项；原消费使用行锁，见 dingtalk.py:214–216。 |
| 命名、类型与职责 | state Cookie 名称集中 router.py:22；_callback_response:64 统一响应清理，消费与成员会话事务边界清楚。新增/变更源码中超过 300 行的仅两个既有框架文件：header/index.vue 486→487、router/guards/beforeEach.ts 420→406。记录为既有 MEDIUM 维护性债务，不要求本次扩大重构；新文件没有新增超限。抽查 dingtalk.ts、logout.ts、execution*.ts 无 any。 |
| 危险代码与敏感内容 | 已扫描 99 个变化源码/运行配置文件的 eval、HTML 原文注入、shell=True、常见真实密钥前缀、前端敏感环境变量和私钥头；唯一命中 backend/tests/test_public_messages.py:24 为过滤器测试的标记字符串，没有私钥内容。第一次扫描因控制台 GBK 输出文档字符失败，已改 UTF-8 并限定源码/配置重新完整执行。结合主 Agent 的暂存清单检查，实际 .env、auth.json、私钥及 output/.cursor/.codegraph 不在提交范围；该判断不扩大为绝对不存在任何未知格式秘密。 |
| 会话和日志安全 | sessions.py:23–27 随机令牌仅哈希落库；dependencies.py:17–36 禁用开发身份/停用账号并取当前角色；dingtalk.py:131 日志仅 method/path；public_messages.py:7–24 拒绝凭据标记，:25–42 删除代码块/链接/路径并限长。使用固定错误文案而非原始 provider 响应。 |
| 部署与执行隔离 | infra/.env.vps.example:6 默认 false；compose.yaml:12,26,36–40 环境注入且必须提供存储凭据；compose.vps.yaml:5–23 仅 loopback 暴露数据服务/API，:30 worker profile 避免默认双消费者；hengxin-worker.vps.service:8,16 使用 codex 用户及 UMask=0077。workspace.py:57–84 保留 bwrap 隔离、clearenv、开发代理白名单和生产拒绝；凭据路径是配置引用，非凭据内容。 |
| 统计集成与权限 | management/usage.py:153–179 对个人请求拒绝其他 operator 并过滤，all_scope 仅主管/超管；:53–59 缺失 token usage 保持未知。test_management_usage.py:45、70、81、103、121 覆盖真实记录、越权、范围、超时/待核实。:165–179 先全量读取再内存筛选为 LOW 扩容余项，不能作为 100 用户性能验收。 |
| 实际邻居视觉对比 | reviewer 本轮 CUA 实际截图 1280×720 的 templates/index 与 tasks/index：相同约 230px 侧栏、内容 x259、标题/蓝色新建按钮同一行、白色圆角卡片和灰底；顶部品牌和退出按钮均完整可见。登录 denied 页也已截图，红色品牌、蓝色主按钮、浅黄色错误提示无裁切。代码依据 header/index.vue:159–160、HengxinLogout.vue:2、dingtalk-login.vue:24–40；根 Design-Brief:3–27。其他历史详情、品牌深色及 Skill 分组视觉沿用各专项报告，不声称重新覆盖所有主题/视口。 |

### 验证原始输出

独立执行 `python -m pytest tests/test_dingtalk_auth.py tests/test_auth_sessions.py -q`，exit 0：

```text
................                                                         [100%]
16 passed, 4 warnings in 3.07s
```

4 条为既有 TestClient per-request cookies 弃用警告。全量与编译采用此前已读取日志和主 Agent 证据，具体原始摘要保留在下方：backend 540 passed/133 skipped、frontend 89 passed、vue-tsc exit 0、Vite 3330 modules transformed/built in 27.70s。不是声称旧全量测试已包含新加的四个参数化测试；认证增量由本轮 16 项补足。

最终只读 review-status：

```text
currentId: 51ddff66e68983d6de0e13ddaf073549d9141df58a205531747809fdaeb6229d
approved: false
```

approved=false 表示尚待主 Agent 登记凭据，非本轮审查失败。主 Agent 可使用同一 candidateId、本报告路径和 stage1=PASS/stage2=PASS 执行 review-approve；若生成文件或代码再变化，必须重新固定并复核。reviewer 未提交、未推送、未登记批准、未写 clean。

---

## 历史记录：前次 Stage 1 FAIL（已被上述复审取代）

# 累计改动提交前集成审查

- 日期：2026-09-16；角色：独立 code-reviewer，只读实现、仅写本报告。
- 最终 candidateId：`3f7124345703a201da0073959a89ccd07ef0de38d72625b3e65adcdb5e7f0673`。
- 初始 candidateId：`83e0ff51ddc4419ec27eac89e54be5f8d65787a51a6ca7f400b5cfd273736c7a`。
- 范围：git diff HEAD 和未跟踪 hengxin-smart-image 项目文件，以及根 Product-Spec、CHANGELOG、DEV-PLAN、Design-Brief、README；排除整个 .codegraph、.cursor、output。项目差异共 170 个路径。以下 backend/frontend/infra/docs 路径相对 hengxin-smart-image，根文档单独标明。
- **Stage 1：FAIL，2 项 HIGH。Stage 2：未执行。当前不可登记两阶段 PASS。**
- 这不是整个产品验收；monitor/settings、真实钉钉双端终验、尺寸治理及正式上线验收仍按原计划保留，不作为本次新增缺陷。

## 快照复核

主 Agent 在审查中去掉 `infra/local_codex_keeper.py:93` 后的一个空白行。已实际读取工作区相对暂存区 diff：仅末尾删除空行，最后一条可执行语句仍是 `temp.replace(KEEPER_FILE)`；无逻辑修改。最终只读 review-status 的 currentId 与最终 candidateId 相同。`git diff --cached --check` 无输出、exit 0。没有用旧报告批准新快照。

`DINGTALK-CALLBACK-REVIEW.md:7` 的局部 PASS 只审 exchange_auth_code、日志和前端错误文案，不涵盖本次发现的完整授权入口与回调事务问题，因此与本报告的集成 FAIL 不冲突。`LOGOUT-REVIEW.md:3` 的退出修复结论同样不覆盖 OAuth state。

## Stage 1：Spec Compliance — FAIL

### HIGH-01：OAuth state 没有浏览器绑定

**Spec 原文：** 根 `Product-Spec.md:499`：“验证短期、一次性 state 及浏览器绑定，避免回调重放和任意跳转”。

**实际差异：** `backend/app/modules/auth/router.py:45–55` 的 authorize 只创建数据库 state 并返回跳转，没有设置浏览器关联 Cookie；`:58–69` 的 callback 只接收 state/code/authCode 和数据库 Session，不读取或验证发起浏览器身份。`backend/app/modules/auth/dingtalk.py:203–224` 仅用 state 哈希查记录、检查过期和消费标记；`backend/app/modules/auth/models.py:53–60` 也没有浏览器关联字段。授权参数 `dingtalk.py:108–115` 没有可替代该绑定的 PKCE/nonce 机制。

**影响与复现路径：** 浏览器 A 发起授权并取得尚未消费的回调 URL 后，该 URL 可在浏览器 B 打开；后端无法区分 B 是否发起过这次登录，会把授权码所属账号的会话 Cookie 写给 B（`router.py:84–85`）。这是登录 CSRF/会话混淆风险，不是“缺企业配置导致未终验”。本结论来自完整路由签名和实现，不声称已对真实企业执行攻击。

**修复验收：** 绑定发起授权的浏览器上下文；无绑定或绑定不匹配时在交换授权码之前拒绝。增加两个独立浏览器客户端的回归：A 的有效 state 在 B 失败，A 正常成功，过期与重放失败。

已查阅主标准确认风险：[RFC 9700 §4.7.1](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.7.1) 要求 state 与 user-agent session 关联，或使用满足条件的等效机制。这里同时违反项目自身明确需求。

### HIGH-02：失败回调会回滚 state 消费，允许再次接受同一 state

**Spec 原文：** 同上，根 `Product-Spec.md:499` 明确“一次性 state”；`:347` 的 AC-020 包含回调刷新/重放。

**实际差异：** `backend/app/modules/auth/dingtalk.py:223` 只在当前事务赋值 consumed_at；`backend/app/modules/auth/router.py:67–70` 将消费和外部身份交换放在同一未提交事务；`:75–83` 企业不匹配、供应方异常及 HTTPException 分支全部 rollback，撤销 consumed_at。后续请求仍可以使用这条未过期 state。

**独立复现：** 使用 SQLAlchemy 内存 SQLite，仅创建真实 AuthLoginStateRecord 表，调用真实 create_login_state、真实 callback 和真实 consume_login_state。仅将外部 provider 换为抛 DingTalkProviderError 的桩；未修改项目文件、未接触线上数据库。SQLite 用于验证事务回滚，不用于证明 PostgreSQL 并发锁行为。命令 exit 0，原始输出：

```text
callback HTTP: 303
after failed callback consumed_at: None
same state accepted again: /tasks/index
```

**测试盲区：** `backend/tests/test_dingtalk_auth.py:47–61` 只在同一成功事务内重复调用消费函数以及检查过期，没有经过 callback 的失败 rollback 分支。全量测试通过不能覆盖此缺陷。

**修复验收：** 消费必须在有效性/浏览器绑定核实后原子且持久化；后续 provider 失败不能使其复活。覆盖 unavailable、enterprise-mismatch 和其他失败路径；第二次回调必须在调用 provider 前拒绝。失败后重试通过重新发起授权取得新 state。

### 本次其他已核对条目与历史证据边界

| 条目 | 结果及证据 |
| --- | --- |
| 企业成员身份映射 | 匹配本次修复要求。`backend/app/modules/auth/dingtalk.py:142–180` 用户令牌→unionId→企业 userId→详情一致性核验；`backend/tests/test_dingtalk_auth.py:65–88` 使用不同 openId 并断言 member-1。历史报告 `docs/DINGTALK-CALLBACK-REVIEW.md:27` 起。 |
| 回调错误显示 | 匹配已知错误类别。`frontend/src/views/auth/dingtalk-login.vue:128–162`；历史实际页面证据 `docs/DINGTALK-CALLBACK-REVIEW.md:37`，不重新声称真实登录成功。 |
| 退出和会话失效 | 实现匹配。`backend/app/modules/auth/router.py:123–131` 撤销和删 Cookie；`sessions.py:35–55` 拒绝过期/撤销；`frontend/src/components/core/layouts/art-header-bar/widget/HengxinLogout.vue:18–36` 成功后清身份并导航、失败保留身份。继承 `docs/LOGOUT-REVIEW.md:27` 起的专项行为/视觉证据。 |
| 开发身份边界 | `infra/.env.vps.example:6` 已为 false；`backend/app/modules/auth/dependencies.py:17–18,31–36` 禁止生产开发身份并实时判断账号状态。线上配置是否一致不由代码快照证明。 |
| 新部署入口 | `infra/compose.vps.yaml:5–14,22–23` 数据服务/API 绑定 loopback；`:48` 前端可公开；`infra/nginx.zhitu.qhhengxin.top.conf:14–15,26–28` HTTPS 跳转与证书路径。此项仅配置核读，不是远程部署安全终验。 |
| 调用统计切片 | `backend/app/modules/management/router.py:14–20` 已接真实用户和数据库；`usage.py:53–59,90–114` 缺失 usage 保留空值、汇总真实条目。没有因其存在宣称监控/settings 已实现。 |
| 品牌、历史模板/Skill、素材与播报 | 采用历史专项审查作为证据：`docs/BRAND-IDENTITY-REVIEW.md:20–48`、`docs/TASK-MATERIALS-BROADCASTS-FINAL-REVIEW.md:1`、`docs/TASK-TEMPLATE-BINDING-FINAL-REVIEW.md:1`、`docs/TASK-SKILL-BINDING-FINAL-REVIEW.md:1`；本轮没有重做全部视觉审查，不用历史结论覆盖授权入口缺陷。 |
| 生图执行与开发机隔离 | 历史 `docs/PHASE11A-PROXY-FINAL-REVIEW.md:29–42`、`docs/PHASE11A-CLOSEOUT-FINAL-REVIEW.md:1`；本次只复核 keeper 空白差异。 |
| Spec 漂移 | 根 Spec 新增品牌、路由、观测、Skill 分组、退出、身份映射均有文字依据（`:3,:159,:261,:476,:123–124`）。尚未完成 Stage 2 的完整新增 API/表/组件盘点，不给全范围“无漂移”保证。 |

完整实现：上述有直接代码/专项证据的本次修复项。部分实现：网页登录 state 有短期随机值和成功事务消费，但缺浏览器绑定、失败后一次性失效。未实现且本次阻断：这两项明确身份安全要求。未实现但不阻断本次范围：已声明后续阶段的监控/settings 和真实双端终验。

### 全 Spec 条目的处置记录

此表保证没有把未完成项隐含算成 PASS；按派发要求不重复全部历史验收。发现 HIGH 后停止推进全面集成批准，其余历史条目不是本轮新验收结论。

| 条目 | 本轮处置 |
| --- | --- |
| REQ-001 / SCOPE-001–003 / AC-001 | 三类业务沿用已交付基础；真实全部 Skill 验收仍在 Phase 14，根 DEV-PLAN 的第 7 节覆盖表。 |
| REQ-002 / SCOPE-004 / AC-002、012 | 模板与 Skill 历史绑定见上述专项报告；没有重新执行历史功能全链。 |
| REQ-003 / AC-003 | 素材、缺失输入拒绝沿用历史业务实现与全量回归；不宣称重新做人工上传。 |
| REQ-004 / SCOPE-005 / AC-004、009、010、015、016、022–025 | 历史 Phase9/11A 及观测报告保留；本次没有新的真实 CLI 故障演练。根 Product-Spec:329,334–335,341–342,350–353。 |
| REQ-005 / SCOPE-006 / AC-006、007、011、021 | 历史返工与并发验证，不重复。根 Product-Spec:331–332,336,349；docs/PHASE10-FINAL-REVIEW.md:13–18。 |
| REQ-006 / SCOPE-007 / AC-005、008、013 | 历史预览、归档和版本保护；根 Product-Spec:330,333,338；Phase11/11A 报告保留。 |
| REQ-007 / SCOPE-008–009 / AC-014、017、018 | 授权和统计已有代码；monitor/settings 与配置审计保持部分实现，不虚报完整。根 Product-Spec:339,344–345；backend/app/modules/auth/dependencies.py:22–37。 |
| REQ-008 / SCOPE-008 / AC-019、020 | 身份映射修复有代码，但 state 两项 HIGH 阻断；真实双端矩阵仍待验收。根 Product-Spec:346–347,499。 |
| 非功能、设计、部署 | 沿用根 Design-Brief:3–27 和既有专项视觉证据；备份、容量及双端上线测试仍是计划项。本次不以 commit/push 替代这些验收。 |

## 已有验证与编译证据

直接读取主 Agent 本轮日志，原始汇总如下。测试由主 Agent 执行，reviewer 没有重复整套测试。

`output/push-backend-tests.log`：

```text
540 passed, 133 skipped, 12 warnings in 49.00s
```

`output/push-frontend-tests.log`：

```text
ℹ tests 89
ℹ suites 0
ℹ pass 89
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2746.7148
```

vue-tsc：主 Agent 报告 exit 0，无 stdout/stderr；本轮 output/push-* 中没有独立类型检查日志，明确采用提供方证据。

读取此前 `output/logout-build.log:3,5,346` 的原始构建输出：

```text
vite v7.1.7 building for production...
✓ 3330 modules transformed.
✓ built in 27.70s
```

这是历史前端构建证据，不冒称 reviewer 对本 candidate 新构建。该日志包含静态/动态混合导入警告；不影响本次两个后端认证缺陷的判定。

## Stage 2：未执行

依据 code-review skill，Stage 1 存在 HIGH，停在 Stage 1。不输出质量、安全扫描、文件大小与实际邻居视觉全量 PASS。预读配置、读取历史 PASS 和主 Agent 敏感文件初扫说明不等于完成 Stage 2。主 Agent 所述私钥标记测试和空环境示例误报不提升为新问题，也不能替代剩余集成审查。

请主 Agent 修复两个 state 缺陷并增加失败回调/跨浏览器回归后重新固定 candidate，重新派发从 Stage 1 开始。不得以本报告执行 review-approve PASS。reviewer 未改业务代码、未 commit/push、未写 .needs-review、未登记批准。
