# 海外生产发布增量独立审查

- 日期：2026-10-13。
- 最终 candidateId：`47afa40574d9e37d404d43998eb7fb3165579a7b948f1929eeccb103594ecf78`。
- 范围：`scripts/release/overseas-{deploy,runtime,services,topology,verify}.py`、`package-overseas.py`、三组对应测试、前端版本 0.2.22、发布规划及 changelog。既有 Phase 25 业务实现不重复全量审查。
- 依据：`docs/OVERSEAS-RELEASE-20261013.md:5`、`docs/OVERSEAS-RELEASE-CHECKLIST.md:5`，以及 code-review/release-builder 技能。
- 结论：**Stage 1 PASS；Stage 2 PASS（发布工具代码范围）**。这不等于生产已安装、已上线、真实登录已验收或管理员已授予。主 Agent 仍须完成实际安装与公网验收，并仅对本编号登记 review-approve。

## 快照变化与已修问题

最初交接 `2757c8…`，随后改为 `79f217…`。审查期间发现两个问题，主 Agent 修改后重新 prepare 为上述最终编号，reviewer 重读变更并重新验证。旧结论不覆盖新版。

1. **HIGH，已修**：主进程 umask 077 会传给 uv，新建虚拟环境不能被非 root 执行用户遍历。旧版本在本地 Linux 隔离容器复现 `.venv` 和 `bin` 都为 0700，UID 10001 执行解释器报 PermissionError。最终版只让 uv 子进程使用 022，源码父目录显式 755，并增加真实执行用户的 import 验证。证据：`scripts/release/overseas-runtime.py:82`、`scripts/release/overseas-services.py:52`。修复复验输出见下。
2. **测试证据失真，已修**：旧日志实际为 `2 failed, 27 passed`，部署 mock 缺少 `install_edge`，两条开放入口后的故障测试没有抵达目标路径。最终补齐 mock 并新增 edge 安装失败回退测试；独立复跑 30 项全过。证据：`scripts/release/test_overseas_deploy.py:86`、`:150`、`:167`。

## Stage 1：需求符合性

| 条目 | 结果及证据 |
|---|---|
| 只读预检、复用生产配置链 | 符合工具范围。读取 live API Compose 标签，保留完整链并附加 overlay；生成配置前对 5 个新 loopback 端口 bind 检查。`overseas-deploy.py:38`、`overseas-services.py:13`。本 reviewer 未远程操作，现网基线由主 Agent 提供。 |
| 经审源码与正式前端打包 | 完整实现。提交/审查双门禁、受控源码白名单、正式入口资产引用检查、压缩资产秘密审计、逐字节归档回读。`package-overseas.py:18`、`:59`、`:85`、`:110`；负例与篡改测试 `test_package_overseas.py:26`、`:63`、`:102`。 |
| 独立数据库/Redis/桶/凭据/网络 | 完整实现。新随机独立秘密，业务 app 使用 overseas_app，identity 不持业务数据库或存储秘密；资源只连 overseas 网络。`overseas-topology.py:70`、`:87`、`:119`；真实 Compose 合并测试 `test_overseas_topology.py:119`；安装检查 `overseas-verify.py:40`。 |
| 原生目录、认证副本、worker/outbox 隔离 | 完整实现。独立系统用户、0700 目录和0600认证副本、共同环境及节点名；systemd 环境采用双引号格式。`overseas-services.py:44`、`:62`、`:77`；`overseas-topology.py:21`、`:93`。未对共享可写 HOME 作复用。 |
| 不进行收费调用、不假登录 | 符合。沙箱 probe 仅 `--version`；HTTP 检查均匿名，真实登录和收费模型明确 NOT_TESTED/NOT_RUN。`overseas-services.py:81`、`overseas-verify.py:73`。 |
| 张帅首位超管 | 真实国内身份唯一候选读取已实现，无伪造成员或会话。`overseas-services.py:108`。**实际授权仍待统一身份登记后执行** `hengxin-smart-image/backend/app/overseas/members/bootstrap.py:12`；主 Agent 已明确保留该交付待办，不得称已完成授权。 |
| 迁移、备份、停止接纳并排空 | 完整实现。build 安装测试通过才允许 prepare/deploy；国内0026前置、排空前不停止执行器、静止后备份、迁移0027；海外 Compose 依赖 migrate 后启动 API，ready 核对海外0009。`overseas-deploy.py:25`、`:38`、`:62`；`overseas-runtime.py:60`；`hengxin-smart-image/backend/app/overseas/health.py:17`。 |
| 回退与开放入口后的不确定边界 | 完整实现。尚未开放时排空新执行器、恢复旧配置/前端及旧服务，保留加性schema；尝试开放web后失败则关入口并保留执行器状态，要求检查，不盲回退。`overseas-deploy.py:101`、`:114`；故障测试 `test_overseas_deploy.py:109`、`:119`、`:132`、`:150`、`:167`。 |
| 旧 API 与0027兼容依据 | 已核实旧提交60babaa的 `backend/app/health.py:15` 不比较迁移head，仅检查连接及job_outbox；0027仅加可空列及索引，`backend/migrations/versions/0027_identity_session_binding.py:12`。这支持回退设计，不替代生产回退实测。 |
| 文件哈希、匿名鉴权及一期健康 | 完整实现安装后逐文件哈希、服务active、资源网络、匿名401、入口文件与资源哈希检查。`overseas-verify.py:28`、`:59`。实际执行结果待安装后采集。 |
| 版本、范围漂移、UI | `hengxin-smart-image/frontend/package.json:3` 仅升至0.2.22；`docs/OVERSEAS-CHANGELOG.md:3` 不宣称已上线。本次没有新增业务页面或样式；视觉邻居对比不适用于版本/运维脚本增量，沿用先前 Phase 25 UI 审查边界。 |

