# Phase11A 基础设施与开发代理完整候选独立审查

日期：2026-09-11。最终 candidateId：`8ca7678d3a1ab9b4ce70eba69d5a7d7261e21d0ea2f3e81a3a98305430fb14e6`。

**Stage 1：PASS；Stage 2：PASS。覆盖 review-status 列出的全部 14 项当前受控变化，未发现需修复缺陷。** 仅为基础设施/代理候选的代码审查通过；完整 Phase11A 业务验收仍未通过。reviewer 不登记凭据，由主 Agent 在快照仍匹配时执行 review-approve。

## 方法与候选连续性

已读取 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`.codex/agents/code-reviewer.toml`、Product-Spec 第8.3节、DEV-PLAN Phase11A 原文及当前运行说明。执行顺序：确认候选和全部文件范围；对照需求检查实现；检查安全、故障路径与测试真实性；运行无服务副作用的验证；复核快照并写报告。每一步完成标准为可定位的代码或执行证据。

开始候选为 `67610be32f850c42ab080cb4520257c79441fff0445b442e12537849ba3b3c4e`，已直接读取全部新文件及两个已跟踪文件的 diff，没有用旧报告替代当前文件审查。期间发现 currentId 变化并立即告知主侧；主侧确认 devserver 重生成类型声明，重新 prepare，要求审查新候选。

对新声明文件全文及 diff 从 Stage 1 重新核对后，用 harness 的 `snapshot/identity/digest` 在内存重建旧声明（仅插回 ElUpload 一行），得到：

```text
currentId: 8ca7678d3a1ab9b4ce70eba69d5a7d7261e21d0ea2f3e81a3a98305430fb14e6
restoring only ElUpload gives: 67610be32f850c42ab080cb4520257c79441fff0445b442e12537849ba3b3c4e
PASS: sole snapshot delta is deleted ElUpload type declaration; all other controlled hashes identical
```

没有写回重建内容。该检查证明所有其它受控文件哈希未变，因此既有本轮直接审查及后端测试仍适用。旧 INFRA/PROXY 报告只作历史背景，不用其不同候选结论批准本候选。

## 全部14项范围及检查结果

除前两项外，路径相对于业务子目录 `hengxin-smart-image/`。以下均为本轮实际读取的当前文件或 diff。

| 文件及行号 | 核对结果 |
| --- | --- |
| 根 `.codegraph/.gitignore:1–16` | PASS：仅本地数据库/WAL/SHM、缓存、日志及 dirty 标记忽略规则，无运行时行为。 |
| 根 `.cursor/rules/codegraph.mdc:1–39` | PASS：工具使用及初始化说明，与给定 CodeGraph 规则一致，无自动执行或生产配置改动。 |
| `backend/app/execution/workspace.py:49–85` | PASS：开发代理白名单、大小写变量、clearenv 和原有隔离参数核对完成。相对 HEAD 仅增加 urlsplit 导入与代理段。 |
| `backend/tests/test_execution_proxy.py:9–49` | PASS：显式代理、宿主普通代理/SECRET 不传递、非法端点和生产拒绝；实际调用命令构建器。 |
| `backend/tests/test_local_codex.py:16–55` | PASS：非生产配置、执行器选择、连接与密码字面量编码、缺失/裸键/空值三例。 |
| `backend/tests/test_local_codex_control.py:23–286` | PASS：项目/环境边界、SQL全非终态、排空竞争、失败关闭、重启次序、unit拒绝覆盖、keeper外部复用和PID变化拒绝。 |
| `backend/tests/test_local_codex_ports.py:9–51` | PASS：实际 inspect/端口检查函数，覆盖正确绑定、同标签同密码但错误端口、缺失及非loopback绑定。 |
| `frontend/src/types/import/components.d.ts:1–131` | PASS：全文与最新diff核对，仅删部分 Element Plus 类型声明；最新增量是 ElUpload 删除。`frontend/tsconfig.json:16–20` 已启用 element-plus/global；无运行时组件或UI实现删除。 |
| `infra/.env.local-codex.example:1–12` | PASS：独立auth/execution/skill路径、固定CLI路径、明确节点/Redis端口，代理默认空，无真实凭据。 |
| `infra/compose.local-codex.yaml:1–15` | PASS：Redis仅loopback发布，API/Outbox关闭fixture并启用真实CLI配置；与当前基础compose合并关系核对完成。 |
| `infra/local_codex_control.py:1–278` | PASS：五种动作、显式项目和文件归属、连接端口、全非终态门禁、排空二查、restart和定向ping、失败关闭与fixture恢复。 |
| `infra/local_codex_keeper.py:20–93` | PASS：身份和所有权校验，安全复用外部keeper，持有句柄并二次核对后才终止自有进程，避免PID复用误杀。 |
| `infra/local_codex_worker.py:12–85` | PASS：显式配置、空代理清除、非root Linux、固定版本/认证/实际沙箱检查，独立Worker启动。 |
| `infra/start_local_codex.ps1:1–15` | PASS：参数约束及数组调用，无拼接shell字符串；PowerShell解析0错误。 |

