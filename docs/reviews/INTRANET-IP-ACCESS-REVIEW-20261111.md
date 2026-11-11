# 内网 IP 直接访问适配独立审查

审查范围：`docs/INTRANET-IP-ACCESS-20261111.md` 对应的后端 HTTP 例外、Cookie、前端安全随机数/摘要/ZIP/复制兼容、部署脚本及本轮测试和构建。前次已批准快照 `c51d3871e99a71cea5ecde6f5bf1ce82eebfecac6e152047e0558493e1d97375` 的迁移工具、AGENTS 变化不重复审查。

使用 `.agents/skills/code-review/SKILL.md`。本审查不操作旧服务器，不写业务库，不执行部署，不修改实现。

## 快照与结论

- 首次 candidateId：`cd9b501d50ce7c0c7cf22b1f356c784a0b9552c4ceb303e2c9917ddd8e4f2430`。
- 审查中第一次变化：`ip_access.py:126` 的 nginx 配置预检由 `--network none` 改为 `--network host`，修正预检命名空间不含指定 LAN 地址的问题；命令仍为 `nginx -t`，没有启动 daemon。已复核中间 candidateId：`de28a6bd722c0786bcc5217f6c9ef460b6aaf7079906e546c69ed654214c0919`。
- 审查中第二次变化：Skills 下载按钮由“下载完整文件夹 ZIP”缩短为“下载 ZIP”，修复下述 MEDIUM 问题；相应组件测试和构建产物更新。
- 最终 candidateId：`8c20163fb511e67f29694b0d396198e573891ebf02eae991d67ce82fe9fc3b0d`，已用 `review-status` 独立核对当前快照一致。
- **Stage 1：PASS；Stage 2：PASS。** 适用于本轮部署前代码/配置审查；未把尚未执行的真实 OAuth、生产业务生成或实际回退验收算作通过。由主 Agent 按协议登记此 candidateId，不写 `.needs-review` clean。

## Stage 1 · Spec Compliance

