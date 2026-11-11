# 内网 Codex 授权代理修复增量审查

- candidateId：`bc6c7c26b148e39b0589889dc4347fcd13ab60d2240235944a0cf01a24bab222`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。本轮范围未发现 HIGH / MEDIUM 阻断问题。
- 源文档：`docs/INTRANET-CODEX-AUTH-FIX-20261111.md`；范围仅下列 5 文件，路径均以 `hengxin-smart-image/` 为前缀：
  - `backend/app/account_management/device.py`
  - `backend/app/execution/workspace.py`
  - `backend/tests/test_account_device_proxy.py`
  - `backend/tests/test_execution_proxy.py`
  - `scripts/migration245/fix_account_proxy.py`
- 仅本地独立审查、编译、测试、临时目录替身故障注入；未连接远端、未执行维护、未修源码、未提交。其他已批准改动不在本轮范围。
- 前后 `harness.py review-status` 均返回上述 currentId，changedFiles 恰为以上 5 文件。代码未变化。主 Agent 负责登记同一快照凭据，本报告不自行批准其他文件。

## Stage 1：Spec Compliance

| 源文档条目 | 结论与证据 |
|---|---|
| 仅修复 `.245`，保持公网不动 | 完整实现。`scripts/migration245/fix_account_proxy.py:9-24` 固定目标路径、主机名、root 身份和维护辅助脚本 SHA256；不存在远端调用。主机名与实际 IP 对应由主 Agent 实查，本轮不冒充独立联网证据。 |
| 第 1 步：登录进程只继承八个代理变量，隔离其他宿主凭据 | 完整实现。`backend/app/account_management/device.py:19-30` 由原最小环境追加八项白名单。`backend/tests/test_account_device_proxy.py:11-46` 覆盖有/无代理、完整环境键集合、宿主 HOME/CODEX_HOME 不继承、代理值原样传递、真实解析循环发布授权码以及取消后 stop_process 调用。 |
| 第 2 步：生产 loopback 仅显式 opt-in，其他校验不放宽 | 完整实现。`backend/app/execution/workspace.py:65-84` 保留 clearenv，非 test/development 必须精确配置 `1`；仍限制 HTTP/HTTPS、loopback 主机、有效端口、无凭据/路径/query/fragment，并拒绝空白和 C0/DEL。`backend/tests/test_execution_proxy.py:23-75` 加本轮 37 项补充检查通过。 |
| 第 2 步：账号服务加入两项配置和持久清单 | 完整实现。`scripts/migration245/fix_account_proxy.py:16-17,38-49` 仅账号 env 与 `native-env.json` 的账号节点追加两键，已有配置则拒绝漂移；其他清单节点保留。 |
| 第 3 步：备份、仅部署账号两源文件/env/清单 | 完整实现。`scripts/migration245/fix_account_proxy.py:27-59,69-81` 对旧源码及候选摘要校验、编译候选、检查 root/单链接/解析路径、0700 事务目录与 0600 备份、排空后重查原文、原子替换并保留 mode/group。不修改账号授权数据。 |
| 第 3 步：暂停双消费、排空、账号空闲后仅重启账号 | 完整实现。`scripts/migration245/fix_account_proxy.py:60-68,75,102-110` 调用已批准 helper 的 drain/gate/control；只对 ACCOUNT 执行 systemctl。实际 helper SHA256 与硬校验一致；`scripts/migration245/upgrade_codex.py:85-127` 核对双队列/四类在途状态、socket gate、四线程、临时授权目录与 cgroup 子进程。6 组本地注入进一步验证本次 main 的调用顺序。 |
| 第 3 步：失败保留备份并安全恢复 | 完整实现。`scripts/migration245/fix_account_proxy.py:83-110` 回退前对 active 账号重新 gate，忙则不强停；恢复旧文件并重启账号；逐项恢复 socket/消费并汇总失败。注入验证 mismatch 回退、写入失败回退、忙时拒绝第二次 stop、排空失败不 stop、首个 resume 失败仍恢复第二个。 |
| 第 4 步：最终 UID 取码取消、实际 sandbox 代理访问、HTTP/队列/UI 验收 | 明确为主 Agent 部署后验收，尚未执行。`scripts/migration245/fix_account_proxy.py:75-82,102-110` 只证明运行配置/安装字节及消费者恢复；不能把 APPLIED 或本报告 PASS 解释为网络或浏览器验收完成。源文档第 4 步仍须真实执行。 |
| 最后约束：用户完成官方登录与启用 | 匹配。`backend/app/account_management/device.py:29-43` 沿用已有官方 device-auth 及取消流程；`scripts/migration245/fix_account_proxy.py:20-110` 无登录/启用账户操作。测试取得码后取消，不等同于账户已授权。 |

限定代码职责内，部分实现/未实现：无。后置真实环境验收未执行，单独保留。Spec 漂移：无新业务 API、页面、表或授权行为。UI/设计稿/引导真实性与邻居页面视觉对比不适用：本范围未修改页面；浏览器弹窗结果由部署后验收提供，未虚构视觉 PASS。

