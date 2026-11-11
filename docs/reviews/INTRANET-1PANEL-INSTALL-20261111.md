# 内网 1Panel 安装准入审查

## 最终复核结论（有效结论）

- 最终 candidateId：`75a326324d594b92f5009ba012e322c811d8648e85912a2d461118f31e243de4`。
- **Stage 1 PASS；Stage 2 PASS，仅限本次安装适配脚本准入。** 审查范围仍仅为两个 maintenance Python 文件及其安装源计划；此快照包含的其他会话前端文件未审查，不获本报告批准。
- 最终 `review-status` 实查 currentId 与上述编号一致；登记批准由主 Agent 执行。未写 `.needs-review`，未执行部署或提交。
- 审查期间发生两轮实现修改，先后快照为 `b77584a...`、`64d8a98...`、最终 `75a3263...`；以下旧报告保留作为问题证据，旧 FAIL 已经复核关闭，不覆盖本节最终结论。
- 最终实现 SHA256：`8E37AA7E10830A736932ACF093B50222E5E0FA41AE32D7317FD70EEEC3F17BE8`；测试文件内容未变。

### Stage 1 复核

| 项目 | 最终结论与证据 |
| --- | --- |
| 官方包/安装器固定与解压边界 | PASS：`scripts/maintenance/install_panel.py:15`、`:74`、`:94`、`:130`；本地摘要、真实20成员和拒绝路径/链接测试均通过。 |
| 独立目录与既有目标保护 | PASS：`:12`、`:105`、`:177`；guard 拒绝目标已存在，独立 BASE 传入官方 Set_Dir，init_configure 内的配置写入已经逐命令检查。正常调用链不触碰 `/opt/1panel`。 |
| 不修改 Docker、不操作原防火墙、不安装应用商店应用 | PASS：`:47`、`:48`、`:49` 覆盖官方调用；`:51` 的受控服务步骤仅处理两项面板服务。 |
| 端口与专属网段访问控制 | PASS（脚本）：`:18`、`:39`、`:123`、`:134`；规则限定10086，访问控制必须先启动。主 Agent 另提供远端 bash -n 和 nft -c 成功，但本 reviewer 未连接生产，不把转述作独立实测。 |
| 强随机凭据、入口和私有输出 | PASS：`:69`、`:88`、`:160`、`:172`、`:184`；1pctl 在写凭据前限制700；随机值不写仓库，输出只写私有 staging。原 HIGH-01 关闭，故障注入证明配置写失败不再进入服务启动。 |
| 失败回退边界 | PASS：`:146`、`:182`；访问规则 setup 已在 try 内，禁用失败抛错保留规则，确认停止且端口关闭后才撤规则。源计划 `docs/INTRANET-1PANEL-20261111.md:15` 已同步该安全边界。原 MEDIUM-02 关闭。 |
| 官方二进制不变 | PASS：`:194` 安装后逐个比较已安装二进制与归档解压文件 SHA256，失败进入回退；未替换官方二进制内容。 |
| 浏览器、监控开启/15天/真实采样、无额外业务应用、服务/摘要/健康/磁盘基线复查 | **待生产验收，不属于此次脚本准入 PASS**。源计划第1、4、5项均完整识别并保留；`:199` 明确提示 browser/baseline still required。 |
| UI/设计和新增范围 | 脚本没有产品UI；无视觉设计稿适用项。实际面板页面和监控图待主 Agent 实查。没有发现超出安装/回退范围的新应用动作，证据 `:45`、`:134`、`:146`。 |

### Stage 2 复核

