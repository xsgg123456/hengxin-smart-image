# 国内入口菜单模式修正增量审查 · 2026-11-11

- candidateId：`56a094272e2962b4fd4fb0392dcef56b2de1b5abd583065559c3405194d9b461`。
- 批准基准：`1727aa01ca08192c1d0da00cee2abb1bfa7cf16104447c0c21efca05f4fd08da`；未变化内容沿用 `docs/reviews/INTRANET-IP-RELOAD-REVIEW-20261111.md` 及其引用报告。
- 审查范围：新增 `hengxin-smart-image/scripts/migration245/build_lan_frontend.ps1`、重建的 `hengxin-smart-image/frontend/dist-lan-ip/`，以及菜单模式对既有路由/真实身份的作用。源合同为 `Product-Spec.md:3` 引用的 `docs/INTRANET-IP-ACCESS-20261111.md:39`。
- 使用 `.agents/skills/code-review/SKILL.md`。只读审查实现，独立运行类型检查与产物完整性核对；未部署、未连接服务器、未执行真实登录后的业务操作。
- **Stage 1：PASS；Stage 2：PASS（本次构建修正范围）。** 无 HIGH/MEDIUM 缺陷。此结论不等于线上 `#/500` 已消失或全部真实业务验收通过；部署后浏览器检查仍由主 Agent 完成。

## 快照核对

开始与结束时 `review-status` 的 currentId 均等于送审 candidate。相对基准共 880 个变化路径，其中 879 个是构建产物的新增/删除/变化，唯一源码增量为构建脚本，没有业务源码变化。末次核验原始精简输出：

```json
{"currentId":"56a094272e2962b4fd4fb0392dcef56b2de1b5abd583065559c3405194d9b461","reviewedId":"1727aa01ca08192c1d0da00cee2abb1bfa7cf16104447c0c21efca05f4fd08da","changedCount":880,"sourceChanges":["hengxin-smart-image/scripts/migration245/build_lan_frontend.ps1"]}
```

## Stage 1 · Spec Compliance

下表 F 表示 `hengxin-smart-image/frontend/`，S 表示 `hengxin-smart-image/scripts/migration245/`。

| 合同条目 | 实现及证据 | 结论 |
| --- | --- | --- |
| 国内入口使用既有前端菜单模式 | `S/build_lan_frontend.ps1:7` 固定 frontend；`F/.env.example:4` 和 `F/vite.config.ts:19` 均为该默认值。`F/src/router/core/MenuProcessor.ts:26` 选择本地路由，`:49` 按角色递归过滤；仅另一路径 `:60` 调用模板菜单 API，地址来自 `F/src/api/system-manage.ts:23`。 | 完整实现，PASS |
| 实际产物已切换模式 | `F/dist-lan-ip/assets/prototype-DOKMvxel.js:55` 包含 `function sR(){const e="frontend";return{isFrontendMode:da(()=>!0),isBackendMode:da(()=>!1),currentMode:da(()=>e)}}`；同一行 getMenuList 确实读取 sR().isFrontendMode 决定执行 processFrontendMenu。不是只检查脚本文字。 | PASS |
| 版本、入口和 API 前缀 | `S/build_lan_frontend.ps1:1`、`:8`、`:9` 为 `0.2.67-lan.2`、`/api/v1`、`/`；产物 `prototype-DOKMvxel.js:55` 的 CURRENT_VERSION 和 VITE_API_URL 对应一致。`F/dist-lan-ip/index.html:43` 引用入口脚本存在，所有 4 项本地 HTML 引用存在。 | 完整实现，PASS |
| 保留真实身份与权限 | `S/build_lan_frontend.ps1:23` 仍用 production。`F/src/api/hengxin/client.ts:7`、`:19` 在 production 使用真实 HTTP；`F/src/api/auth.ts:7`、`:8` 读取后端用户并拒绝非 active/无角色身份；`F/src/router/guards/beforeEach.ts:185` 先加载用户。后端 `hengxin-smart-image/backend/app/modules/auth/permissions.py:13`、`:22` 独立依赖真实用户并校验权限，快照无后端增量。 | 无鉴权降级，PASS |
| 原合同 1：内网入口、网段、上传/SSE 和 loopback | 仅新增构建脚本，`S/build_lan_frontend.ps1:23` 仅写本地 dist；既有代理及服务配置无增量。 | 沿用已批准基准 |
| 原合同 2：origin、Cookie、钉钉与 CSRF | 上述快照核对无相关源代码变化；本轮 frontend 模式不改身份服务。合同 `docs/INTRANET-IP-ACCESS-20261111.md:41` 将用户登录成功描述为反馈，不作为 reviewer 的实测结果。 | 无增量偏差 |
| 原合同 3：HTTP 随机数、摘要、ZIP 和复制 | 快照无这些业务源文件增量，构建类型检查通过；已批准 ACCESS 报告的实现结论沿用。 | 无增量偏差 |
| 原合同 4：最小覆盖、回退及真实验收 | `S/build_lan_frontend.ps1:21` 至 `:24` 只做检查和本地构建，没有部署/删除后端数据行为。实际切换、回退包和登录后页面验证属于 `docs/INTRANET-IP-ACCESS-20261111.md:43` 的后续步骤。 | 本地交付完整；部署验收待执行 |
| 引导真实性、UI、Spec 漂移 | `S/build_lan_frontend.ps1:1` 至 `:30` 不新增页面、提示、API 或表；本次恢复原路由选择配置。 | 无新增漂移 |