## Stage 2：Code Quality

| 项目 | 结论与证据 |
|---|---|
| 命名、结构、大小 | PASS。5 文件分别 43、113、46、75、114 行，均低于 300 行。`device.py:19-25` 白名单改动集中；`workspace.py:71-84` 校验与 env 注入集中；`fix_account_proxy.py:20-110` 单次固定维护事务复用已批准辅助函数，无新增依赖或不必要抽象。 |
| 测试真实性 | PASS（本地覆盖）。`test_account_device_proxy.py:28-46` 真实执行 device_login 循环，仅替换进程/文件安全封装/休眠边界，断言参数、解析和清理。`test_execution_proxy.py:9-20` 使用假二进制验证构造命令，未声称运行真实 Linux Bubblewrap。维护注入调用真实 main，路径/系统进程/helper 边界替身、临时文件真实读写；没有把此结果当作 root 权限、systemd 或远端网络证明。 |
| 错误处理 | PASS。`fix_account_proxy.py:83-110` 对忙账号拒绝回退停机，对每个消费独立恢复；存在原异常时不被恢复错误覆盖。正常/回退/恢复失败分支均有本轮执行证据。 |
| 安全扫描 | PASS。限定 5 文件扫描 eval、shell=True、浏览器危险注入、前端密钥变量、硬编码密钥前缀无命中。`device.py:29-30` argv 启动而非 shell；`workspace.py:74-84` 严格限制代理；`fix_account_proxy.py:21-36,53-59` 身份、摘要和目标文件检查。测试中的 OPENAI_API_KEY 为明确假值 `never-inherit`（`test_account_device_proxy.py:17`），断言不进入子环境。固定服务器绝对路径是本次已授权部署范围，没有打印 env/auth 内容。 |
| 继承 helper 的适用性 | PASS。`fix_account_proxy.py:23-26` 对 helper 固定哈希；本地核对确为 `d6e34d3911ba8772021ea7254557bb90f7efb62376df2eca84e76f8ecd6e5b01`，与 `docs/reviews/INTRANET-CODEX-UPGRADE-RECHECK-20261111.md` 的已批准版本相同。本轮不重审其全部升级职责，仅核查调用语义与新 main 故障路径。 |

测试补充说明：仓库测试的 C0/DEL 用例位于 URL path，单独不能区分“拒绝非空路径”和“拒绝控制字符”。本轮另实测全部 32 个 C0 字符与 DEL 作为合法 URL 前缀均拒绝，且 opt-in `0` / `true` / `yes` / 空值均拒绝，因此没有仅凭路径用例宣称完成控制字符验证。

## 编译和测试原始输出

在 backend 目录执行 `.venv/Scripts/python.exe -m pytest tests/test_account_device_proxy.py tests/test_execution_proxy.py -q`：

```text
....................                                                     [100%]
20 passed in 0.49s
exit_code: 0
```

对范围内全部 5 个 Python 文件执行 `python -m py_compile`：

```text
exit_code: 0
stdout: (empty)
stderr: (empty)
```

使用 `test_execution_proxy.command.__wrapped__` 原 fixture 加临时目录和 MonkeyPatch，调用真实 sandbox_command 补充检查：

```text
37 additional control-character/strict-opt-in checks PASS
exit_code: 0
```

本地 stdin Python 故障注入：导入真实 fix_account_proxy.main；临时目录替换固定路径、基线哈希使用测试文件实际值；辅助模块替换外部边界，不执行服务器操作。原始输出：

```text
APPLIED_ACCOUNT_PROXY
success PASS ['drain', 'gate', 'stop', 'start', 'resume worker1', 'resume worker2']
ROLLED_BACK_ACCOUNT_PROXY
verify_failure PASS ['drain', 'gate', 'stop', 'start', 'gate', 'stop', 'start', 'resume worker1', 'resume worker2']
rollback_busy PASS ['drain', 'gate', 'stop', 'start', 'gate', 'resume worker1', 'resume worker2']
drain_failure PASS ['drain', 'resume worker1', 'resume worker2']
APPLIED_ACCOUNT_PROXY
RESTORE_UNCONFIRMED ["consumer worker1"]
resume_failure PASS ['drain', 'gate', 'stop', 'start', 'resume worker1', 'resume worker2']
ROLLED_BACK_ACCOUNT_PROXY
write_failure PASS ['drain', 'gate', 'stop', 'stop', 'start', 'resume worker1', 'resume worker2']
ALL 6 ACCOUNT MAINTENANCE CASES PASS
exit_code: 0
```

本次 PASS 允许主 Agent 对同一快照登记代码审查结果；真实服务 UID、sandbox 网络、HTTP 健康、消费队列和普通浏览器授权码展示仍需按源文档完成后置验证，官方账户授权与启用留给用户。
