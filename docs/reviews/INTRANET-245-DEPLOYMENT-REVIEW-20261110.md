# 内网 245 部署模块独立审查

- 最终 candidateId：`cd3df50e4eb053f62984c511693cd2e564b7a5665d0f912b882e63661cd7993e`。
- 初始 candidateId：`b741f9f50f7068c4a5cdacef4326c77c0336274c615959e87d5cf11e98b2f2b5`，不批准初始版本。
- 范围：`hengxin-smart-image/scripts/migration245/` 下 `data_copy.py`（D）、`data_copy_test.py`（DT）、`build_compose.py`（B）、`build_compose_test.py`（BT）、`install_files.py`（I）、`install_files_test.py`（IT）。下文缩写行号均指这些完整路径。
- 依据：Product-Spec.md:1、DEV-PLAN.md:1、docs/INTRANET-245-PLAN-20261110.md 第 3–5 节，以及 docs/INTRANET-245-ACCEPTANCE-20261110.md 的 B01/B02/B05/B09、D01–D05/D09、A07。其余业务、真实登录、重启及并行运行项属于后续部署验收，不在脚本准入范围。
- 方法：完整静态阅读、真实隔离 PostgreSQL 16、合成配置测试、无网络 Linux Python 3.12 容器。审查员没有连接服务器、修改实现或提交。
- **结论：Stage 1 PASS；Stage 2 PASS。仅准入本报告六文件对应的三个模块；不代表 59 项迁移验收完成。** 数据导出必须走受保护管道；目标必须是已确认的新机和新库。仅主 Agent 可登记同一候选的 review-approve。

## 快照与修复复核

初始 I:85–100 仅检查 native_hashes 子集，两个运行时二进制只查存在和执行位；未检查多余文件和二进制内容。主 Agent 修改为最终 I:89–114：代码文件集合精确相等，二进制清单限定两个固定绝对路径并核对 SHA-256。IT:28–52 实测多余文件和篡改二进制被拒绝。

