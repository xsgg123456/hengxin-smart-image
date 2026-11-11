# 内网 245 Edge / Sandbox 修复复审 · 2026-11-10

candidateId：`5337cb538fda63dfc1e0910a4b620652779e8bedd2613a3159ac790e73df1d0d`。

**Stage 1：PASS。Stage 2：PASS。仅限下述四文件和生成器/部署补丁的代码范围，不代表新机实际服务健康或全迁移验收通过。** 主 Agent 可为同一 candidate 按协议登记本报告，不得批准其他快照。

范围：`hengxin-smart-image/scripts/migration245/` 下 `build_edge.py`、`build_edge_test.py`、`build_sandbox_proxy.py`、`build_sandbox_proxy_test.py`。未改代码、未连接/写入服务器。执行 code-review skill，从 Stage 1 重新检查后进入 Stage 2。

前次失败记录：[原候选报告](INTRANET-245-EDGE-SANDBOX-REVIEW-20261110.md)。本次并非沿用旧 PASS：旧候选为 `488976d998733cd8938156c38222e3c4184d7ba501cdaba2247413d8f340fbdb`，两阶段从未通过。新候选新增三种 nginx 临时目录及五目录回归测试；sandbox 两文件 SHA256 未变。将 edge 三新增行仅在内存去除后得到原文件 SHA256 `ed4f5923c00aeeecfeca32b55766d8f1a3549e28e8f4ec531002fe8537d213dc`，证明实现差异限定三行。审查前后 review-status 都为新 candidate，未发现审查中代码变化。

## Stage 1 · Spec Compliance：PASS

依据：`Product-Spec.md:3`；`docs/INTRANET-245-PLAN-20261110.md:7`、`:22`、`:35`、`:57`、`:64`、`:83`、`:100`、`:102`。完整复审以下本批责任项；未把身份、数据库、独立授权、业务全功能或新机长期运行纳入 PASS。

下表所有代码位置相对于 `hengxin-smart-image/scripts/migration245/`。

| 需求 | 结论和证据 |
|---|---|
| 新端限定，旧生产及公网 DNS 不变 | 完整实现：`build_edge.py:144`、`build_sandbox_proxy.py:134` 的 host/root 门禁早于读写；固定本地路径，无 SSH/DNS 操作；edge `:162` 仅写候选，sandbox `:130` 不重启。错误主机/root 测试 edge_test `:94`、sandbox_test `:157` 通过。 |
| 正式域名、指定新 IP、公司网段 | 完整配置：edge `:30`–`:38` 固定 192.168.1.245:443 和正式名，两个许可网段 + deny all；edge_test `:40`–`:46` 通过。专用浏览器解析是后续人工/运维步骤，无修改全公司解析的实现。 |
| 已有镜像锁定及保护证书副本 | 完整实现：edge `:86`、`:90`–`:100` 使用 SHA256 image ID、pull never、host network、只读且禁止自动创建的 bind mount；`:118`–`:125`、`:147`、`:159` 检查 root/0600 证书、路径及本地镜像。 |
| nginx 只读容器可初始化 | **原 HIGH E1 已关闭**：edge `:24`–`:28` 五种 temp path 均位于 /tmp；`:98`–`:99` 只读根 + /tmp tmpfs。edge_test `:60`–`:70` 新增全路径断言；reviewer 同只读容器实际 `nginx -t`、启动、退出全部成功，原始输出见后。 |
| loopback 上游、SSE、上传参数 | 完整配置：edge `:40`–`:57` 512m、HTTP/1.1、正确转发头、关闭缓存与请求/响应 buffering、300s 超时；`:88` 上游地址严格要求 loopback:18080。edge_test `:42`–`:46`、`:86` 验证。实际 500 MB 上传/SSE 连通仍属新机验收。 |
| 容器代理 listener 与六网段精确控制 | 完整配置：edge `:64`–`:80` 严格验证六网络所有权/驱动/CIDR/网关；`:106` 单监听 172.30.245.1:7891，连接 127.0.0.1:7890；`:111`–`:112` deny any、allow loopback 与六 CIDR。edge_test `:48`–`:58`、`:72`–`:84` 通过。 |
| production 默认拒绝，显式 flag=1 才允许 | 完整实现：sandbox `:22`–`:25`、`:41`–`:51` 精确替换并编译；sandbox_test `:44`–`:64` 验证默认、错误 flag 拒绝及显式启用。 |
| 保留严格 loopback URL 校验且拒绝控制字符 | 完整实现：sandbox `:24`–`:25` 追加 C0/DEL 拒绝；保留真实 workspace.py 校验。sandbox_test `:66`–`:88` 覆盖远程、凭据、scheme、port、path、空白及控制字符。测试读取真实仓库源码，其 SHA256 为 `35d4ba0240f5c1ffaaec317c3592ef28899cf04c414f6f640b737ef3465fcb75`，与主 Agent 提交的两端源 hash 一致；未冒称直接读取服务器。 |
| 两 worker env，APP_ENV/沙箱不变 | 完整实现：sandbox `:18`–`:19`、`:54`–`:59` 仅向两 env 追加 flag/proxy；sandbox_test `:59`–`:62`、`:87`–`:98` 验证 clearenv/namespace/workspace-write 保持、补丁逆向恢复逐字相等、原 APP_ENV 与既有 env 字节前缀保持。 |
| 源 hash、防漂移、备份、原子替换、不 restart | 完整实现：sandbox `:62`–`:68`、`:95`–`:129`，源 hash、模式检查、同文件系统、私有备份、双重漂移检查、每文件 os.replace 和 journal。sandbox_test `:117`、`:130`、`:143` POSIX 实测通过。原子性是单文件，不是四文件事务；失败保留备份和已应用标记供恢复。 |
| UI/引导真实性 | 不适用：四文件没有产品页面、导航或引导文案；不需要浏览器设计比对。 |
| Spec 漂移 | 无新增产品页面/API/表/组件；本批代理适配已在计划 `:7` 明示，HTTPS 同域名方案在计划 `:57` 明示。 |

