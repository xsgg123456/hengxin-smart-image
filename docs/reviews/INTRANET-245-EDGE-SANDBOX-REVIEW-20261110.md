# 内网 245 Edge / Sandbox 独立审查 · 2026-11-10

candidateId：`488976d998733cd8938156c38222e3c4184d7ba501cdaba2247413d8f340fbdb`。

范围仅 `hengxin-smart-image/scripts/migration245/` 下的 `build_edge.py`、`build_edge_test.py`、`build_sandbox_proxy.py`、`build_sandbox_proxy_test.py`。依 code-review skill 执行，未修改代码、未连接服务器、未写入服务器、未启动业务服务。审查前后 review-status 均为此 candidate；报告不批准后续改动。

**Stage 1：FAIL，存在 1 项 HIGH。Stage 2：未执行。不得登记两阶段 PASS。**

## Stage 1 · Spec Compliance

源需求：`Product-Spec.md:3`；`docs/INTRANET-245-PLAN-20261110.md:7`、`:22`、`:35`、`:57`、`:64`、`:83`、`:100`、`:102`。仅审查本批生成器/部署补丁负责的条目，身份、迁库、授权、业务界面和整体迁移完成不在本报告范围。

| 条目 | 结论与证据 |
|---|---|
| 仅新端操作，不改变旧生产和公网解析 | 完整实现本批边界：edge `:141`、sandbox `:134` 先检查主机/root；仅本地固定路径，未提供 SSH/DNS 修改逻辑。edge `:159` 只生成候选，sandbox `:130` 无重启逻辑。错误主机用例 edge_test `:82`、sandbox_test `:157` 通过。 |
| 沿用正式域名，限定新端监听及公司网段 | 配置完整：edge `:27`–`:35` 固定 192.168.1.245:443、zhitu.qhhengxin.top、两个许可网段并 deny all；edge_test `:40`–`:46` 验证。独立浏览器解析由后续运维实施，本文件不实现解析修改。 |
| 锁已有镜像、host network、证书本地受保护副本 | 完整实现生成器边界：edge `:83`、`:87`–`:97`、`:140`–`:158` 检查镜像 ID、本地存在、证书 root/0600、只读挂载、不拉镜像。 |
| 新端 HTTPS 入口可实际启动 | **未实现，HIGH E1**：edge `:24`–`:25` 未覆盖 fastcgi/uwsgi/scgi 临时目录，`:95`–`:96` 将根文件系统只读且仅允许 /tmp 写入，nginx 初始化失败。见下方复现。 |
| 代理 loopback 18080，保留 SSE / 大文件上传语义 | 配置完整：edge `:37`–`:54` 为 512m、HTTP/1.1、转发来源/协议、关闭请求/响应缓存、300s 超时；`:85` 检查上游仅发布 loopback。edge_test `:42`–`:46` 通过。但受 E1 阻断，不能声称实际 SSE/上传通过。 |
| Docker bridge socat 转发与精确来源限制 | 配置完整：edge `:61`–`:77` 验证六网络 CIDR/标签/驱动/网关；`:103` 固定 172.30.245.1:7891 → 127.0.0.1:7890；`:108`–`:109` deny any + 六 CIDR + loopback。edge_test `:48`、`:60` 验证通过。实际 systemd 255/eBPF 接受与拒绝连接待主 Agent 实测。 |
| production 仅显式 flag=1 开放 loopback 代理 | 完整实现补丁逻辑：sandbox `:22`–`:25`、`:41`–`:51`；sandbox_test `:44`–`:88` 证明默认/错误 flag 拒绝、显式 flag 允许、远程/凭据/不合法 scheme/path/port/C0/DEL 拒绝。 |
| 保持 APP_ENV 与工具沙箱 | 完整实现本批逻辑：sandbox `:54`–`:59` 仅追加两个键；sandbox_test `:59`–`:62`、`:87`–`:96` 验证既有 namespace/clearenv/workspace-write 保持以及补丁可逆后源码逐字相等。 |
| 两 worker 环境、真实源 hash、防漂移、备份、单文件原子替换，不 restart | 完整实现本批逻辑：sandbox `:14`–`:19`、`:62`–`:68`、`:95`–`:129`。本地实际 workspace SHA256 为 `35d4ba0240f5c1ffaaec317c3592ef28899cf04c414f6f640b737ef3465fcb75`，与主 Agent 所报双端真实源码一致；本报告未直接读取服务器源码。`:126` 是逐文件 os.replace，不是四文件事务；失败留下受保护备份及 applied journal。POSIX 用例 sandbox_test `:117`、`:130`、`:143` 通过。 |
| UI 一致性与引导真实性 | 不适用：四文件不产生产品 UI、页面提示或导航。没有 UI 改动，故无需邻居页面视觉对比。 |
| Spec 漂移 | 未发现新增页面/API/表/组件；仅执行已写入计划 `:7` 的新端代理适配与 `:57` 的 HTTPS 入口。 |