- 代码结构 PASS：最终206行，标准库依赖；guard、适配、归档检查、访问控制和回退分别独立，见 `scripts/maintenance/install_panel.py:64`、`:74`、`:94`、`:105`、`:134`、`:146`。无 any 或超300行文件。
- 安全扫描 PASS（本范围）：对两个文件检索 eval、innerHTML、VITE密钥、常见API密钥前缀、shell=True 等均无命中；subprocess 使用参数数组，见 `:64`、`:185`。绝对路径属于限定部署目标，guard 在变更前校验属主、目录类型与写权限；凭据由 `:172` 随机生成。
- 官方执行权限/调用路径 PASS：官方 `install.sh:1071`、`:1075`、`:1080`、`:1082` 复制到 `/usr/local/bin` 并在 `/usr/bin` 建链接，unit 的 ExecStart 为 `/usr/bin/1panel-core` 与 `/usr/bin/1panel-agent`；`:85` 适配为失败退出，`:88` 限制控制脚本权限；drop-in 使用 `UMask=0077`，见 `:39`。
- 测试真实性 PASS（安装准入）：现有3个测试确实读取固定发行包和官方安装器；额外独立故障注入使用真实适配后的函数，证明配置失败时不执行 systemctl。四个回退状态/端口组合及 disable失败分支已用 mock 测试，不会触碰主机服务。它们证明分支逻辑，未假称 Linux 实际部署成功。
- 测试盲区（非本次准入阻断）：仓库内3个持久测试仍未保存上述回退和故障注入用例，见 `scripts/maintenance/test_install_panel.py:9`、`:17`、`:21`；本次审查已独立执行补证。实际 systemd/nft/二进制初始化和重启后的规则持久性仍须生产验收。
- 视觉对比不适用：该范围不新增UI或邻居页面；实际官方面板浏览器验证属于源计划第4项，不以静态审查替代。

### 最终验证原始输出

适配后的真实函数在 sed 失败时：

```text
SED_FAILURE_BLOCKED: exit=1 stdout=INJECTED_CONFIG_WRITE_FAILURE
ROLLBACK state=inactive listener=False revoke=True PASS
ROLLBACK state=failed listener=False revoke=True PASS
ROLLBACK state=active listener=False revoke=False PASS
ROLLBACK state=inactive listener=True revoke=False PASS
DISABLE_FAILURE: exception propagated; access restriction retained; PASS
```

最后一次 `python -m unittest discover -s scripts/maintenance -p test_install_panel.py -v`：

```text
test_actual_package_members (test_install_panel.PanelInstallTests.test_actual_package_members) ... ok
test_escape_and_links_rejected (test_install_panel.PanelInstallTests.test_escape_and_links_rejected) ... ok
test_pinned_installer_and_entrypoint (test_install_panel.PanelInstallTests.test_pinned_installer_and_entrypoint) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.867s

OK
```

最终 `python -m py_compile scripts/maintenance/install_panel.py scripts/maintenance/test_install_panel.py`：stdout/stderr 空，exit code 0。故障注入文件位于被 Git 忽略的 `output/1panel-install/reviewer-fault-injection-fixed.sh:1`，不属于发布代码。

---

## 首次审查记录（旧快照，不作为最终结论）

- candidateId：`b77584a015bdae5db9fa3505f5acb75bf0a21e5c356c6e3c4efa41deb6451a24`
- 范围：`scripts/maintenance/install_panel.py`、`scripts/maintenance/test_install_panel.py`；需求依据为完整读取的 `docs/INTRANET-1PANEL-20261111.md`。
- 只读辅助证据：`output/1panel-install/install.sh`、`1pctl`、两份 systemd unit、实际发行包与 `before.json`。未连接生产，未执行安装，未修改实现，未提交。报告和本地故障注入脚本为审查产物。
- 本报告仅判断安装脚本准入；不批准生产安装结果、浏览器功能或监控采样。其他会话的产品文档与前端预览排除。
- 结论：**Stage 1 FAIL；Stage 2 未执行**。修复后须重新 prepare 并从 Stage 1 复核；不得登记当前快照的两阶段 PASS。

## Stage 1：需求逐项核对