## Stage 2 · Code Quality

- **质量 PASS**：脚本共 30 行，职责限定构建；`S/build_lan_frontend.ps1:22`、`:24` 检查原生命令退出码，`:25` 至 `:29` 在成功/失败后恢复进程环境与工作目录。不使用字符串拼接执行命令。
- **安全 PASS**：`S/build_lan_frontend.ps1:5` 至 `:9` 暴露到 Vite 的仅公开版本/模式/路径，扫描未发现密钥、Token、密码、eval 或 Invoke-Expression；没有服务器操作和数据删除。模板 `useAuth` 也读取该模式（`F/src/hooks/core/useAuth.ts:63`），核查国内/海外业务视图无 useAuth/v-auth 使用；本轮没有改变后端权限实现。
- **产物完整性 PASS**：独立核对 1,572 个静态模块引用，缺失为 0；80 个 gzip 文件逐个解压与未压缩文件比较，差异为 0。证据源为 `F/dist-lan-ip/index.html:43` 及其 JS 依赖集合。
- **测试真实性**：reviewer 独立 `pnpm exec vue-tsc --noEmit` 退出 0；没有把编译、产物检查或用户反馈当作已登录浏览器通过。尚未验证的故障路径是线上部署后不再请求模板菜单、国内导航恢复；明确留给后续验收。
- **视觉比较边界**：本次无布局/样式/组件源码变化，沿用已批准基准的视觉结论；本 reviewer 未打开登录后的页面，没有宣称新增实际渲染对比通过。国内页面可达性由部署后普通浏览器复测决定。

## 原始验证输出

独立类型检查原始输出（后续进程退出码 0，无其它输出）：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

主 Agent 构建原始日志摘录，完整文件 `output/intranet-ip-frontend-menu-fix-build.log:1`；reviewer 已核对日志和实际产物，不重复覆盖构建目录：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = 0.2.67-lan.2
vite v7.1.7 building for production...
transforming...
✓ 4830 modules transformed.
rendering chunks...
computing gzip size...
```

日志末行：

```text
✓ built in 45.07s
```

独立产物核对原始输出：

```json
{"moduleReferencesChecked": 1572, "missing": [], "gzipChecked": 80, "gzipMismatch": []}
```

已有 pnpm 配置告警不影响本次类型检查/构建退出成功，但不能将这些配置描述为已经生效。报告仅批准上述同一候选快照的增量两阶段审查；由主 Agent 按协议登记，不向 `.needs-review` 写 clean。
