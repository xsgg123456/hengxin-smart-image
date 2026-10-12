# Phase 17 独立两阶段审查（2026-10-12）

- 初始 candidateId：`5db370b8893169c84d5230da07c0e106e7dc54635345f1f2916eb3a08e9c505a`。
- 最终 candidateId：`33d8fc0bc27548f2806c57cd747579570b78c5e12c2320f69e362812b98b07e8`。本报告 Stage 1 PASS、Stage 2 PASS 均对应此最终快照。
- 审查角色：独立 code-reviewer；只读实现与测试，仅写本报告，未修复、未提交、未登记批准。
- 来源：`DEV-PLAN.md:74`、`Product-Spec.md:956`、`docs/OVERSEAS-PHASE17-CONTRACT.md:1`、`Design-Brief.md`、`docs/OVERSEAS-PHASE17-RUNBOOK.md:1`。
- 范围：Phase 17 身份服务、公共会话原语、国内身份桥、海外成员/会话与两项迁移、独立服务配置/联调工具、正式登录/双入口/退出及相关测试。既有海外模拟业务、旧预览、既有 Skill 改动不冒充本 Phase 新交付；共享 BusinessEntry、入口与预览兼容性纳入检查。
- 本文路径中的 `backend/`、`frontend/`、`infra/` 均相对仓库内 `hengxin-smart-image/`。

## Stage 1：Spec Compliance

**结论：PASS。完整实现下列本阶段条目；部分实现、未实现、HIGH 问题均为 0。** 后续任务/管理功能属于 Phase 18–25，不计为当前缺陷。