| 合同条目 | 代码与验证证据 | 结论 |
| --- | --- | --- |
| 1：仅 `.245:8080` 提供 HTTP，保留公司网段、上传与 SSE 代理；内部服务继续 loopback | `scripts/migration245/ip_access.py:50` 从既有 nginx 模板派生，只变更监听/Host/转发协议；`scripts/migration245/build_edge.py:28` 保留 `192.168.1.0/24`、`192.168.2.0/23`、`deny all`、512m 上传限制、禁用请求/响应缓冲和 300s 超时。`ip_access.py:103` 起只改两个 API 挂载和环境、identity origin、web 静态目录，没有修改内部 ports。 | 代码完整；公司电脑真实 HTTP 验收属于部署后待验收项。 |
| 2：三个服务同一 origin，显式启用 RFC1918 HTTP，不切换 development | `backend/app/core/config.py:12` 明确列举 RFC1918 三段，拒绝域名/公网/loopback/链路本地/非规范 IPv4/凭据/路径/异常端口；`:59` 默认关闭；`:100` 保留生产 HTTPS 默认要求；`scripts/migration245/ip_access.py:111` 设置两个业务独立前缀及 identity 的相同 origin，不改 APP_ENV。`backend/tests/test_intranet_http.py:26` 起覆盖两个 Settings 类型及生产禁止项。 | 完整实现。 |
| 2：Cookie HttpOnly/SameSite/path/过期保留，Origin/CSRF 不放宽 | `backend/app/core/browser_auth.py:17` 原有 `X-HX-Request` 和精确 Origin 校验未改；`:42` 仅显式内网 HTTP 时移除 Secure，HttpOnly/lax/path/TTL 保留；`backend/app/identity/router.py:60` 既有 identity Cookie 按 origin 协议设置。59 项后端测试包括 Cookie 属性、往返及错误 Origin 拒绝。 | 完整实现。 |
| 2：钉钉权限、回调及验收真实性 | `backend/app/identity/router.py:65` 企业校验未改；`:89` 回调仍由配置的 public origin 派生；业务权限代码未改。合同明确真实授权前不能宣称登录验收。主 Agent 通知新增钉钉回调因账号权限暂未保存，用户已同意本轮搁置。 | 代码适配完整；新增回调与真实登录尚未完成，不能当作已通过。 |
| 3：安全 UUID、等价 SHA-256 与调用点 | `frontend/src/utils/browser-crypto.ts:2` 优先原生 UUID，回退仅用 getRandomValues 并设置 UUID v4/variant；`:14` 原生 digest 或 CryptoJS 原始字节 WordArray，无 Math.random/摘要跳过。`api/overseas/tasks.ts:104`、`views/hengxin/components/annotation/use-annotation-canvas.ts:137`、`views/overseas/admin/skill-folder-read.ts:1` 等生产调用点已替换。全 src 扫描直接 `crypto.randomUUID` 仅剩封装内原生分支；无直接 `crypto.subtle` 遗留。 | 完整实现。 |
| 3：HTTP ZIP 完整目录/空目录/二进制与逐文件摘要核验 | `frontend/src/views/overseas/admin/skill-folder-zip.ts:5` 校验路径/大小/条目限制，`:37` 添加根目录，`:40` 逐项读取冻结 release，`:44` 校验长度及 SHA-256，保留 directory entry；`:54` 构造 Blob 下载。`tests/skill-folder-zip.test.ts:24` 实际解压比较全部条目和原始二进制，不是仅判断 ZIP 文件存在。 | 完整实现。 |
| 3：仅声明已发起下载，不自动回收服务端；HTTPS 保存保留 | `frontend/src/views/overseas/admin/SkillFolderActions.vue:35` ZIP 分支成功提示“已发起”，随后 return；`:59` 删除仍只在独立二次确认 remove 流程中；`skill-folder-save.ts:66` 按目录选择器能力选择原路径，`:134` 原写入/读回核验保留。组件测试覆盖 ZIP 失败不误报、成功不调用 remove。 | 完整实现。 |
| 3：复制兼容及图片输入入口 | `frontend/src/utils/clipboard.ts:2` 原生复制或临时 textarea/execCommand，失败抛可操作提示且 finally 恢复焦点/选区；`views/codex-auth/AuthorizationDialog.vue:48`、`directives/business/highlight.ts:80` 保留手动选择反馈。`views/hengxin/components/upload-interaction.ts:1`、`UploadInteraction.vue:2` 保留 Ctrl+V/选择文件说明。 | 完整实现。 |
| 4：新服务器限定、备份、基线、最小覆盖及回退 | `scripts/migration245/ip_access.py:41` 限定 hostname/root 和 root 私有目录；`:77` 检查运行 API 源码哈希、payload 清单/哈希和既有 edge 内容；`:120` 写独立备份；`:164` 应用前再次检查配置与 payload；`:18` 固定四服务，`:186` `up -d --no-deps`；`:196` 健康失败回退。无数据库迁移、native worker 重建或旧服务器连接。 | 代码完整；运行态应用/回退未由 reviewer 执行。 |
| 4：健康、Origin、Cookie、登录跳转与页面验证 | `ip_access.py:146` 提供两业务 ready、identity config 和入口健康检查；更深的 Origin/Cookie/登录跳转验证由部署后单独进行，脚本成功输出也明确要求独立验证（`:199`）。 | 未冒称全链路验收；真实 OAuth/业务生成仍待外部授权。 |

UI 问题与修复记录：MEDIUM（已关闭），`SkillFolderActions.vue:3` 的长按钮在 1280×720 下被 `OverseasSkillCatalog.vue:54` 的操作列可视范围裁切，截图 `output/playwright/ip-access-skills-candidate.png` 可见 ZIP 最后字符不完整，而既有基准 `ip-access-skills-baseline.png` 中旧文案完整。主 Agent 已改成“下载 ZIP”，reviewer 重新打开最终构建并查看 `output/playwright/ip-access-skills-final.png`，按钮完整显示、与基准的字体/颜色/纵向间距一致；3 项 ZIP/组件测试再次独立通过。没有遗留 HIGH/MEDIUM 项，没有新增页面/API/数据库表的 Spec 漂移。新 ZIP 例外由合同第 3 条明确授权，覆盖旧文件夹下载限制；`Product-Spec.md:3`、`DEV-PLAN.md:3` 已引用合同。

## Stage 2 · Code Quality