初始 I:159–166 创建目标文件时用 `open('xb')`，随后才 chmod。审查在 Linux umask 022 下调用实际 install(private)，仅替换目标目录与主机 guard，三份文件写入中均为 0644。此为 Stage 1 HIGH：私钥/配置写入期间权限不满足保护要求；发现时停止进入 Stage 2并通知主 Agent。最终 I:178 以 `os.open(O_CREAT|O_EXCL, 0600)` 创建；同一独立复现确认写入中和完成后均为 0600。该修复后才继续两阶段。Python 官方 [os.open 文档](https://docs.python.org/3.12/library/os.html#os.open) 说明创建 mode 受 umask 限制，与实测一致。

前轮 D 的 NULL 版本缺陷已改为 D:69 的 `IS NOT TRUE`；DT:199–211 在真实 PostgreSQL 验证源/目标空版本表及 NULL/false 拒绝、true 接受。旧数据报告的 FAIL 不直接套用于新候选。

落盘期间曾出现中间候选 `7ad22e22a2f8fdc32ec6aa41a1a934a4705992fd054a56c0fbc6300ccdeda3a6`，仅 B:158 的报告 uid_mapping 海外1002改为999；审查员以反向字节替换及哈希证明仅该差异，并复跑9测试。主 Agent 随后撤回该报告值修改，全部六文件回到最终 `cd3df50e4eb053f62984c511693cd2e564b7a5665d0f912b882e63661cd7993e`；末次B原始SHA-256再次确认为下表值。宿主机UID调整未执行，后续native UID参数化必须另审，本报告不批准账号修改或原生消费者启动。

最终原始字节 SHA-256：

| 文件 | SHA-256 |
|---|---|
| D | 93ADC198BEC7A4D0FFCF3502A127859F08356CE1499129104FD26610C829A4BB |
| DT | C5D5F8070357A085C4B3C6C80CA034D58F7C396D51E468F8DD8E8EDCF6350973 |
| B | 5637EC4ACD4419FABB835FC3C691227BBC1B99CC390805A85AE5ED8FC182FDED |
| BT | 4B8F31E71B30DB5051B9BBBAFF5D7BD21AF1B34D8E70B06606CCC557B3F97F9F |
| I | 726F44F2639B7D1FA1EC3977935EC68E61386C1E943950E5F1EB0AE2784F83D9 |
| IT | A3E008EBF3BF7B2F8DC3B6C13E0FCE53555A576FE35BEA747E33A81A003F1BDF |

collect_runtime.py 与 transport.py 分别仍为 F2205A319A352245FA482D8AB3EA6DD627298E4A995A2265E0EC001BE72E6AF8、E3792B1A011BA747016A8F88821E2F31A96F4CEF6E6F38C727F8A2D749E47C6B；可引用 [此前两阶段报告](INTRANET-245-COLLECTOR-REVIEW-20261110.md)，本次未重新批准其他新增模块。

## Stage 1：Spec Compliance — PASS

### 数据模块

| 条目 | 判定与证据 |
|---|---|
| 国内 8 表用户/身份/角色/申请/事件/成员审计/设置/设置审计 | 完整实现，D:14–23 显式列及类型，D:110、204 导出和导入，D:213 完整行/数量/摘要校验。DT:213 国内 pending 往返通过。 |
| 海外 8 表成员/角色/申请/事件/成员审计/设置/Skill 状态/管理审计 | 完整实现，D:24–33；管理审计 D:112 只选 skill.*，D:158–176 再拒绝业务 action、未知 JSON 字段和值。DT:43、142 验证过滤及 disabled 原样保留。 |
| 所有 83 表处理 | D:35–38 完整 39/44 表清单、D:121 仅导出白名单、D:188–198 对全部目标非版本表查空或精确种子。逐表映射沿用 [前轮报告附表](INTRANET-245-DATA-REVIEW-20261110.md)，相关 SCHEMA/ALL_TABLES/SEEDS 与处理路径未改；两张版本表现由 D:69、89 拒绝空值，覆盖前轮唯一失败项。不存在跳过未白名单表的导入入口。 |
| 默认运行门闩、旧业务/队列/登录态排除 | D:44–54、191–198 只接受新端默认种子，源运行状态不导出；DT:159 dirty seed/旧业务拒绝、DT:142 重跑拒绝。Redis/MinIO 实例为空仍须部署层验收。 |
| 只读一致性、版本和列结构 | D:72–107、134–138 使用只读可重复读事务、固定表/列/PK/版本、超时及快照字段；DT:190 验证写入被数据库拒绝，DT:199–211 验证 NULL 修复。 |
| 目标隔离和事务回滚 | D:221–231 固定本地 Docker/PG socket、新前缀及精确 confirmation；D:183–217 锁全表、保持约束、按 FK 顺序插入、提交前核验；DT:170、181 真 PG 验证摘要和 FK 失败整事务回滚。 |
| 数据/SQL 保真 | D:57、203 使用原始 JSON 的 UTF-8 十六进制编码，非 Python 重新序列化；DT:142 验证高精度 JSON 数字往返，DT:53 注入样本不进入 SQL 原文。 |
| 私有导出和脱敏 | D:255 只拒绝 TTY，实际私有管道权限由调用层保证，不能单独直接向工具控制台导出；D:234–242 不回显数据库原始错误，DT:58 验证客户记录不进入异常。 |

### 配置生成模块

| 条目 | 判定与证据 |
|---|---|
| 16 服务及锁定镜像 | B:14–18、129–132 精确服务集合及数量、sha256 ID；B:164 pull_policy=never。BT:112、151、157 验证数量、不可变镜像及异常 inventory。 |
| 内部秘密轮换、外部配置保留 | B:54–85、133–134 分环境生成密码并成套更新 DB/Redis/MinIO/identity；BT:81 验证新秘密接线、外部 API 哨兵值保留。真实海外/identity Redis Cmd 的 `$REDIS_PASSWORD` 引用由主 Agent 脱敏实查提供，仓库 infra/compose.overseas.yaml:69 与 compose.identity.yaml:8 同构；B:166–170 为国内显式添加 requirepass。 |
| 新网络/新卷/共享挂载、无旧数据连接 | B:153–156、176–190 新命名卷和桥，应用数据端点 B:58–67 定向新端；海外 execution/skills 转新主机 bind。BT:112 核对不 external、loopback 和共享路径。源宿主机同名 bind 在新机是否为空、无远程挂载是部署层前置，不以名字代替实查。 |
| 原 runtime 参数和配置等效 | B:88–124 保留 command/entrypoint/user/资源/安全参数/healthcheck/restart；BT:132 验证关键字段与 Compose `$` 转义。B:199–202 生成原生环境，移除 systemd 瞬态字段。 |
| 正式 origin/回调字面和代理 | B:78–84 保持正式 HTTPS origin、容器代理桥与 native loopback；B:203–204 只改国内 upstream 和 forwarded protocol，不写 DNS/钉钉配置。BT:128、142 核验 nginx/代理。受控浏览器解析与真实回调归后续验收。 |
| publisher alias 修正、端口不外露 | B:173–175 移除错误海外 API alias，B:191–193 全部发布 loopback；BT:120、119 验证。不直接建立公开 HTTPS 入口。 |
| 主机/输出守卫和不启动服务 | B:229–239 固定 root/hostname、桥网段冲突检测、source 路径无链接；B:212–226 固定目录、独占 0600 输出；BT:171、184 验证不覆盖/错误主机。入口只生成文件，无 docker up。 |

### 文件安装模块

| 条目 | 判定与证据 |
|---|---|
| 只在新机私有根，拒绝覆盖 | I:30–38 固定 hostname、全祖先 root/不可组他人写，私有根无共享权限；I:76–83 拒绝已存在/链接目标和不安全祖先，I:160/172 安装前两次核验。IT:106、114 验证拒绝现有路径和旧 hostname。 |
| 包成员路径和类型白名单 | I:41–67 限制四类来源，拒绝绝对/父路径/重复/链接/设备；IT:52–67 覆盖正常与异常成员。private 仅两份 TLS 与 config.toml，auth.json 不在根白名单。 |
| 先验证再安装 | I:162–168 私有新 staging、data 解包过滤、verify 成功后才写最终目标；I:174–181 不覆盖地复制。失败不被视为部署成功；部分目标需人工核对后处理，不能直接覆盖重试。 |
| 代码和运行时完整性 | I:89–114 精确代码文件集合、原始大小/hash、两个独立 binary hash；IT:28–52 Linux 实际拒绝多余文件和篡改。主 Agent 确认 runtime-binaries.sha256 已走受保护传输；审查员未自行访问远端。 |
| 当前前端完整资源 | I:115–125 对发布清单中 frontend/dist 的集合和每文件 hash 精确检查，IT:69–83 验证错字节/多文件拒绝。688 数量来自已采集清单，不在合成测试伪造真实交付成功。 |
| Skills 全树字节与前后稳定 | I:126–144 前后 manifest 字节相等、路径安全、实际文件集合相等、逐文件 hash；IT:85–104 验证源变更和坏字节拒绝。文件与 DB 状态的跨系统一致性、权限/属主/执行能力仍须部署验收。 |
| 私密文件从创建即受保护 | I:145–150 staging chmod600，I:178 独占0600创建；独立 Linux 实际 install(private) 观察写入中和最终模式均0600，详情见输出。 |

### 未实现、范围外和漂移

- 本次限定脚本准入范围无未实现 HIGH；初始两个安装问题已在最终快照修复。
- D:3 明确完整 Alembic 建库是前置；D:72 的约束检查不证明迁移链完整或缺失约束已复建，序列/全 schema/FK 验收不能跳过。
- I:90–99 不比较 native_hashes.mode；Skills manifest 不含 mode，copytree 不保留原 UID。权限/属主映射、真实 Codex/bwrap 执行、发布索引与 DB 引用是后续 B03/D05，不能把本报告当作这些条目 PASS。
- B:139 使用一个新 Compose 项目 hengxin-lan 和三组独立服务/卷/网络命名，相对方案三项目名属于实现组织差异，不改变两套数据独立的授权目标；未增产品功能。
- 无新增 UI/交互/设计稿，UI 一致性、占位引导、邻居页面视觉比较不适用。
- B06–B11、D06–D10、A01–A09、国内/海外全部业务及重启/一天观察未由这些脚本验收；源码复制不等于功能验收。保持计划清单的未完成状态。

## Stage 2：Code Quality — PASS

- 结构：D/DT/B/BT/I/IT 分别277/232/247/192/193/123行，均小于300；数据/配置生成/文件安装职责分离。Python 无 any 或动态 eval/exec，异常路径 fail closed（D:237、B:246、I:59/95/111/114）。
- 安全扫描：六文件逐行阅读及危险模式检索，无 eval/exec/shell=True、前端秘密暴露或硬编码真实令牌。D:57/62 用静态标识符与hex字面值；B:133 随机秘密、B:224 0600；I:58 拒绝tar链接/越界、I:178 独占0600。测试里的 old-* 和 EXTERNAL_API_KEY 为合成哨兵，不是真秘密。绝对路径是经授权的固定部署边界。
- 测试真实性：DT 的8个PG用例实际跑SQL及事务，不只是检查字符串；但夹具自建表/部分约束，未运行Alembic，不能证明全迁移链。BT 的9用例为合成inspect，只证明转换，不证明真实Compose能启动。IT 最终7用例在Linux无skip；新增执行位测试在Windows标skip是正确平台约束，本审查用真实Linux补齐。实际私密安装路径另有独立函数集成复现，避免只测纯函数。
- LOW，BT:33–38：合成海外/identity Redis Cmd 未模拟生产 shell 动态密码引用，当前用主Agent提供的脱敏真实Cmd与仓库定义交叉核查；建议后续fixture直接覆盖该生产形态，避免未来字面密码Cmd漏接线。
- LOW，I:183–186：receipt只列验证文件数量和归档hash，不含最终文件全树hash/属主/权限；部署层必须保留安装后独立清单。本轮未将receipt当资源回收或全功能验收。

## 原始验证输出

在初始候选执行 `DATA_COPY_PG_TEST=1 python -B -m unittest data_copy_test build_compose_test install_files_test -v`；最终 D/DT/B/BT hash 与这次运行一致；B 中途报告元数据修改又撤回，已再次核对原始哈希。原始末段：

```text
Ran 27 tests in 11.122s

OK
```

其中data为12项（8真实隔离PG+4单元），compose为9项，旧install为6项。真实PG无发布端口、network none、tmpfs且仅清理本审查随机命名容器。

最终候选独立 Linux 原始完整输出，退出码0：

```text
test_archive_accepts_scoped_files_and_rejects_duplicates (install_files_test.FileInstallationTests.test_archive_accepts_scoped_files_and_rejects_duplicates) ... ok
test_archive_rejects_traversal_absolute_links_and_scope (install_files_test.FileInstallationTests.test_archive_rejects_traversal_absolute_links_and_scope) ... ok
test_code_rejects_extra_files_and_changed_binary (install_files_test.FileInstallationTests.test_code_rejects_extra_files_and_changed_binary) ... ok
test_existing_destination_is_never_overwritten (install_files_test.FileInstallationTests.test_existing_destination_is_never_overwritten) ... ok
test_frontend_requires_exact_manifest_and_bytes (install_files_test.FileInstallationTests.test_frontend_requires_exact_manifest_and_bytes) ... ok
test_skills_requires_unchanged_source_and_complete_hashes (install_files_test.FileInstallationTests.test_skills_requires_unchanged_source_and_complete_hashes) ... ok
test_wrong_host_fails_before_accessing_target_paths (install_files_test.FileInstallationTests.test_wrong_host_fails_before_accessing_target_paths) ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.018s

OK
```

私密文件集成复现，修复前原始输出：

```text
private_destination_mode_during_copy= 0o644
private_destination_mode_during_copy= 0o644
private_destination_mode_during_copy= 0o644
```

修复后相同隔离流程原始模式输出（仅目标临时路径、hostname guard替换，调用真实安装函数）：

```text
private_destination_mode_during_copy= 0o600
private_destination_mode_during_copy= 0o600
private_destination_mode_during_copy= 0o600
private_final_modes=0600 PASS
```

最终六文件内存compile原始stdout如下，退出码0，无编译错误stderr：

```text
compile PASS: data_copy.py
compile PASS: data_copy_test.py
compile PASS: build_compose.py
compile PASS: build_compose_test.py
compile PASS: install_files.py
compile PASS: install_files_test.py
```

报告前review-status返回currentId与最终candidateId相等。未写.needs-review，未登记review-approve，未把原始候选或旧FAIL报告覆盖为最终批准。