| 合同条目 | 结论与代码证据 | 验证证据 |
|---|---|---|
| 17.1：一次钉钉身份，复用企业验证，脱离国内角色 | 完整。`backend/app/identity/router.py:60,105,116` 调既有 provider；`backend/app/modules/auth/dingtalk.py:241` 将国内持久化延迟委托到 `dingtalk_members.py:42` | `backend/tests/test_identity_client.py:66` 在独立进程检查身份入口不加载国内 ORM/DB；真实四授权组合见集成记录第18行 |
| 独立 Redis 身份服务，不连接业务资源 | 完整。`backend/app/identity/config.py:7` 独立前缀且不读 env 文件；`main.py:12` 只创建 Redis；`infra/compose.identity.yaml:20` 身份 API 不注入业务库/存储凭据 | 上述独立进程测试及 `infra/identity-test/checks.py:216` 三进程、两库迁移实测 |
| 身份 cookie 与 OAuth 浏览器绑定 | 完整。`backend/app/identity/router.py:54,94`：HttpOnly、Lax、HTTPS Secure、限定 Path；state 对比且先消费再换码 | `backend/tests/test_identity_service.py:52,120,165` 检查 cookie、跨浏览器拒绝、失败消费、成功及重放 |
| 60秒 audience ticket，一次性、防重放/篡改/跨业务 | 完整。`backend/app/identity/store.py:57` 按 business 分键并哈希；`:64` Redis GETDEL 原子消费；`router.py:41` 密钥决定业务 | `backend/tests/test_identity_service.py:73` 8并发仅1成功；`:105,179` TTL/实际到期；真实 HTTP 测试 `infra/identity-test/checks.py:131` |
| 17.2：独立海外成员、pending、五角色基础 | 完整。`backend/app/overseas/auth/models.py:11,14,29` 独立元数据、多角色约束；`identity.py:8` 只登记 pending；不读国内管理员配置 | `backend/tests/test_overseas_auth.py:95,103,113` 待授权/禁用/无角色均拒绝，国内管理员变量不提权，伪造角色422 |
| 独立业务 cookie/token/hash，不相信国内cookie | 完整。`backend/app/identity/session_records.py:8` 随机token只存哈希；`backend/app/overseas/auth/sessions.py:6` 独立cookie/path；`dependencies.py:22` 只查海外会话 | `backend/tests/test_overseas_auth.py:75,113`；真实 HTTP 将对方token改成目标cookie名仍401，集成记录第20行 |
| TTL、每请求成员启停/角色与上游身份校验 | 完整。`backend/app/identity/session_records.py:10` 取寿命最小值；`backend/app/core/browser_auth.py:31` 上游检查；海外 `dependencies.py:26` 本地状态与角色检查；国内 `auth/dependencies.py:28` 同样绑定 | `backend/tests/test_overseas_auth.py:122,136`；国内桥测试第44行；集成记录第24–25行，身份服务停止两边503 |
| 全局撤销、单业务退出、单边停用互不混淆 | 完整。`backend/app/identity/store.py:49` 删除共同身份；海外 `router.py:53` 仅撤本业务；`core/browser_auth.py:37` 不信客户端撤销状态 | `backend/tests/test_identity_service.py:91`；`test_overseas_auth.py:149`；真实单边停用国内仍200、全局退出双401（集成记录第21–22行） |
| 换身份即撤销旧业务cookie，包括新身份未授权 | 完整。国内 `identity_bridge.py:20`、海外 `router.py:32` 有效兑换后撤旧会话，pending分支提交撤销 | `test_business_identity_bridge.py:94`、`test_overseas_auth.py:162`；集成记录第44行附加真实HTTP，保留旧统一身份有效作对照，排除假阳性 |
| 同源头、独立服务密钥、内部接口不公网转发 | 完整。`backend/app/core/browser_auth.py:16`、身份 `router.py:32,41`；业务请求多余角色字段被拒绝 | `test_identity_service.py:138`；集成记录第43行真实错误Origin403且未消费ticket；`docs/OVERSEAS-PHASE17-RUNBOOK.md:30` 公网仅指定路径，明确不转发internal。部署配置尚未生产验收 |
| 国内legacy兼容 | 完整。`backend/app/core/browser_auth.py:32` 仅无绑定旧会话走兼容；国内 `dingtalk_members.py:42` 保留原角色映射；`migrations/versions/0027_identity_session_binding.py:14` nullable增量列 | `test_business_identity_bridge.py:57`：上游撤销后绑定会话401、旧会话200；最终全量后端1732通过 |
| 17.3：双入口四种组合、403禁用、故障重试、401重登 | 完整。`frontend/src/api/identity/auth.ts:18` 区分401/403/故障；`BusinessEntry.vue:6,19` 禁用与原因；`IdentityPortal.vue:47` 统一加载 | `frontend/tests/unified-identity.test.ts:6` 四组合；真实浏览器四组合；reviewer独立重跑故障脚本PASS |
| 海外单授权不启动国内bootstrap；原国内启动链保留 | 完整。`frontend/src/main.ts:1` 按入口动态加载，`identity-main.ts:1` 不引国内启动链，`IdentityPortal.vue:70,83` 明确进入国内才导航 | `frontend/tests/unified-identity-real.browser.mjs:29` 不出现国内me/workspace请求；故障脚本同样断言无国内me |
| 正式海外仅真实身份，预览独立 | 完整。`IdentityPortal.vue:13` 仅姓名/角色/切换/退出；无模拟角色输入与任务模块；海外 `main.py:28` 仅health/auth路由 | 真实浏览器第37行拒绝出现模拟“提交图需”；既有预览5+4+5组回归全部通过 |
| 退出顺序与失败提示、已有会话 | 完整。`frontend/src/api/identity/auth.ts:29` 先撤统一身份再两业务清理；`IdentityPortal.vue:90` 清访问状态、错误可重试；`HengxinLogout.vue:18` 仅404进入legacy路径 | 单测退出故障与部分失败；故障浏览器先503退出失败且未提前清业务，重试成功；国内旧会话有“重新连接”入口 |
| UI与引导真实性 | 完整。复用 LoginLeftView、AuthTopBar、品牌SVG与登录样式：`IdentityPortal.vue:2,32,106`；双入口不出现死任务引导 | reviewer打开正式页面与3012既有预览实际对比，见下节截图；身份页与业务切换/退出路径均有对应处理 |

Spec 漂移：未发现本 Phase 新增超范围业务。角色/成员表是合同明确的 Phase18 基础；无管理授权接口或海外自动管理员。国内既有管理员语义保留不构成海外提权（`backend/app/modules/auth/dingtalk_members.py:53` 与海外 `identity.py:17` 对照）。

## Stage 2：Code Quality

**结论：PASS。未发现需修复的 HIGH/MEDIUM 问题。**