## Stage 1：需求符合性

| 本轮要求 | 证据与结论 |
| --- | --- |
| Windows check/start/stop/fixture/status及非生产项目限制 | 完整实现：control.py:26–48,90–108,190–245,248–264，入口ps1:1–15。项目必须hx-local-*且排除prod；配置位于本infra；容器标签、工作目录、compose路径及APP_ENV核对，固定本机Docker context。 |
| 保护所有非终态任务，API排空后二次查库 | 完整实现：control.py:19–23,123–126,184–188,210–222。job和round包括NULL及未知非终态均拒绝；先停API等待退出，再查库；发现竞争只恢复原API，未切换消费者。对应测试control:60–69,132–147。 |
| PG/MinIO/Redis端口必须对应实际服务 | 完整实现：control.py:109–117,225–227；PG/MinIO在切换前核对，Redis在Worker restart前核对。严格要求唯一运行服务及指定127.0.0.1绑定。ports测试覆盖真实校验函数。 |
| 重复start重载并就绪后开放API | 完整实现：control.py:168–182,224–231；使用restart而非start，Worker初始化读取配置；定向节点pong后启Outbox/API。主侧现场两次start的MainPID 2512→2787支持该行为。 |
| 消费者隔离、停止、fixture恢复、保留数据 | 完整实现：control.py:206–244，先停旧消费者再切换；fixture先停WSL；中途失败保持入口关闭；无down/卷删除/历史来源改写。对应测试control:149–175。 |
| keeper只管理自有进程及PID复用防护 | 完整实现：keeper.py:44–78比较完整身份与owner；OpenProcess后再次核对身份，按句柄终止；:79–93外部保活复用但owner为空。真实Win32终止竞态的自动测试边界见后文。 |
| 固定CLI、登录和真实bubblewrap预检，独立认证/会话 | 完整实现：worker.py:43–71核对文件、settings版本、login status、实际prepare_workspace/sandbox_command；Settings.codex_version默认0.153.4，样例固定对应路径。workspace.py:18–46按任务分home、按轮次分work/control，复制所需auth而非桌面完整CODEX_HOME。 |
| 显式代理仅test/development、无认证loopback HTTP(S) | 完整实现：workspace.py:62–74限制scheme、hostname、端口、认证、路径/query/fragment及空白；只增加六个大小写代理变量；:56–61保留clearenv，不传宿主其它环境。 |
| 空代理清除宿主遗留值 | 完整实现：worker.py:26采用local.get(...) or ''，:34不再过滤该字段，:49环境更新覆盖旧值；独立环境合并复现全部通过。 |

没有新增页面、业务API或表，没有发现本轮未经授权的产品范围扩展；类型声明变化不影响页面渲染，视觉对比不适用。WSL镜像网络/autoProxy是用户授权的机器配置，不属于受控14文件；网络现场证据来源明确如下。

完整Phase11A只部分完成：本候选对应环境接入与代理基础设施；真实业务新图、同会话整套/单张返工、下载归档、双任务并行及资源/故障验收尚未齐备，不将未来验收缺口列成本轮代理缺陷。

