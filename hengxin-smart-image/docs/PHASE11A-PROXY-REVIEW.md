# Phase 11A 开发代理独立两阶段审查

日期：2026-09-11。candidateId：`92eb98f927eea09336221e3e0381b1c65de03a686d5391d8763ff2b293074868`。

**Stage 1：FAIL（1 项 MEDIUM 边界要求未完整实现）；Stage 2：FAIL（同一缺陷，无额外缺陷）。不能登记两阶段 PASS，也不能批准完整 candidate。** Stage 1 未发现 HIGH，继续完成 Stage 2。完整 Phase 11A 真实图片、返工及并行验收仍未通过，不将网络恢复或 running 状态当作业务成功。

## 范围与方法

已读取 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、Product-Spec 8.3、DEV-PLAN Phase 11A 相关内容和旧基础设施报告。按用户当前授权核对 WSL 镜像网络/autoProxy 复用 Windows loopback 代理、显式开发代理、默认不继承、保留隔离和生产禁用。

顺序：核对快照及需求覆盖；检查校验、环境映射及故障测试；补查指定三项前轮变化；写报告。完成标准是每项结论有代码位置或执行输出，未知证据不补作 PASS。

直接审查范围（除点目录外，路径相对嵌套 `hengxin-smart-image/`）：

- `backend/app/execution/workspace.py` 的代理新增部分及相邻隔离实现。
- `infra/local_codex_worker.py` 的代理映射和环境更新路径。
- `infra/.env.local-codex.example`、`backend/tests/test_execution_proxy.py`、`docs/LOCAL-CODEX-DEVELOPMENT.md`。
- 追加只读审查：根目录 `.codegraph/.gitignore`、`.cursor/rules/codegraph.mdc`、`frontend/src/types/import/components.d.ts` diff；参考 frontend/tsconfig.json。

旧基础设施参考 `docs/PHASE11A-INFRA-REVIEW.md` 中 `409f6eef2092301682f8271999a04f0cdf032ac926b3b33135542673d49fd302` 的两阶段 PASS。本次没有重做其整套审查。当前 review-state 仅存 baseline `94a4abc5…`、本候选和空 approved，没有旧候选文件哈希清单；因此不能独立证明旧 controller/keeper/overlay/入口及三份 local_codex 测试与 409f 候选逐文件相同。旧报告可作历史依据，但本报告不声称已覆盖批准全部 14 项候选变化。

开始及报告前 review-status 均返回上述 currentId，reviewedId=null、approved=false。文档更新未改变受控快照。只新增本报告；未改代码、服务或网络，未 spawn、commit 或 review-approve。

## Stage 1：需求覆盖

| 要求 | 结论与证据 |
| --- | --- |
| 显式本地代理进入任务沙箱 | 已实现正常路径：workspace.py:62–74 读取专用变量，设置大小写 HTTP_PROXY、HTTPS_PROXY、NO_PROXY；test_execution_proxy.py:24–33 检查显式值、NO_PROXY、clearenv 及不泄漏宿主 HTTP_PROXY/SECRET。 |
| 仅开发/测试、限制 loopback HTTP(S) 无认证端点 | 已实现：workspace.py:65–71 拒绝生产、其它协议/主机、无效端口、认证、路径/query/fragment 和空白；独立测试全部相关用例通过。 |
| 不放宽已有任务隔离 | 已实现：对 HEAD diff 仅增加导入和代理 setenv；workspace.py:56–61、75–84 保留 clearenv、namespace、cap-drop、只读运行时与私有 home/work 挂载，没有新增宿主目录挂载或网络转发。 |
| Worker 映射、空默认阻止继承 | **部分实现，F-01**：local_codex_worker.py:26 的缺省和显式等号空值有效，但裸变量被 :34 过滤，:49 更新环境时保留宿主同名变量。 |
| 配置及联调说明 | 样例 :12 默认空值；LOCAL-CODEX-DEVELOPMENT.md:15 明确镜像网络、autoProxy、端点、环境限制和沙箱内请求验证；真实业务仍单独验收。DEV-PLAN:353 尚为旧阻塞叙述，用户已说明后续标记历史已解决，未计新增代码缺陷。 |

本轮无 UI 行为改动，视觉验证不适用；未发现新增业务 API、表或未经授权的功能。生产配置未在本轮范围内修改。

## Stage 2：F-01 · MEDIUM / P2 — 裸代理配置保留宿主代理

位置：`infra/local_codex_worker.py:26,34,49`。