- 结构和复用：token/hash/expiry、会话CRUD、浏览器验证、钉钉provider分别保持单份。业务依赖注入各自模型，身份进程没有业务ORM依赖；证据 `backend/app/identity/session_records.py:8`、`tokens.py:7`、`core/browser_auth.py:16`、`modules/auth/dingtalk.py:241`。
- 文件和类型：本 Phase 新文件均不超过300行；最大联调文件 `infra/identity-test/checks.py` 259行，`IdentityPortal.vue` 111行。新前端API使用unknown与运行时guard，未新增any；`frontend/src/api/identity/request.ts:4,13`、`auth.ts:11`。既有大型文件不因本次局部改动冒充新拆分目标。
- 安全扫描：本次新增身份目录、海外auth及前端身份代码未命中eval、innerHTML、dangerouslySetInnerHTML、VITE密钥变量、真实key前缀。服务密钥仅后端配置，repr隐藏；`backend/app/identity/config.py:10`。provider日志已去掉原始错误body；`modules/auth/dingtalk.py:124`。测试固定密码只存在临时隔离拓扑 `infra/identity-test/run.py:39`，与真实运行配置分离。
- 输入与失败关闭：未知/错误成员profile、无时区/过期expiry、非布尔active不放行；`backend/app/identity/schemas.py:6,22`、`client.py:30,38` 与 `tests/test_identity_client.py:24,40,53`。UI网络错误不按403处理；`frontend/src/api/identity/auth.ts:23`。
- 原子性与退出：Redis GETDEL证明ticket并发只一次；海外首次成员绑定有唯一约束与savepoint竞争恢复（`backend/app/overseas/auth/identity.py:9`）；每个受保护请求查询本地与身份有效性，晚到cookie仍不能绕过已撤销身份（`core/browser_auth.py:31`）。前端load代次检查和busy禁用阻止旧业务权限响应开启按钮（`IdentityPortal.vue:43,48,57,60`）；未将前端缓存视为授权依据。
- 测试真实性：单测中的provider替身、HTTP故障注入明确标注；四组合的权限由隔离数据库seed决定，真实浏览器没有拦截业务API（`frontend/tests/unified-identity-real.browser.mjs:14`；`infra/identity-test/checks.py:50`）。ticket过期包括Redis实际到期；旧cookie撤销补测保留原身份仍200，故不能用“上游已撤销”伪造本地撤销通过（集成记录第44行）。
- 视觉对比：reviewer在1280×720实际打开正式入口与既有海外预览邻居。截图 `output/playwright/p17-review-entry.png`、`output/playwright/p17-review-neighbor.png`。品牌宽280px、右侧按钮宽440px/高64px、按钮间20px、同左侧插画/页头；对应 `IdentityPortal.vue:107`、`BusinessEntry.vue:26`。正式页显示真实允许状态；邻居截图的海外按钮当时处于hover，颜色差异不判为静态规范差异。测试mock仅用于该视觉对比，不充当真实身份验收。3014测试服务与独立浏览器已关闭，既有3012保留。

## 编译与验证原始输出

已阅读全量日志；未将旧失败日志当最终结果。最终后端无本 Phase 测试跳过，17项跳过为既有Linux root/WSL/Bubblewrap环境要求。

`output/overseas-phase17-backend-final.log`：

```text
1732 passed, 17 skipped, 15 warnings in 325.61s (0:05:25)
```

`output/overseas-phase17-frontend-final-test.log`：

```text
ℹ tests 258
ℹ suites 0
ℹ pass 258
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 7333.0089
```

`output/overseas-phase17-frontend-final-build.log`：

```text
> vue-tsc --noEmit && vite build
✓ built in 36.82s
```

镜像首次编译原始输出（原 `output/overseas-phase17-build.log`；该文件现为最终缓存复跑日志，见末尾补充复核）：

```text
#14 naming to docker.io/library/hengxin-smart-image-backend:phase17 done
#14 unpacking to docker.io/library/hengxin-smart-image-backend:phase17 1.6s done
#14 DONE 7.2s
```

reviewer独立运行 `node tests/unified-identity-faults.browser.mjs`，退出码0：

```text
PASS：503可重试、403禁用、海外身份页、统一退出故障重试、国内bootstrap隔离
```

真实API及浏览器最新版复验、清理记录见 `docs/OVERSEAS-PHASE17-INTEGRATION.md:35`；旧预览回归日志 `output/overseas-phase17-preview-regression.log`、`output/overseas-phase17-shell-regression.log`、`output/overseas-phase17-admin-regression.log`。`git diff --check` 退出码0。

