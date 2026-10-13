# 正式构建 CSS 热修独立审查

日期：2026-10-13。审查者：独立 code-reviewer，按 `.agents/skills/code-review/SKILL.md` 执行。

最终 candidateId：`55ae6380d4d5645d1b7ac21612719a580ad8b10fda888703350a13464b061915`。

原候选 `729fec913410cf4c2850d487704c7eea8bf5449465ef100a9ff79d3372d6d9f3` 审查中新增发布脚本适配，不能沿用旧快照批准。已读取新增 diff、复跑发布测试，并重新核对两个阶段；结束前 `review-status` 显示 currentId 与最终候选一致。

## 范围与结论

Stage 1：PASS。Stage 2：PASS。无 HIGH / MEDIUM 问题；一项 LOW 自动化建议。

范围仅为本次五个变更文件：`hengxin-smart-image/frontend/vite.config.ts`、`hengxin-smart-image/frontend/package.json`、`hengxin-smart-image/frontend/tests/built-entry-css.mjs`、`scripts/release/frontend-static.py`、`scripts/release/test_frontend_static.py`。依据 `docs/OVERSEAS-CSS-HOTFIX-20261013.md:7` 的修复与发布边界、`Product-Spec.md:961` 的复用统一登录要求、`Design-Brief.md:169` 的品牌/Art/Element 视觉要求。不是全部海外业务、真实钉钉认证或生产上线验收。

## Stage 1：Spec Compliance

| 本轮要求 | 结论及证据 |
| --- | --- |
| 正式身份入口正确加载组件 CSS | 完整实现。`frontend/vite.config.ts:70` 禁用条件折叠，保留两个预加载分支。独立执行真实 dist 入口，根路径、根 hash、业务入口、海外根页、成员页均请求 40 个 CSS；关键 IdentityPortal / BusinessEntry / OverseasShell / OverseasTasksPage 依赖均存在。断言见 `frontend/tests/built-entry-css.mjs:21`。 |
| 国内分支仍正常 | 完整实现。`frontend/src/main.ts:3` 的分流不变；实际国内入口只加载 domestic-main，4 个 CSS，含 dingtalk-login 与 domestic-main；测试 `frontend/tests/built-entry-css.mjs:22`。 |
| 保留登录及海外现有设计与权限 | 完整实现。本次 diff 没有 Vue、鉴权 API 或权限实现变化。登录尺寸来源 `frontend/src/views/auth/IdentityPortal.vue:114` 的 280px logo 和 `frontend/src/views/auth/login/style.css:5` 的 440px 表单；海外复用布局见 `frontend/src/views/overseas/OverseasShell.vue:3`、`:24`。独立目视正式产物截图，桌面左右区域、logo、侧栏、内容卡片恢复，未以 DOM 文本代替视觉判断。 |
| 登录、业务选择、海外及成员页视觉检查，含窄屏 | 完整实现。已亲自 view_image 查看 `output/css-hotfix-login.jpg`、`css-hotfix-business.jpg`、`css-hotfix-overseas.jpg`、`css-hotfix-members.jpg`、`css-hotfix-login-mobile.jpg`、`css-hotfix-overseas-mobile.jpg`。桌面 1280px 页面无横向内容裁切；390px 登录按钮完整、海外侧栏折叠、主卡片完整。业务选择按钮为既有 64px 高/20px 间距，与 `frontend/src/views/auth/BusinessEntry.vue:26` 一致。成员表头/行/分页正常。 |
| 仅发布前端，保留备份 | 发布实现符合。`scripts/release/frontend-static.py:23` 使用本次前缀；`:39`、`:71`、`:73` 校验目标 0.2.23 / 已部署 0.2.22。`:81` 建备份，`:102` 切换 HTML，`:113` 失败恢复；4 项独立测试证明正常安装不动后端/旧资产、损坏包拒绝、同名资产冲突拒绝、切换后失败回退。生产发布尚未执行，不将脚本审查写成线上成功。 |

部分实现/未实现：本次修复代码无。生产重新检查是通过审查后的交付动作，尚未验收。