触发前提：test/development Worker 宿主已有 `HENGXIN_CODEX_PROXY_URL=http://127.0.0.1:9999`，本地 dotenv 文件包含一行无等号、无值的 `LOCAL_CODEX_PROXY_URL`。python-dotenv 将它解析成 None；`local.get(..., '')` 不对存在但为 None 的键使用默认值。返回字典过滤 None 后不再含 HENGXIN_CODEX_PROXY_URL，`os.environ.update(values)` 保留原值，随后沙箱接收 9999 代理。用户没有在本地配置显式选择该端点，却实际使用宿主端点，违反本轮明确要求。

这不是生产绕过或任意远程代理绕过：workspace 仍限制开发环境及 loopback，故定 MEDIUM，不夸大为隔离逃逸。

独立复现使用实际 configuration()、临时 dotenv 文件，以及与 main() 相同的 dict.update 语义；未调用服务或网络：

```text
缺少 LOCAL_CODEX_PROXY_URL: mapped='' effective=''
LOCAL_CODEX_PROXY_URL=: mapped='' effective=''
LOCAL_CODEX_PROXY_URL（无等号）: mapped='<missing>' effective='http://127.0.0.1:9999'
LOCAL_CODEX_PROXY_URL=http://127.0.0.1:7890: mapped='http://127.0.0.1:7890' effective='http://127.0.0.1:7890'
```

解析语义已对照 [python-dotenv 官方参考](https://bbc2.github.io/python-dotenv/reference/)：无值键返回 None。

建议将缺失/None 明确归一为空字符串，或明确拒绝裸键；确保返回映射始终覆盖宿主专用变量。补充真实 configuration→环境合并测试，覆盖缺失、等号空、裸键和有效代理，预置宿主同名代理。当前 test_execution_proxy 直接构造工作空间环境，test_local_codex 未断言代理映射，不能覆盖此故障。

代码质量：workspace 104 行、Worker 85 行、代理测试 49 行以内，符合 300 行上限。新增代码以参数数组构造 setenv，没有动态 shell、业务 SQL、密钥输出；错误拒绝发生在命令执行前。现有缺陷无需修改隔离参数。

## 追加三项审查

| 文件 | 结论 |
| --- | --- |
| `.codegraph/.gitignore:1–16` | 仅忽略本目录数据库及 WAL/SHM、cache、log、dirty 标志，无运行时代码、凭据或外部操作；静态审查未见缺陷。 |
| `.cursor/rules/codegraph.mdc:1–44` | CodeGraph 工具选择及初始化说明，与用户提供规则一致；无自动执行命令或生产行为；静态审查未见缺陷。 |
| `frontend/src/types/import/components.d.ts:75–117` | diff 仅删除部分 Element Plus 全局类型声明，没有运行时代码变化。部分组件仍被 Vue 模板使用，但 tsconfig.json:19 已包含 element-plus/global，因此不能将声明删除直接认定组件消失。前端 typecheck/test 由主侧补充，尚未收到本轮结果，不声称已编译通过。 |

## 验证与证据边界

- reviewer 独立执行，禁用字节码及 pytest cache：`python -m pytest hengxin-smart-image/backend/tests/test_execution_proxy.py hengxin-smart-image/backend/tests/test_execution_workspace.py hengxin-smart-image/backend/tests/test_local_codex.py -q -p no:cacheprovider`，**21 passed、1 skipped in 0.34s**。跳过的是 Windows 不支持的 POSIX symlink 用例，不算通过；测试模块与生产模块导入成功。未单独做全后端编译或构建。
- reviewer 独立 F-01 四种配置内存复现，结果如上。
- 主侧补充：WSL 对应测试 **22 passed**；全后端 **386 passed、39 skipped、10 warnings**。reviewer 未重跑全套，不将 skip 计为通过。
- 主侧提供：同一 bubblewrap 沙箱 CLI exec 返回 NETWORK_OK、exit 0，WSL 镜像网络已生效、重启前容器恢复，本轮未新建转发或修改防火墙。reviewer 未操作或独立复验现场。
- 主侧最新真实任务 `c26ce47c-bc48-42dd-81b6-ae312f8ddf86`，来源 cli、running，session `01a08f61-30b5-7d00-b9e7-0f4f8afea599`，仍等待真实图片。不能代替生成、返工、下载归档和双任务并行证据。

## 交接

修复 F-01 后重新 review-prepare，从 Stage 1 复核差异，再决定两阶段结论。完整候选登记还需要旧基础设施未变化的可核对依据（或补充范围审查）；本报告不能单独授权完整 candidate。完整 Phase 11A 保持验收进行中。

### 主侧最后补充

前端 typecheck 退出 0、60 tests 通过（主侧提供，更新上表待补状态，reviewer 未重跑）。真实 CLI 图像工具已生成两张 1254×1254 文件，因 Skill 要求 800×800 正在重试：支持网络与 imagegen 链路已通，不证明业务验收通过。本轮不审业务 Skill。该补充不改变 F-01 或两阶段 FAIL 结论；用户确认代码候选仍为 92eb98f9…。
