# Codex Fast 受限维护入口审查（2026-11-13）

- candidateId：`f8c838ee8f80579a40e8bd95b3b820d43d668ce83319f94664a1fe85a4a8be22`。
- 结论：Stage 1 **PASS**；Stage 2 **PASS**。无 HIGH / MEDIUM 问题；一项非阻断测试增强建议。
- 审查依据：`Product-Spec.md:1`、`DEV-PLAN.md:1`、`docs/INTRANET-RELEASE-TOOLS.md:21` 的此次 Fast 维护合同，以及 code-review skill。
- 范围：`scripts/release/intranet/` 下 `fast_maintenance.py`、`scope_changes.py`、`scope_release.py`、`release.py`、`release_cli.py`、`test_fast_maintenance.py` 六个代码文件及三份对应文档。已提交业务实现仅核实所引用 runner 的 Git 原始字节与差异，不重新声明业务全量验收。
- 开始、结束分别运行 `review-status`，currentId 均等于上述 candidateId；审查期间未发现代码快照变化。仅写本报告，不改代码、不登记审批、不提交、不连接生产。
- 未纳入：`output/install-fast-maintenance-tool.py` 安装助手、生产部署和两业务在线验收；根目录既存零字节未跟踪文件 `=12.1,` 与此次维护无关。主 Agent 后续须对同一快照登记 review-approve，不能以本报告代替生产验收。

## Stage 1：Spec Compliance — PASS

|合同条目|结论与证据|
|---|---|
|仅国内/国外 full，使用专用入口|完整实现。`release_cli.py:19` 在主机检查前拒绝无 scope、shared、frontend；`release.py:65` 在状态访问前再次限制并禁止同时传 rollback_target；`fast_maintenance.py:13` 再校验包 scope/mode。独立 CLI 拒绝矩阵 4 项通过。|
|限定已审提交和国外 runner 一行变化|完整实现。`fast_maintenance.py:7` 固定完整提交、路径、前后 SHA；`:13` 校验 commit/目标 SHA，`:20` 精确比较路径及前后摘要。独立读取 Git blob，旧新摘要分别匹配常量；`hengxin-smart-image/backend/app/overseas/execution/runner.py:106` 相对父提交只有一行参数插入，见下方原始证据。|
|真实文件字节、来源和作用域检查|完整实现。`snapshot.py:25` 调用实际 `validate_release`；`hengxin-smart-image/scripts/migration245/unify_release.py:167` 检查 root 安全路径、完整目录清单与逐文件摘要；`scope_changes.py:30` 检查 backend provenance、符号链接与实际字节；`:160` 分别求旧新可达归属并取并集。维护未跳过这些校验。这里沿用受信打包 manifest 的来源模型，不声称 manifest 是 Git 签名。|
|普通发布继续拒绝跨业务变更|完整实现。`scope_changes.py:141` 默认 false；`:174` 只有显式维护且 owners 精确为 domestic/overseas 才进入例外，普通分支仍拒绝；`test_fast_maintenance.py:38` 在两组上先断言普通发布拒绝，再断言维护接受。|
|其它共享、账号、未知归属、依赖/schema/runtime 不放宽|完整实现。`scope_changes.py:153` 保持兼容性及 runtime 检查，`:170` 优先拒绝未知，`:174` 不包含 shared 身份域；除唯一固定路径/摘要外仍进入 denied。`snapshot.py:40` 保持依赖及 schema 比较。`test_fast_maintenance.py:65`、`:71`、`:77` 覆盖身份服务、依赖及旧摘要错误；既有 scope_changes 套件覆盖未知归属和可达图边界。|
|沿用准备、排空、备份、切换、验证、恢复|完整实现。`release.py:109` 仍调用同一 prepare，`:132` deploy 使用目标组备份与运行态核验，`:166` 失败恢复；`scope_release.py:32` 绑定现有分组 engine；`scope_actions.py:42` 排空目标组；`engine.py:100` 与 `:171` 在应用及排空后检查候选摘要。无新部署/迁移状态机。|
|失败只恢复目标组，cancel/recover/rollback 不绕过|完整实现。`release.py:122` 恢复前检查 schema/data，`:192`、`:209`、`:222` 保留原恢复/回退/取消行为；`scope_release.py:42` 从当前全局配置生成目标组回退，`release_cli.py:59` 检查 pending scope。`test_fast_maintenance.py:85` 真实调用 Release 流程覆盖成功、排空失败、未切换失败；既有 scope_flow 测试覆盖交错发布和独立回退。|
|不重跑既有联合迁移|完整实现。`release_cli.py:27` 保留 split migration 检查，`:34` 保留 joint marker guard；`joint_studio_marker.py:21` 只校验标记。prepare-fast 分支没有调用 joint_studio 迁移引擎。|
|维护台账可追溯，每组保留两版，另一组不变|完整实现。`release.py:94` pending 记录维护类型、包和 scope；`:162` 复制到 last；`scope_catalog.py:31` 将完整 item 保存到目标组 last 并推进 current/previous；`:54` 保护所有组两版引用。`test_fast_maintenance.py:94`、`:103` 验证维护字段和非目标组不变；全套隔离测试覆盖真实 POSIX GC 引用保护。|
|允许短暂一侧 Fast，另一侧原参数|匹配。Git 差异仅修改 CLI 调度参数，无协议或数据结构改动；`Product-Spec.md:3` 明确接受该发布中间状态；`scope_release.py:37` 和 `release.py:152` 保持非目标服务身份检查。此项是代码兼容性结论，不代表实际生产已切换。|
|无 UI、共享账号业务、数据库和依赖改动|匹配。本候选六个文件均为发布工具及测试，`git diff --stat` 与 `review-status` 文件清单一致。UI 设计数值、引导真实性及邻居页面渲染对比不适用；不虚构 UI 验证。|

