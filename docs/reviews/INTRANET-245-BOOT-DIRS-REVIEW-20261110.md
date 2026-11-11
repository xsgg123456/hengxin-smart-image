# 内网 245 启动目录补充审查 · 2026-11-10

candidateId：`46915ca57b8d4bba90af8cac90f408a654bff857fdd888e5c93dcbb3d5c1b8e6`。

**Stage 1：PASS；Stage 2：PASS。** 本次审查唯一新增文件 `hengxin-smart-image/scripts/migration245/hengxin-lan.tmpfiles.conf`，并复核原 Edge/Sandbox 四文件未变化。只批准代码/配置范围；目标机器实际重启恢复仍须主 Agent 验收。未修改代码，未连接或写入服务器。

## 快照与范围

审查前后 `review-status` 均报告当前 candidate 为上述编号，已审编号为 `5337cb538fda63dfc1e0910a4b620652779e8bedd2613a3159ac790e73df1d0d`，changedFiles 唯一为新增 tmpfiles 配置。其 SHA256：`4c79d1130c4c91768f265e72aa92a6ac39eee4d3711859c0247aa758905dce6f`。

前次两阶段 PASS 见 [Edge/Sandbox 修复复审报告](INTRANET-245-EDGE-SANDBOX-FIX-REVIEW-20261110.md)。实算以下文件 hash 与该报告逐项相等，因此原代码结论延续，本次未重复无关测试：

| 文件，均在 hengxin-smart-image/scripts/migration245/ | SHA256 |
|---|---|
| build_edge.py | 7269872ee7d7b8172cc8fdf1c90c6488f48807167200486c6569b1fab8713f3b |
| build_edge_test.py | 4e2b94d136514b4c80911ea1dd9572caa26c50e8915a7c73027425c3c2e27621 |
| build_sandbox_proxy.py | 54740b71b7571313f0e02c5770ceb706f6da08e541169861446d1cf5af1f9ac2 |
| build_sandbox_proxy_test.py | 231fb3e9e8de95cc647c6386345efa1e0f7b04e5a11f6b58a2a93250e2105e74 |

## Stage 1 · Spec Compliance

依据 `Product-Spec.md:3`、`docs/INTRANET-245-PLAN-20261110.md:109`、`:110`、`:217`、`:218` 的新端隔离、socket 权限、启动顺序和重启恢复要求。主 Agent 本次明确补充：预创建空挂载目录，解决 Docker `create_host_path:false` 早于 broker 启动的问题。不会复制旧 socket/PID/锁。

| 条目 | 结论和证据 |
|---|---|
| accounts 父目录及 domestic/overseas 子目录 | 完整实现：新增配置 `:2`–`:4` 使用 d 创建三目录，0750、codex:hengxin-codex-auth；与主 Agent 提供的新机/源机属主基线一致。本地隔离 tmpfiles 执行得到 UID1001/GID986、0750。 |
| legacy broker 目录 | 完整实现：配置 `:5` 创建 /run/hengxin-codex-auth，权限/属主同上。与主 Agent 提供的 RuntimeDirectoryMode=750 基线一致。 |
| publisher 目录 | 完整实现：配置 `:6` 为 /run/hengxin-skill-publisher、0750、root:10001；与 `hengxin-smart-image/backend/app/overseas/management/skill_publisher.py:186`–`:187` 实际 chown/chmod 一致。 |
| 启动早于 Docker 恢复所需目录 | 配置完整：配置 `:1`–`:6` 为系统 tmpfiles 数据，安装至系统 tmpfiles.d 后可于系统早期创建；`build_compose.py:189` 仍为 create_host_path:false。systemd v255 原生 setup unit 在 sysinit.target 之前运行，见下方官方依据。前提是目标 Docker 保持普通服务默认启动依赖；本次未读取新机 unit，真实启动顺序与首次重启结果由主 Agent 实证。 |
| 不重建或搬运 socket 内容 | 完整实现：配置 `:2`–`:6` 全为 d，无复制/写 socket 指令。隔离测试重复执行后 sentinel 文件仍存在、字节不变。 |
| 不改变账户/沙箱/旧生产 | 完整实现：六行静态配置无创建用户、改业务身份、网络命令或远程访问。安装限定新机属于主 Agent 部署责任；配置自身不包含安装脚本。 |
| UI、功能漂移 | 不适用 UI。无新增页面/API/表；预创建目录是计划 `:217` 的启动依赖修复，不新增产品功能。计划 `:110` 的“由服务新建”可在实施记录补充为“tmpfiles 预创建空目录，服务创建 socket”；不是复制旧运行态。 |