| 需求 | 结论与证据 |
| --- | --- |
| 计划第 1 项：固定容器、服务、配置、证书、健康和磁盘基线 | 部分证据已有：`output/1panel-install/before.json:1` 保存容器、服务、摘要和磁盘；健康接口未在该文件体现。本次仅安装准入，最终基线验收由主 Agent 继续执行；不认定已完成。需求 `docs/INTRANET-1PANEL-20261111.md:7`。 |
| 第 2 项：固定发行包并检查真实脚本 | 完整实现：包 SHA256 和安装器 SHA256 均与代码常量一致；`scripts/maintenance/install_panel.py:15`、`:66`、`:113`；真实归档 20 个成员通过测试。官方校验文件来源由主 Agent 提供，本次独立核验本地字节与固定摘要。 |
| 第 2 项：独立目录，禁止动默认目录及既有 Docker/防火墙 | 正常路径匹配：`scripts/maintenance/install_panel.py:12`、`:97` 拒绝既有目标，`:143` 传入独立基础目录；官方脚本 `output/1panel-install/install.sh:1162` 再拼接 `/1panel`。Docker、原防火墙函数被 `scripts/maintenance/install_panel.py:47` 覆盖为只读检查；原 `main` 调用点为官方脚本 `:1287`、`:1289`。异常配置写入路径不匹配，见 HIGH-01。 |
| 第 2 项：10086 空闲检查 | 完整实现于 `scripts/maintenance/install_panel.py:106`；官方脚本 `output/1panel-install/install.sh:895` 再检查所选端口。真实端口可用性属于主 Agent 生产核验，本次未连接生产。 |
| 第 3 项：只启动面板与专属访问控制，不安装其他应用 | 正常路径匹配：`scripts/maintenance/install_panel.py:49` 跳过 AppStore，`:142` 启动专属规则服务；官方脚本 `output/1panel-install/install.sh:1125` 仅启用面板服务。实际无新增业务应用仍待安装后验证。 |
| 第 3 项：loopback 和指定公司网段，规则仅影响 10086 | 静态匹配：`scripts/maintenance/install_panel.py:18` 定义独立 inet 表，三条规则均限定 tcp dport 10086，允许所列网段后拒绝其余来源；`:39` 通过 Requires/After 在面板前启动规则。真实规则加载和访问测试未执行。 |
| 第 3 项：强随机凭据、安全入口与私有原始输出 | 随机生成和存储权限匹配：`scripts/maintenance/install_panel.py:118` 设置 0077，`:130` 使用 secrets，`:60` O_EXCL/0600 创建私有文件，`:150` 私有记录日志。但写入官方控制配置失败时仍会启动，见 HIGH-01；不可认定已保证最终初始化凭据。 |
| 第 4 项：浏览器登录、首页监控、采样、15 天保留、默认间隔 | 未执行，明确属于主 Agent 安装后的交付验收。脚本 `scripts/maintenance/install_panel.py:161` 正确提示仍待浏览器与基线验证，没有伪称完成。需求 `docs/INTRANET-1PANEL-20261111.md:10`。 |
| 第 5 项：服务未重启、摘要不变、健康正常和新增/整盘占用 | 未执行，属于安装后的验收；不能以脚本检查通过代替。需求 `docs/INTRANET-1PANEL-20261111.md:11`，脚本 `scripts/maintenance/install_panel.py:161` 明确保留后续验证。 |
| 失败回退仅处理新增面板服务与专属规则 | 部分实现，不匹配，见 MEDIUM-02。没有调用通用卸载，也没有业务服务/证书删除命令：`scripts/maintenance/install_panel.py:162`。 |
| UI、设计稿和 Spec 漂移 | 本范围没有新产品 UI，邻居页面比较不适用于安装脚本；生产面板 UI 验收未执行。除下述规则保留行为外，没有发现新增应用或收费通知功能：`scripts/maintenance/install_panel.py:45`、`:142`。 |

## HIGH-01：配置写入失败后仍启用并启动面板

需求原文：强随机初始密码及独立目录，见 `docs/INTRANET-1PANEL-20261111.md:8`、`:9`。

`scripts/maintenance/install_panel.py:71` 的注释声称关键复制保持 fail-fast，但 `:73`、`:74` 实际只替换入口并追加四个覆盖函数，没有加退出检查。真实官方脚本 `output/1panel-install/install.sh:1093` 至 `:1099` 连续修改目录、端口、用户名、密码、入口等，全部不检查结果；`:1122` 不检查初始化结果，随后 `:1125`、`:1127`、`:1128` 继续启用和启动。外层 `scripts/maintenance/install_panel.py:154` 至 `:159` 仅检查最终退出码、服务 active 与数据库文件，不能证明这些配置写入成功。

本地无部署故障注入直接抽取官方 `init_configure`、`install_and_configure` 函数；将 cp/chmod/rm/ln/mkdir/systemctl/tee/log 全部替换为无副作用 stub，并使 sed 恒返回 23。注入结果：