## Stage 2：缺陷关闭、质量与安全

前轮代理F-01关闭。使用真实configuration读取临时dotenv，再合并预置宿主代理的环境字典，独立输出：

```text
missing: mapped='' effective=''
LOCAL_CODEX_PROXY_URL: mapped='' effective=''
LOCAL_CODEX_PROXY_URL=: mapped='' effective=''
LOCAL_CODEX_PROXY_URL=http://127.0.0.1:7890: mapped='http://127.0.0.1:7890' effective='http://127.0.0.1:7890'
```

三项回归并非只检查dotenv默认值，而调用真实Worker配置函数，断言返回字典必须含空字符串。本次额外验证补足环境合并环节。Windows控制器configuration:35会拒绝裸键；直接Worker入口仍需本修复，现已正确覆盖。

前轮基础设施端口与重复start缺陷，经当前代码及对应测试重新检查均关闭；没有依赖旧文件未变的假设。范围内Python文件均低于300行（最长测试286行、控制器278行），控制器、keeper、Worker职责分开。数据库密码URL编码、dotenv关闭插值、子进程错误不回显凭据，unit路径转义及已有unit完整内容/位置/drop-in检查保留。固定空闲SQL不拼接业务输入；没有新增eval、动态业务SQL、前端密钥或任意shell执行。安全文本扫描所列危险模式无命中；样例凭据为空，测试密码是明确测试数据。

测试真实性边界：控制状态机模拟Docker/WSL；SQLite执行真实空闲SQL可验证状态集合但不证明PostgreSQL事务竞争。keeper的外部/复用拒绝有自动测试，Win32自有进程创建/终止竞态未由reviewer实机覆盖。没有把这些模拟用例描述成现场服务验收。

## 验证结果及来源

reviewer独立执行，禁用字节码与pytest缓存，不操作服务：

```text
python -m pytest tests/test_execution_proxy.py tests/test_execution_workspace.py tests/test_local_codex.py tests/test_local_codex_control.py tests/test_local_codex_ports.py -q -p no:cacheprovider
83 passed, 1 skipped in 1.78s
Python syntax: 8 files PASS (memory only)
PowerShell parse errors: 0
```

跳过用例为Windows下POSIX符号链接检查，不计通过。Python语法通过内存compile验证，不生成pyc；PowerShell只解析入口，不执行启停。未进行全应用生产构建。

主侧提供且当前PHASE11A-VALIDATION.md记录：WSL全后端 `389 passed, 39 skipped, 10 warnings`；前端先前typecheck退出0、60 tests通过。reviewer未重跑全套；skip及既有依赖弃用/SQLAlchemy警告不计已验证。最新ElUpload声明删除后的typecheck由主侧重跑中，本报告不提前声称该次执行已完成；静态审查已核对全局类型来源。

主侧现场证据：同一prepare_workspace/sandbox_command执行codex exec获得NETWORK_OK、exit0；WSL重启后原运行容器全部恢复；两次start的MainPID 2512→2787及fixture恢复成功。最终应用留在真实CLI模式的重载与HTTP200由主侧负责记录，reviewer没有操作或独立复验服务。

最新真实任务 `c26ce47c-bc48-42dd-81b6-ae312f8ddf86` 已终态失败：原生工具生成1254×1254，重试仍不符合Skill的800×800要求，Skill禁止resize；CLI写两失败项，平台未发布。这证明网络不再是阻塞，不构成本轮代理缺陷，也不能当作业务图片验收成功。本次不修改业务Skill。

## 交接

新候选完整14项已审，基础设施/代理Stage 1与Stage 2均PASS。主Agent应确认currentId仍为本报告的8ca7678d…，再按HARNESS协议登记本报告；不得登记初始67610be3…或将本结论用于后续自动生成的新快照。普通Markdown报告不改变代码候选。

本轮只新增本报告，未改代码/服务、未spawn、未commit、未执行review-approve。完整Phase11A保持未完成，后续由主Agent处理Skill尺寸约束与业务验收。