范围内完整实现，无部分/未实现需求。配置安装、目标账户存在、目标 Docker 依赖顺序和重启后业务可用性不在本次本地审查完成结论内。

## Stage 2 · Code Quality

| 检查 | 结论和证据 |
|---|---|
| 文件结构/命名 | PASS：配置 `:1` 单行目的说明，`:2`–`:6` 五条固定路径，6 行小于 300；无多余动作。 |
| 权限和安全 | PASS：`:2`–`:6` 均 0750，没有 world 权限；固定所有者与经确认的执行角色相符，无通配符、递归删除/清理、shell、凭据。Age 为 -，没有配置按时间清理子内容。数值 GID10001 与 publisher 实现一致。 |
| 幂等与非破坏性 | PASS：使用 d 指令；本地实际 create 两次均退出0，保留既存子文件，未使用 D/R/r 等清理指令。 |
| 测试真实性 | PASS：直接把受审配置原文交给 systemd-tmpfiles --root 隔离执行，临时根内预置与新机相同 UID/GID 解析，不用手写模拟 mkdir 代替真实解析器。实际核验五目录模式/UID/GID。 |
| 编译/解析 | 无语言编译步骤；真实 systemd-tmpfiles 解析执行退出0，原始输出见后。 |
| 视觉比对 | 不适用：仅启动配置，没有页面变化。 |

未发现 HIGH/MEDIUM 代码问题。原 Edge/Sandbox PASS 及其实际服务验收限制继续有效。

## 验证证据与边界

本地 WSL Ubuntu，root 身份在 Python TemporaryDirectory 下创建隔离根，运行 `systemd-tmpfiles --root=<temporary-root> --create <temporary-config>`。仅此临时根内含合成 passwd/group，未修改 WSL 正式账户和 /run。原始输出（本地版本为259，未冒称目标255）：

```text
systemd 259 (259.5-0ubuntu3.4)
first_create_exit=0
PASS /run/hengxin-codex-accounts mode=0750 uid=1001 gid=986
PASS /run/hengxin-codex-accounts/domestic mode=0750 uid=1001 gid=986
PASS /run/hengxin-codex-accounts/overseas mode=0750 uid=1001 gid=986
PASS /run/hengxin-codex-auth mode=0750 uid=1001 gid=986
PASS /run/hengxin-skill-publisher mode=0750 uid=0 gid=10001
repeat_create_exit=0
PASS existing contents retained
```

[systemd v255 setup unit 源码](https://raw.githubusercontent.com/systemd/systemd/v255/units/systemd-tmpfiles-setup.service) 显示其位于 sysinit.target 前，并执行 create/remove/boot；本配置只有 d 且无 cleanup age，不由 remove 操作删除目录内容。[systemd-tmpfiles 255 官方说明](https://www.freedesktop.org/software/systemd/man/255/systemd-tmpfiles.html) 说明 --root 从隔离根内 passwd/group 解析账户，支持本次测试方法。[tmpfiles 官方说明](https://www.freedesktop.org/software/systemd/man/latest/tmpfiles.d.html) 说明配置用于启动创建易失目录。

主 Agent 后续需在目标机器安装配置后验证五目录实际权限、setup/Docker 顺序并执行已授权的新机重启验收；本报告没有宣称该部署或重启已完成。由主 Agent 对同一 candidate 登记本报告两阶段 PASS，不写 .needs-review clean。