```text
INJECTED_CONFIG_WRITE_FAILURE
INJECTED_CONFIG_WRITE_FAILURE
INJECTED_CONFIG_WRITE_FAILURE
INJECTED_CONFIG_WRITE_FAILURE
INJECTED_CONFIG_WRITE_FAILURE
INJECTED_CONFIG_WRITE_FAILURE
INJECTED_CONFIG_WRITE_FAILURE
SYSTEMCTL enable 1panel-agent.service
SYSTEMCTL enable 1panel-core.service
SYSTEMCTL daemon-reload
SYSTEMCTL start 1panel-core
SYSTEMCTL start 1panel-agent
FINAL_STATUS=0
PROCESS_EXIT=0
```

复现脚本：`output/1panel-install/reviewer-fault-injection.sh:1`。这证明配置失败仍继续启动且函数返回成功；没有声称实际生产已经发生该故障。Bash 默认使用末条命令/管道末端的退出状态，与此结果一致：[GNU Bash Exit Status](https://www.gnu.org/s/bash/manual/html_node/Exit-Status.html)、[GNU Bash Pipelines](https://www.gnu.org/s/bash/manual/html_node/Pipelines.html)。

要求：关键复制、链接、配置替换、权限设置和服务启停须显式检查失败并停止；覆盖测试至少证明配置失败不会走到启动。不要直接给整个官方脚本加未经验证的全局 errexit，以免破坏其预期探测循环。

## MEDIUM-02：失败回退与源计划不符，异常边界过窄

需求原文：失败时“仅停止新增 1panel-core/agent 服务并撤销本次面板专属访问规则”，`docs/INTRANET-1PANEL-20261111.md:15`。

`scripts/maintenance/install_panel.py:134` 至 `:142` 已写规则和 unit、启动并 enable 规则服务，但 `try` 到 `:149` 才开始；这些阶段失败没有统一清理。`:162` 的异常处理仅 stop 两个面板服务，未检查 stop 返回码、未 disable 已 enable 的面板服务，也明确保留访问规则。既不符合计划中的撤销行为，也不能把失败状态视为已妥善回退。

要求：扩大异常处理范围；核对面板已停止后撤销本次专属规则并禁用新增自启动。如停止不能确认，为避免暴露端口而保留拒绝规则，应同步写入源计划并明确报告回退不完整。不能动既有服务、Docker 或默认目录。

## 测试与编译原始结果

命令：`python -m unittest discover -s scripts/maintenance -p test_install_panel.py -v`

```text
test_actual_package_members (test_install_panel.PanelInstallTests.test_actual_package_members) ... ok
test_escape_and_links_rejected (test_install_panel.PanelInstallTests.test_escape_and_links_rejected) ... ok
test_pinned_installer_and_entrypoint (test_install_panel.PanelInstallTests.test_pinned_installer_and_entrypoint) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.867s

OK
```

命令：`python -m py_compile scripts/maintenance/install_panel.py scripts/maintenance/test_install_panel.py`。原始 stdout/stderr 均为空，exit code 0。Python 字节码编译不是 Linux 服务部署验证。

现有测试对应 `scripts/maintenance/test_install_panel.py:9`、`:17`、`:21`，只覆盖固定安装器、归档成员和路径/链接拒绝；未覆盖关键配置失败与回退路径。

## 快照证据与审查边界

首次及审查中 `review-status` 的 currentId 与本报告 candidateId 相同，approved=false。读取实现时原始文件 SHA256：

```text
install_panel.py B88D32C2F4A95B8293BFFE313F18D6A9B6C3828F61FF5D76462C16FCB11AF169
test_install_panel.py 1DC88CA8F9317CE88CFDB7CB2D905A27A5CF858201396C2602ECC34D2F871205
install.sh 3FAA744FD158283470B48B3A971DC98CC390C7F291D4287B170416AE862DD28F
1panel-v2.5.0-linux-amd64.tar.gz 106D088FC3B1E9CAF8ADCE0B5C04D77D22AF740045CAEDF5AC694D375F58D73C
```

主 Agent 已通知将修复上述问题。此报告只约束旧快照，不为正在进行的修改提供结论。Stage 1 存在 HIGH，因此 Stage 2 代码质量、安全扫描、测试完整性及正式两阶段准入尚未完成。