- 代码结构与类型：新文件 `browser-crypto.ts` 22 行、`clipboard.ts` 21 行、`skill-folder-zip.ts` 61 行、`ip_access.py` 209 行，各自职责明确，未引入 any。既有调用点改动为封装导入/调用替换。依赖 `frontend/package.json:74` 与 `pnpm-lock.yaml:2142` 锁定 fflate 0.8.3。
- 安全扫描：新文件未发现 eval、innerHTML、dangerouslySetInnerHTML、前端密钥变量或硬编码服务凭证。`ip_access.py:23` 使用 argv 数组运行子进程，不用 shell；`:41` 限定目标，`:88` 校验清单，`:96` 拒绝异常路径，`:209` 不把 Docker 配置异常输出打印到终端。绝对部署路径为合同指定的新服务器目录，非泄漏用户凭据。
- 测试真实性：UUID 用例删除 randomUUID/subtle 并在调用 Math.random 时抛错；SHA-256 用 node:crypto 对空/Unicode/二进制/跨块数据作独立 oracle；ZIP 用 unzipSync 检查实际条目与字节。组件用真实 SFC 编译、注入 HTTP 能力缺失，测试错误及成功分支。后端用生产 Settings + TestClient 检查 Cookie 与 Origin 拒绝，海外前缀独立验证。
- 测试边界：`scripts/migration245/test_ip_access.py:49` 起三项覆盖准备不改在线配置、源基线不符拒绝、payload 改动拒绝。Docker 本身使用替身，不能证明真实 apply 后容器健康或失败回退成功；`ip_access.py:138` 的回退路径尚无故障注入自动化。该边界不等于发现功能缺陷，部署后的实际健康与回退证据需独立记录。
- 视觉对比：已用本地真实 Chromium 打开候选 `dist-lan-ip` 与既有 `dist`，同为 1280×720。统一登录页 Logo、双色背景、按钮、间距一致；证据 `output/playwright/ip-access-candidate.png` / `ip-access-baseline.png`。Skills 页采用相同本地模拟身份和目录响应，禁用 showDirectoryPicker 触发 HTTP 分支，发现并要求修复上述长文案裁切。未修改生产响应、未执行任何登录/删除/上传。浏览器模拟数据只证明渲染，不证明真实权限或 OAuth。

## 验证原始输出

Reviewer 独立复跑后端：

```text
...........................................................              [100%]
59 passed, 2 warnings in 1.00s
```

两条现存兼容性警告为 Starlette TestClient 使用 httpx 的弃用警告、anyio.abc.BlockingPortal alias 的弃用警告；没有失败。

Reviewer 独立复跑部署脚本：

```text
test_changed_frontend_refused_before_apply (test_ip_access.AccessPreparation.test_changed_frontend_refused_before_apply) ... ok
test_prepare_does_not_modify_live_configuration (test_ip_access.AccessPreparation.test_prepare_does_not_modify_live_configuration) ... ok
test_unexpected_live_source_refuses_prepare (test_ip_access.AccessPreparation.test_unexpected_live_source_refuses_prepare) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.116s

OK
PREPARED: payload hashes, source baseline, compose and nginx validated
PREPARED: payload hashes, source baseline, compose and nginx validated
```

Reviewer 独立复跑 UUID/摘要、复制、ZIP 与组件共 12 项：

```text
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1312.7376
```

主 Agent 提供日志，经 reviewer 读取原始输出：

```text
# output/intranet-ip-frontend-typecheck.log
> hengxin-smart-image-frontend@0.2.67 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit

# output/intranet-ip-frontend-all-tests.log
ℹ tests 541
ℹ suites 0
ℹ pass 541
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 18152.0624

# output/intranet-ip-frontend-build.log（初始候选）
🚀 API_URL = /api/v1
🚀 VERSION = 0.2.67-lan.1
vite v7.1.7 building for production...
transforming...
✓ 4830 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 54.46s
```

构建/测试命令还输出 pnpm package.json 中 pnpm.overrides/onlyBuiltDependencies 被忽略的提示；本轮未改这些配置，不把现存工具提示归为此次新增缺陷。主 Agent 报告目标机 prepare 已完成 payload/运行基线/compose/nginx 检查；reviewer 未独立连接服务器，因此只将其视为交接证据，不冒充独立实测。

最终文案修复后重建输出与 reviewer 独立定向复测：

```text
# output/intranet-ip-frontend-build.log（最终候选）
✓ built in 46.15s

✔ HTTP ZIP 解压保持完整根目录、空目录、Unicode名称和全部原始字节 (60.284ms)
✔ ZIP 拒绝损坏内容、网络中断、危险路径和过量数据，不产生成功文件 (11.2515ms)
✔ HTTP 真实保存组件使用 ZIP，成功仅告知已发起下载，失败不误报和不删除远端 (158.7037ms)
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1148.3371
```