部分实现：无。未实现：无。Spec 漂移：无；新增 CLI 已同步至 `Product-Spec.md:3`、`DEV-PLAN.md:3`、`docs/INTRANET-RELEASE-TOOLS.md:21`。

## Stage 2：Code Quality — PASS

- 结构与命名：`fast_maintenance.py:7` 将受限政策集中为固定常量和两个纯函数；`scope_changes.py:174` 只增一条严格例外；六文件分别 21、190、62、247、69、107 行，均低于 300 行。未引入 any、重复状态机或吞掉拒绝异常的逻辑。
- 安全扫描：对六文件执行 eval、dangerouslySetInnerHTML、innerHTML、VITE 密钥前缀、用户绝对路径及已知密钥前缀搜索，无命中；新增逻辑不拼接 shell/SQL、不新增外部命令执行或密钥。`release_cli.py:21` 的 host/root 校验和 `:26` 全局锁保留；`release.py:65` 禁止维护与 rollback_target 混用。未发现此次增量安全问题。
- 测试真实性：`test_fast_maintenance.py:15` 用临时真实文件和 manifest 做归属/摘要验证；`:85` 的状态机测试明确 mock source checker，仅证明接线、备份、台账和恢复，不冒充完整生产联测。独立核对 Git 字节弥补其摘要 monkeypatch 不验证正式常量的问题；完整内网发布套件在 WSL 独立复跑通过。
- LOW（非阻断建议）：`test_fast_maintenance.py:19`、`:91` 分别替换摘要和 source checker，建议未来增加不替换常量的 Git blob 回归及成功 CLI 路由持久化测试。本次已独立核实正式常量、代码接线和非法 CLI 参数，未发现行为缺陷。
- 视觉对比：不适用。`release_cli.py:9` 是命令行入口，候选没有页面/样式变更。

## 独立验证原始输出

Git SHA-256：通过 `git show <revision>:hengxin-smart-image/backend/app/overseas/execution/runner.py` 直接读取二进制后计算，未经 PowerShell 文本换行转换。

```text
('3b38a2c^', '3e0f26f97a9e8ad2ed07f06aa239cd57ff76aa1f9c455c9b35bf842058992187')
('3b38a2c', 'b94c5974ae0fa1c879de45150d60d12335a594b11eb808b95677aefa9eb02b7f')
```

该文件 Git diff 唯一新增行：

```python
args = ['-c', 'service_tier="priority"', '-c', 'features.fast_mode=true', *args]
```

完整隔离测试命令：`wsl -d Ubuntu -- /tmp/hengxin-domestic-studio-python/bin/python -m pytest scripts/release/intranet -q --disable-warnings`。退出码 0，原始测试输出：

```text
........................................................................ [ 17%]
............s........................................................... [ 34%]
................................................ss..........s........... [ 52%]
.................s............................................... [ 67%]
........................................................................ [ 85%]
.............................................................    [100%]
409 passed, 5 skipped, 15 subtests passed in 15.86s
```

注：首次用 WSL 系统 Python 尝试时返回 `/usr/bin/python3: No module named pytest`；改用已存在的项目测试 venv 后如上通过。跳过的 5 项不计作验证通过。WSL 启动另有 localhost 代理提示，未影响测试退出码。

六文件分别执行 Python `compile(source, filename, 'exec')`，不写 pyc，不执行发布逻辑。退出码 0，原始编译输出：

```text
COMPILE_OK fast_maintenance.py
COMPILE_OK scope_changes.py
COMPILE_OK scope_release.py
COMPILE_OK release.py
COMPILE_OK release_cli.py
COMPILE_OK test_fast_maintenance.py
```

CLI 独立负向验证：无 scope、shared、frontend、非法 --apply 均在接触主机状态前 SystemExit(2)。原始结论输出：

```text
CLI_INVALID_MATRIX_OK 4 cases
```

`git diff --check` 退出码 0，无空白错误；仅 Git 原有 CRLF 转 LF 提示。审查末尾 `review-status` 输出：

```json
{"currentId":"f8c838ee8f80579a40e8bd95b3b820d43d668ce83319f94664a1fe85a4a8be22","reviewedId":"663e4b1625f26a11ace2eb8b1a8b737e9a7621d58ff63d0a87792687b1a89eaf","changedFiles":["scripts/release/intranet/fast_maintenance.py","scripts/release/intranet/release.py","scripts/release/intranet/release_cli.py","scripts/release/intranet/scope_changes.py","scripts/release/intranet/scope_release.py","scripts/release/intranet/test_fast_maintenance.py"],"approved":false}
```

`approved:false` 表示 reviewer 未代主 Agent 写入批准凭据；不改变本报告两阶段 PASS 结论。