### HIGH E1 · 生成的只读 nginx 容器启动失败

需求原文（计划 `:62`、`:83`）：新机提供可信 HTTPS 443；保留 HTTPS origin、Host、转发协议、上传大小、SSE 和超时语义。

代码位置：`hengxin-smart-image/scripts/migration245/build_edge.py:24`、`:95`、`:96`。只把 client/proxy temp 移至 /tmp，其他 nginx 编译默认目录仍在 /var/cache/nginx。nginx 初始化会创建这些目录，即使无 FastCGI 路由。

本地已有 `nginx:1.27-alpine`、`--network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --security-opt no-new-privileges:true --entrypoint /bin/sh` 实测。测试输入取生成器 NGINX，仅将 listen 换为 127.0.0.1:443 并去除证书路径/ssl 监听参数，以排除证书和网卡依赖，其他目录配置原样。执行 `nginx -t -c /tmp/edge.conf` 的原始输出：

```text
nginx: the configuration file /tmp/edge.conf syntax is ok
2026/11/10 08:00:56 [emerg] 1#1: mkdir() "/var/cache/nginx/fastcgi_temp" failed (30: Read-only file system)
nginx: [emerg] mkdir() "/var/cache/nginx/fastcgi_temp" failed (30: Read-only file system)
nginx: configuration file /tmp/edge.conf test failed
exit_code=1
```

官方依据：[nginx 构建路径说明](https://nginx.org/en/docs/configure.html) 列出 fastcgi/uwsgi/scgi temp 编译路径和可覆盖的相应指令。主 Agent 另提供新机锁定镜像只读核查结果：`/var/cache/nginx/*` 无现成目录，编译默认路径均位于该目录；这部分为主 Agent 提供的证据，不冒称 reviewer 实机执行。

修复标准：补齐三种 temp path 至可写 /tmp；增加只读容器真实 `nginx -t` 回归，修复后重新固定 candidate，重派从 Stage 1 审查。

## 编译和测试原始输出

四文件 Python `compile(bytes, path, 'exec')`，退出码 0：

```text
COMPILE PASS hengxin-smart-image\scripts\migration245\build_edge.py
COMPILE PASS hengxin-smart-image\scripts\migration245\build_edge_test.py
COMPILE PASS hengxin-smart-image\scripts\migration245\build_sandbox_proxy.py
COMPILE PASS hengxin-smart-image\scripts\migration245\build_sandbox_proxy_test.py
```

Windows 执行 `python -m unittest build_edge_test build_sandbox_proxy_test -v`：

```text
Ran 16 tests in 0.191s
OK (skipped=2)
```

两个跳过项为 Unix 文件权限/链接用例，随后 WSL Ubuntu 执行 `python3 -B -m unittest build_edge_test build_sandbox_proxy_test -v`，完整测试输出：

```text
test_host_and_root_guards_precede_reads (build_edge_test.EdgeTests.test_host_and_root_guards_precede_reads) ... ok
test_protected_rejects_permissions_and_symlinks (build_edge_test.EdgeTests.test_protected_rejects_permissions_and_symlinks) ... ok
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
Ran 16 tests in 0.152s

OK
```

这些单元测试未覆盖 nginx 真实启动，不能替代上述失败结果。Stage 2 代码质量、安全扫描、测试真实性全量复核在修复后执行；本次不能给 Stage 2 结论。实际服务健康、目标 systemd 255 策略生效、真实 sandbox 网络和收费执行均未由本次审查验证。