## 审查边界与快照

此次通过是本地 Phase17 身份合同通过，不代表真实钉钉配置、生产代理/迁移/部署或后续业务功能验收。生产内部路由隔离仍须按runbook实施验证，不能以本地测试替代。未访问生产或收费服务。

审查中 Vite 按访问页面扫描裁剪 `frontend/src/types/import/components.d.ts`。主 Agent 最终补回41行既有组件声明；reviewer复查该文件与HEAD无差异，内容为既有类型声明，未改变运行逻辑。其余已审实现保持不变；重新核对 `review-status` 当前ID为上列最终candidateId。最终类型检查再次退出0，`output/overseas-phase17-typecheck-final.log` 原始输出：

```text
> hengxin-smart-image-frontend@0.2.21 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

此次生成声明差异复核通过，两阶段PASS绑定最终快照。由主 Agent 使用该candidateId及本报告路径执行review-approve；reviewer未写 `.needs-review`，未自行批准或提交代码。

## EOF 清理最终差异复核（独立 reviewer，2026-10-12）

- 基线：已批准 `8a944966950dc34cafdb35e7b68c0d1f8c93c10a75761bcb34e24c80a46cc948`；本次候选：`33d8fc0bc27548f2806c57cd747579570b78c5e12c2320f69e362812b98b07e8`。
- 范围：仅 `frontend/tests/unified-identity-faults.browser.mjs:45` 与 `frontend/tests/unified-identity-real.browser.mjs:50` 最后一个语句之后各删一行空行。独立执行 review-status 确认相对批准快照只这两文件变化；以 SHA-256 核对索引内容确实等于批准快照，并逐字节断言旧文件 = 新文件 + 一个换行（统一 CRLF/LF），最终正常结尾换行保留。其他未暂存差异是基线已有内容，不能将整个 git diff 误认为此次新增差异。

### Stage 1：PASS

本次逐项继承上文16行合同检查的实现与验证证据：钉钉复用、独立Redis、身份cookie/OAuth、一次性ticket、独立成员、业务cookie、TTL/上游校验、退出撤销、换身份撤旧cookie、同源/内部密钥、legacy兼容、四授权与故障状态、bootstrap隔离、正式/预览隔离、退出重试、UI引导，均无实现内容变化。前13及第15项相关测试的语句和断言逐字节保留；第14及第16项页面内容与样式的快照哈希不变。完整实现结论保持，部分实现、未实现、HIGH问题仍为0；无新增API/页面/角色/业务逻辑，Spec漂移仍为0。具体代码行号及原验证方式沿用上文对应表格，两个测试正文行号也未偏移。

### Stage 2：PASS

逐项继承上文结构复用、文件类型、安全扫描、输入失败关闭、原子性退出、测试真实性、视觉对比的证据。两处删除均在已闭合的 finally 语句后（上述两文件第45、50行），不存在模板字符串或注释内容变更；文件缩为45/50行，没有新增密钥、危险函数或断言变更。所有生产代码及视觉资源快照保持，原截图与测试前提继续适用。本次未重跑全量测试或重新打开页面，不把继承证据写成本次执行；限定文件 `git diff --check` 独立执行退出0、无输出。未发现HIGH/MEDIUM问题。

### 编译证据修订与交接

最终缓存复跑由主Agent执行并报告退出0；reviewer读取当前 `output/overseas-phase17-build.log`，确认缓存命中且成功导出同名镜像，原始输出如下（与上文首次构建耗时分开记录）：

```text
#8 [stage-1 6/7] COPY backend/ ./
#8 CACHED
#14 naming to docker.io/library/hengxin-smart-image-backend:phase17 done
#14 unpacking to docker.io/library/hengxin-smart-image-backend:phase17 0.0s done
#14 DONE 0.1s
```

两阶段PASS绑定本节候选及报告顶部最终candidateId。DEV-PLAN与验证说明的Markdown更新不属于代码快照，不将其当作功能实现变化；原本地/生产验收边界不变。reviewer仅更新报告，没有修改实现、暂存、提交、写clean或执行review-approve；主Agent仍须按最终candidateId登记批准并重新暂存这两个清理后的文件。