上述路径表中脚本简称均位于 `scripts/release/`。发布检查清单中的真实角色登录、实际付费模型、生产灾备恢复/RPO/RTO等未验证项继续保留，不用本次工具审查替代。

## Stage 2：质量、安全与测试

- 源文件均少于300行；打包、拓扑、安装、切换、验收分文件负责；异常通过失败关闭入口或停止后续操作传播。`overseas-deploy.py:114`、`overseas-topology.py:39`。
- 未发现本次新增脚本中硬编码生产密钥、eval、shell=True 或危险HTML注入。子进程使用argv；秘密文件0600，拓扑文件排他创建；原生源码可读权限与认证秘密权限分开。`overseas-runtime.py:26`、`overseas-topology.py:148`、`overseas-services.py:68`。
- 生产网络标识、固定端口、固定宿主路径为本次单机发布设计；真实端口检查发生在生成配置前。`overseas-services.py:20`。端口检查与Docker启动之间仍依赖发布窗口内无并发占用；若冲突则启动失败，不会据此强停未知进程。
- 故障测试实际覆盖接纳关闭后发现任务、备份/迁移失败、edge安装失败、web开放失败、公网验证失败、镜像ID漂移。`test_overseas_deploy.py:109` 起。Docker Compose 实际合并参与本次30项测试，无skip。
- 依赖审计现存 critical=0/high=36/moderate=34/low=1，证据 `output/overseas-release-audit.json:2804`；本次无依赖变更，不能称依赖零漏洞。
- 新发布最终镜像的 `installation-tests.log`、实际非root服务安装验证、沙箱probe和公网检查目前未执行；代码强制安装测试成功并固定镜像ID后才继续。`overseas-deploy.py:25`、`:38`、`:64`。既有phase25镜像只用于本 reviewer 的 Linux 权限复现，不作为最终发布镜像验收证据。

## 原始验证输出

reviewer使用项目后端虚拟环境运行三组测试（系统Python没有pytest，未把失败的系统Python调用算作验证）：

```text
..............................                                           [100%]
30 passed in 1.26s
```

本地无网络一次性 Linux 容器，复现修复后的 uv 子进程 umask022；随后切UID10001执行新解释器：

```text
Using CPython 3.12.10 interpreter at: /usr/local/bin/python3.12
Creating virtual environment at: /tmp/review-venv
Python 3.12.10
VENV_MODE 0o755
BIN_MODE 0o755
```

Python编译检查（内存compile，无代码改写）：

```text
overseas-deploy.py: compile PASS, 158 lines
overseas-runtime.py: compile PASS, 187 lines
overseas-services.py: compile PASS, 114 lines
overseas-topology.py: compile PASS, 166 lines
overseas-verify.py: compile PASS, 87 lines
package-overseas.py: compile PASS, 162 lines
test_overseas_deploy.py: compile PASS, 197 lines
test_overseas_topology.py: compile PASS, 149 lines
test_package_overseas.py: compile PASS, 151 lines
```

正式前端构建日志由主Agent提供，reviewer读取 `output/overseas-release-build.log` 末尾原始结果：

```text
✓ built in 52.58s
```

审查结束前只读 `review-status` 的 currentId 仍为 `47afa40574d9e37d404d43998eb7fb3165579a7b948f1929eeccb103594ecf78`，approved=false，等待主Agent依报告登记。reviewer未修改部署代码、未远程写入、未提交、未登记批准。
