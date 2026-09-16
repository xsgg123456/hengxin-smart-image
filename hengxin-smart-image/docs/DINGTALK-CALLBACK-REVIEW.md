# 钉钉回跳登录修复独立审查

- 日期：2026-09-16。
- 最终送审 candidateId：`19ce4b273ffb68c6ecbf1afbcad51f7b39a7289065bada78ae6412072bc5cd38`。
- 初始 candidateId：`881d419891dacb2b14d21f1f49d5d65478041c38914bfa2401c42d151046f48b`；审查期间前端 message 优先级发生变更，已重新读取并复核，初始版本结论不用于批准最终版本。
- 范围：`backend/app/modules/auth/dingtalk.py` 的 exchange_auth_code、_request_json 日志；`backend/tests/test_dingtalk_auth.py`；`frontend/src/views/auth/dingtalk-login.vue` 的 callbackError 映射及 message 优先级。下文代码路径相对本报告上级项目目录。其他既有脏改动不属于本轮。
- 结论：**Stage 1 PASS；Stage 2 PASS（限定上述代码范围，无 HIGH 阻断项）**。保留下述测试盲区与快照凭据限制。此结论不是全项目验收、部署完成或真实登录端到端通过。

## 快照核对与凭据限制

已读取 `.codex/review-state.json` 中最终 candidate 的文件摘要，以下三个文件与当前内容逐一匹配（SHA256，CRLF/LF 归一）：

| 文件 | SHA256 |
| --- | --- |
| backend/app/modules/auth/dingtalk.py | c3363cfbe01cc50a56b064abb9487933e8b036dab471cbb90c5742102949b089 |
| backend/tests/test_dingtalk_auth.py | c93ce154b2d314b946062e2748d4b499e57287bde0ad8ac722f457069b60095d |
| frontend/src/views/auth/dingtalk-login.vue | 4b0d8a08e7bb38716107ab899ae0784d7a2900fae5f6024f9f60ea8fb93195ab |

最后一次 `review-status` 返回的全仓 currentId 为 `87abd7e95dbef533c88f5245e012646433c51b51fc057581be2c463869d90787`，与送审 candidate 不同。差异原因未扩大调查；三个范围内文件一致不能证明全仓一致。主 Agent 登记 review-approve 前必须解决该凭据不匹配并复核差异，不得直接将局部 PASS 当成另一全仓快照批准。本 reviewer 未执行 review-approve，未写 `.needs-review`。

## Stage 1：Spec Compliance — PASS（本轮范围）

需求依据：仓库根 `Product-Spec.md:124` 新增条款；`Product-Spec.md:495` 企业身份映射；`Product-Spec.md:497` 服务端持有凭证。逐项结果如下。

| 条目 | 结论与证据 |
| --- | --- |
| 用户授权码换用户令牌，再获取个人资料 | 完整实现。`backend/app/modules/auth/dingtalk.py:142` 换取用户令牌，`:148` 校验返回值，`:151` 对 users/me 使用 x-acs-dingtalk-access-token。`backend/tests/test_dingtalk_auth.py:78` 明确断言该请求头。 |
| unionId 经企业应用映射为企业 userId，不把 openId 当成员身份 | 完整实现。`backend/app/modules/auth/dingtalk.py:154` 要求 unionId；`:160` 取得应用令牌；`:167` 调用 getbyunionid；`:172` 读取 userid。测试 `backend/tests/test_dingtalk_auth.py:72` 特意提供不同 openId，`:83` 断言得到 member-1。 |
| 验证企业成员关系及详情一致性 | 完整实现。`backend/app/modules/auth/dingtalk.py:158` 拒绝显式 corpId 不一致，`:173` 拒绝外部联系人或缺失 userid，`:175` 查企业详情，`:180` 同时校验 userid、unionid。API 失败不签发 DingTalkMember。测试 `backend/tests/test_dingtalk_auth.py:87` 覆盖显式跨企业拒绝；详情不一致等分支缺少持久回归用例，见 Stage 2。 |
| 回调失败显示原因类别，不静默返回正常登录提示 | 完整实现已知后端错误码映射。`frontend/src/views/auth/dingtalk-login.vue:128` 解析 hash 查询；`:129` 覆盖 AUTH_PENDING、ACCOUNT_DISABLED、enterprise-mismatch、unavailable、denied；`:133` 初始化状态；`:151` 提供类别文案；`:162` 让已知回调错误优先于 configError。对接既有 `backend/app/modules/auth/router.py:78` 起的异常重定向分支。 |
| 凭证仅在服务端持有 | 范围内匹配。`backend/app/modules/auth/dingtalk.py:142`、`:160` 使用服务端配置；`:182` 返回身份对象不包含令牌。前端新增映射 `frontend/src/views/auth/dingtalk-login.vue:128` 不接收令牌或密钥。 |
| UI 与引导真实性 | 新逻辑复用既有 ElAlert 和重新授权按钮（`frontend/src/views/auth/dingtalk-login.vue:24`、`:40`、`:194`）。reviewer 本地 CUA 打开 `http://127.0.0.1:3008/#/auth/login?auth=AUTH_PENDING`，实际显示“企业身份已验证，等待超级管理员分配角色。”及“重新授权”。主 Agent 另报告 enterprise-mismatch 页面显示对应企业不匹配文案；该项标为提供方证据。 |
| Spec 漂移 | 未发现本轮新增无需求依据的页面、API、表或组件；范围内改动对应身份映射、日志及回调提示（`backend/app/modules/auth/dingtalk.py:119`、`:138`；`frontend/src/views/auth/dingtalk-login.vue:128`）。 |