完整实现为上表代码责任；部分/未实现的本批需求：无。新机实际运行验收不在这四文件的代码完成结论内。

## Stage 2 · Code Quality：PASS

| 检查 | 结论与证据 |
|---|---|
| 命名、结构、文件大小 | 四文件分别 170/132/151/165 行，均小于 300。edge `:64`、`:83`、`:118`、`:128`、`:143` 分离输入验证、生成、路径保护、写出、主入口；sandbox `:41`、`:54`、`:62`、`:80` 分离源码补丁、环境补丁、收集、部署。无 any；Python 模块没有采用类型注解体系，不为本次独立运维脚本强加新风格。 |
| 错误处理与敏感输出 | edge `:167`–`:170`、sandbox `:147`–`:151` 统一拒绝且不打印源文件/env 内容。sandbox `:109`–`:129` 保留内容备份、hash manifest 和 applied journal；缺 env 则只写计划 `:95`–`:97`。未声称自动多文件回滚。 |
| 命令注入、危险执行 | edge `:151`、`:155`、`:159` 子进程均传固定 argv，无 shell=True；无生产 eval/exec/SQL/UI 注入入口。sandbox_test `:34` 的 exec 仅执行本地受审源码提取的 sandbox_command AST，用于生成 argv，未执行 Codex。 |
| 凭据安全 | 扫描仅匹配 sandbox_test `:91`、`:111` 的合成 SECRET 字符串，无真实密钥。edge `:118`–`:125` 要求 root/0600、无链接；sandbox `:32`–`:38` 拒绝链接/硬链接，`:100` env 私有模式，`:138`–`:143` 检查根目录和目标所有权；备份 exclusive/0600，目录 0700。 |
| 网络边界 | edge `:106` 固定来源 listener 与目标，无把远程 URL 拼入 unit；`:111`–`:112` 精确配置 allow/deny。systemd 的 IPAddressAllow/Deny 对入站源和出站目的分别过滤，符合本 unit 使用方式；[systemd 255 官方文档](https://www.freedesktop.org/software/systemd/man/255/systemd.resource-control.html)。真实内核 eBPF 支持和规则效果仍须实测，单元字符串不证明网络隔离已经生效。 |
| 测试真实性 | sandbox_test `:16`–`:21` 读取实际仓库 workspace.py，`:29`–`:42` 提取真实函数而非复制伪实现；`:83`、`:87` 验证 hash 漂移和补丁范围；POSIX 文件系统用例实际备份/替换/拒绝链接。edge_test `:72`–`:92` 覆盖 CIDR/所有权/镜像/上游漂移，`:102`–`:117` 覆盖重复写入保护。本次补做真实只读 nginx 初始化/进程启动，排除原纯字符串断言漏报。 |
| 测试盲区与实际验收 | `build_edge_test.py:26` 只验证生成配置，不运行 TLS/生产上传/SSE；sandbox_test `:39` 使用合成二进制占位，不执行真实 bwrap/Codex。实际 systemd 255、TLS 证书链、目标主机端口冲突、代理允许/拒绝连接、实际 sandbox 网络均由主 Agent 随部署验证。本报告的 PASS 不扩展到这些能力。 |
| 视觉邻居比较 | 不适用：无 UI；未伪造页面渲染验收。 |

无 HIGH/MEDIUM 待修代码问题。以上运行验收边界不等于已验证实际服务。

## 独立验证与原始输出

本机已有 `nginx:1.27-alpine` 镜像，未拉取升级。与失败复现采用同样 `--network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --security-opt no-new-privileges:true`；仅将配置 listen 改为 loopback 并去除 TLS 证书依赖，目的为隔离复验原目录错误，不伪称验证真实证书。执行 `nginx -t -c /tmp/edge.conf && nginx -c /tmp/edge.conf && nginx -s quit -c /tmp/edge.conf`：

```text
nginx: the configuration file /tmp/edge.conf syntax is ok
nginx: configuration file /tmp/edge.conf test is successful
2026/11/10 08:02:48 [notice] 1#1: signal process started
exit_code=0
```

Python 四文件 compile 验证，退出码 0：

```text
COMPILE PASS hengxin-smart-image\scripts\migration245\build_edge.py
lines=170 SHA256=7269872ee7d7b8172cc8fdf1c90c6488f48807167200486c6569b1fab8713f3b
COMPILE PASS hengxin-smart-image\scripts\migration245\build_edge_test.py
lines=132 SHA256=4e2b94d136514b4c80911ea1dd9572caa26c50e8915a7c73027425c3c2e27621
COMPILE PASS hengxin-smart-image\scripts\migration245\build_sandbox_proxy.py
lines=151 SHA256=54740b71b7571313f0e02c5770ceb706f6da08e541169861446d1cf5af1f9ac2
COMPILE PASS hengxin-smart-image\scripts\migration245\build_sandbox_proxy_test.py
lines=165 SHA256=231fb3e9e8de95cc647c6386345efa1e0f7b04e5a11f6b58a2a93250e2105e74
```

WSL Ubuntu 运行 `python3 -B -m unittest build_edge_test build_sandbox_proxy_test -v`，退出码 0，无跳过：

```text
test_host_and_root_guards_precede_reads (build_edge_test.EdgeTests.test_host_and_root_guards_precede_reads) ... ok
test_protected_rejects_permissions_and_symlinks (build_edge_test.EdgeTests.test_protected_rejects_permissions_and_symlinks) ... ok
test_readonly_root_uses_writable_tmp_for_every_nginx_temp_path (build_edge_test.EdgeTests.test_readonly_root_uses_writable_tmp_for_every_nginx_temp_path) ... ok
test_reject_external_web_or_mutable_image (build_edge_test.EdgeTests.test_reject_external_web_or_mutable_image) ... ok
test_reject_network_drift_or_forged_ownership (build_edge_test.EdgeTests.test_reject_network_drift_or_forged_ownership) ... ok
test_unit_allowlist_exact_and_retries_missing_bridge (build_edge_test.EdgeTests.test_unit_allowlist_exact_and_retries_missing_bridge) ... ok
test_valid_scope_and_immutable_readonly_mounts (build_edge_test.EdgeTests.test_valid_scope_and_immutable_readonly_mounts) ... ok
test_write_is_exclusive_and_batch_preflight_preserves_existing (build_edge_test.EdgeTests.test_write_is_exclusive_and_batch_preflight_preserves_existing) ... ok
test_atomic_apply_backups_and_repeated_run_refused (build_sandbox_proxy_test.ProxyTests.test_atomic_apply_backups_and_repeated_run_refused) ... ok
test_environment_preserves_app_env_and_secrets (build_sandbox_proxy_test.ProxyTests.test_environment_preserves_app_env_and_secrets) ... ok
test_existing_development_test_behavior_and_source_drift (build_sandbox_proxy_test.ProxyTests.test_existing_development_test_behavior_and_source_drift) ... ok
test_explicit_production_opt_in_preserves_only_loopback_proxy (build_sandbox_proxy_test.ProxyTests.test_explicit_production_opt_in_preserves_only_loopback_proxy) ... ok
test_missing_environment_is_plan_only_and_drift_refused (build_sandbox_proxy_test.ProxyTests.test_missing_environment_is_plan_only_and_drift_refused) ... ok
test_production_default_and_invalid_flags_remain_denied (build_sandbox_proxy_test.ProxyTests.test_production_default_and_invalid_flags_remain_denied) ... ok
test_remote_credentials_schemes_paths_ports_and_controls_rejected (build_sandbox_proxy_test.ProxyTests.test_remote_credentials_schemes_paths_ports_and_controls_rejected) ... ok
test_source_host_guard_before_reads (build_sandbox_proxy_test.ProxyTests.test_source_host_guard_before_reads) ... ok
test_symlink_and_shared_environment_rejected_without_changes (build_sandbox_proxy_test.ProxyTests.test_symlink_and_shared_environment_rejected_without_changes) ... ok

----------------------------------------------------------------------
Ran 17 tests in 0.140s

OK
```