Spec 漂移：无。版本升级与发布脚本适配服务于本次热修，没有新增业务页面、表、接口或角色。引导真实性：没有新增引导；现有登录操作源码未变（`IdentityPortal.vue:17`、`:75`）。

视觉边界：截图由主 Agent 从正式 dist 静态服务获取，reviewer 独立目视检查；管理员是明确的本地 fixture，不代表真实认证或生产权限验证。

## Stage 2：Code Quality

- 代码质量 PASS：变更配置只有一项 Terser compress 开关和原因注释（`frontend/vite.config.ts:70`）；新测试 30 行，单一职责；发布文件 130 行。不存在新增 any 或无关重构。官方 [Terser options](https://terser.org/docs/options/) 确认 conditionals 控制 if / 条件表达式优化；修复有效性另由真实产物红绿验证支撑。
- 测试真实性 PASS：`frontend/tests/built-entry-css.mjs:7` 从实际 index.html 定位压缩入口，`:10` 仅替换动态模块执行并移除末尾 export，真实 preload/依赖映射/分支条件仍被执行。`:23` 验证恰好一次正确入口导入，`:25` 检查文件真实存在，`:27` 检查关键 CSS。相同测试对旧产物确实失败，不是仅检查配置字符串。
- 测试边界明确：测试 DOM 的 load 事件是模拟成功，因此此用例不证明 HTTP 加载成功、完整 Vue 模块行为、网络失败恢复或 CSS 实际渲染；六张浏览器截图补充了本次渲染证据。282 项既有测试日志通过，不把它们误称为新增构建测试。
- 安全 PASS：对本次文件扫描硬编码密钥、eval、危险 HTML、前端 SECRET/TOKEN 等模式，无新增命中。`built-entry-css.mjs:19` 的 VM 只执行本地构建入口，用于测试，不进入产品；发布哈希和路径约束保持（`frontend-static.py:54`），未改动凭据或后端服务。
- 视觉对比 PASS：另外亲自打开历史品牌基准 `output/brand-production-login.png` 与海外邻居 `output/playwright/phase18/members-real.png`。当前登录图形/背景/主按钮色保持既有设计；海外左侧栏、顶部标签、白色圆角卡片、成员表格和邻居布局一致。历史截图业务菜单更多属不同阶段内容，不作为本次新增功能要求。对应复用源码 `OverseasShell.vue:17`、`:24`。
- LOW 建议：`frontend/package.json:27` 的 test 只匹配 `tests/*.test.ts`，本次 `.mjs` 仍需构建后单独执行。建议未来将 `node tests/built-entry-css.mjs` 纳入构建产物的 CI/发布检查，防止人工遗漏。本次已独立执行，不阻断热修。

## 原始验证输出

reviewer 独立执行 `node tests/built-entry-css.mjs`：

```text
PASS / 40 CSS dependencies
PASS #/ 40 CSS dependencies
PASS #/auth/business 40 CSS dependencies
PASS #/overseas 40 CSS dependencies
PASS #/overseas/admin/users 40 CSS dependencies
PASS #/api-image-edits/create 4 CSS dependencies
```

同一测试指定旧包 `../../output/css-before/frontend/dist`，按预期 exit 1：

```text
AssertionError [ERR_ASSERTION]: / missing IdentityPortal CSS
    at file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/tests/built-entry-css.mjs:27:12
```

reviewer 独立执行 `python scripts/release/test_frontend_static.py`：

```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.094s

OK
```

环境说明：曾尝试 pytest，系统 Python 返回 `No module named pytest`；此文件使用 unittest，随后直接运行成功，无需安装依赖。

主 Agent 已生成、reviewer 读取的构建原始日志 `output/overseas-css-hotfix-build.log` 尾部：

```text
dist/assets/index-OdK6Mdvs.js                                                       963.71 kB │ gzip: 307.80 kB
✓ built in 38.20s
```

类型检查原始日志 `output/overseas-css-hotfix-typecheck.log`：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.23 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

既有测试原始日志 `output/overseas-css-hotfix-tests.log`：

```text
ℹ tests 282
ℹ suites 0
ℹ pass 282
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10606.182
```

主 Agent 可仅对上述最终 candidateId 登记两阶段 PASS；本报告不写 clean、不代替生产发布后验收。