完整实现：上表本轮条款。部分实现／未实现：范围内未发现。真实扫码、浏览器 Cookie、容器免登及双端完整流程属于待验收能力，不能由本轮代码 PASS 推导通过（`Product-Spec.md:499`、`:511`）。

## Stage 2：Code Quality — PASS（本轮范围）

### 安全与回归

- 未发现本轮新增硬编码生产密钥、动态代码执行、HTML 注入或拼接 SQL。对三个文件进行了危险字符串扫描；测试密钥为显式测试占位值（`backend/tests/test_dingtalk_auth.py:16`）。前端展示的是固定文案，不直接渲染 auth 参数（`frontend/src/views/auth/dingtalk-login.vue:129`、`:151`）。
- 日志不记录 token、code、请求体或 URL 查询：`backend/app/modules/auth/dingtalk.py:131` 仅输出 method 和 urlsplit(url).path，避免应用令牌查询串进入该 warning。底层异常仍以 cause 链接（`:132`）；本结论限于新增日志语句，不等同全系统日志泄漏审计。
- 身份映射失败、详情错误、身份不一致均终止认证（`backend/app/modules/auth/dingtalk.py:170`、`:178`、`:180`）；未发现本轮放宽授权或 openId 直接提权路径。
- **MEDIUM，非阻断：回归测试覆盖不足。** `backend/tests/test_dingtalk_auth.py:68` 的 mock 按顺序返回响应，只对 users/me 请求头做断言，未断言 getbyunionid 的 unionid 请求体、查询令牌及详情 userid 请求体；未覆盖 contact_type 非 0、缺失 unionId、映射错误、详情 userid/unionid 不一致及日志脱敏。应后续补充，避免错误接口参数或移除安全检查仍让现有 12 项测试通过。前端错误类别及 configError 优先级也没有本轮自动化交互回归；当前证据为代码检查和局部 CUA。
- **LOW：错误分类粒度。** `backend/app/modules/auth/dingtalk.py:170` 将所有非零映射错误归为 provider unavailable。安全上拒绝登录，但上游返回成员映射失败时可能只显示服务不可用，未区分具体成员原因。该问题不阻断当前“失败有类别提示”的修复。

### 结构、类型与视觉

- 三个文件分别为 258、137、258 行，均未超 300 行；exchange_auth_code 顺序处理令牌、映射和核验，命名对应领域含义（`backend/app/modules/auth/dingtalk.py:138`）。前端使用 LoginScenario 和 Record 类型（`frontend/src/views/auth/dingtalk-login.vue:129`）。
- Python JSON 边界仍使用 Any（`backend/app/modules/auth/dingtalk.py:119`），通过 dict/string 与业务字段校验收窄；不将此既有边界类型误报为新增前端 any。
- reviewer 已看到待授权错误页实际渲染，提示及按钮存在。继续打开既有登录基准页面时 CUA 返回 `IAB visibility is not supported in a subagent thread`，因此**邻居基准完整视觉对比未完成，不声称视觉验收通过**。本轮仅改提示映射和优先级，不改模板及样式（`frontend/src/views/auth/dingtalk-login.vue:128`、`:162`）；局部代码通过不覆盖全站视觉。

## 验证证据与原始输出

### Reviewer 独立执行：认证与会话组合测试

命令：在 backend 目录执行 `python -m pytest tests/test_dingtalk_auth.py tests/test_auth_sessions.py -q`，退出码 0。

```text
............                                                             [100%]
============================== warnings summary ===============================
tests/test_auth_sessions.py::test_server_session_cookie_authenticates_and_logout_revokes
tests/test_auth_sessions.py::test_server_session_cookie_authenticates_and_logout_revokes
tests/test_auth_sessions.py::test_server_session_cookie_authenticates_and_logout_revokes
tests/test_auth_sessions.py::test_expired_session_is_rejected
  C:\Users\EDY\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\testclient.py:455: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 4 warnings in 1.74s
```

### Reviewer 独立执行：最终前端类型检查

`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：退出码 0，stdout/stderr 为空。此检查在读取最终 message 修改后执行。

先前 `pnpm exec vue-tsc --noEmit` 未能启动检查，环境门禁原始关键输出如下；随后直接运行已安装 vue-tsc，无安装或代码修改：

```text
[ERR_PNPM_UNSUPPORTED_ENGINE] Unsupported environment (bad pnpm and/or Node.js version)
Expected version: 10.33.4
Got: 11.19.0
Expected version: 24.18.1
Got: v24.19.0
```

### 构建日志核读及提供方证据

reviewer 已读取仓库根 `output/dingtalk-callback-build.log`，原始首尾摘录：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 3330 modules transformed.
rendering chunks...
✓ built in 31.58s
```

该日志另有 dingtalk-login.vue 同时静态和动态导入的分包警告，无构建失败。上述 31.58s 日志在最终 message 补丁前读取；主 Agent 随后报告新构建也通过，但 reviewer 未重新核读新构建日志，不把旧产物认定为最终快照产物。

主 Agent 提供：VPS 真实应用凭证调用 unionId→userId 返回 errcode 0、matchesExpected true；候选已暂存 VPS 尚未生效。reviewer 未读取真实凭证、未独立重复生产 API 请求，这项属于提供方联调证据。

## 交接

本轮代码无 HIGH 阻断问题，可据此继续主 Agent 的快照核对与上线流程；不得绕过上文 currentId 不匹配。后续真实用户授权码换取、扫码回跳、Cookie 建会话及正确进入工作区仍待线上验收。reviewer 未修改业务代码、未部署、未提交。
