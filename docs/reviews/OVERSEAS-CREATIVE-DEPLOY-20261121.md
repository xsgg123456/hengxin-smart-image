# 海外创作工具集生产专项审查

**Stage 1 PASS · Stage 2 PASS**

核准审查对象为 `3973fbdc382007faefc95d3dfc54ed381716ceb590362a9e1a5c6210b04fd8ff`。独立重算工作区编号，与 harness 登记一致。范围为应用提交 `faab6d0` 之后的八个发布工具及测试 Python 文件、`docs/OVERSEAS-CREATIVE-RELEASE-20261121.md` 第 3–15 行。该手册的原始文件 SHA256 为 `11a602fa7b5e1e9ebede82b680f671fc8f5735fa7241b78bd1202569cdee6af5`。应用功能已独立送审，本次只验证生产发布行为。生产发布结果须由主 Agent 另行核验。

初审 `eb7ea7ea…` 缺海外当前前端基线校验，手册故障状态命令缺 scope。第二次送审 `45e04daa…` 已增加门禁，但测试的假存储路径抛出 TypeError。最终候选修复了两项问题。正反用例只改变前端版本，国内 publisher 始终在位，两次均未写事务。证据见 `scripts/release/intranet/domestic_tasks_release.py:59`、`scripts/release/intranet/test_overseas_creative_release.py:97`、`docs/OVERSEAS-CREATIVE-RELEASE-20261121.md:11`。

## Stage 1 · 逐项验收

下表中的文件名均位于 `scripts/release/intranet/`，另有标注的除外。

| 手册条目 | 结果和证据 |
|---|---|
| 1、2　两组制品、来源和暂存 | 两个真实归档均已逐文件重新计算 SHA256，归档内普通文件集合等于 manifest 清单加 manifest 本身。共验证 overseas 613 个文件、shared 629 个文件。实际两包及旧基线通过专项清单校验，精确差异为 29 个后端路径，仅有 0029 一个迁移。候选来源树、前端摘要、运行依赖、后端 delta 门禁见 `overseas_creative_policy.py:20`，登记暂存路径检查见 `domestic_tasks_release.py:66`、`design_shared_frontend.py:52`。 |
| 3　锁、固定基线和 SQL 摘要 | `release_cli.py:31` 检查主机和 root，随后在台账锁内路由。`domestic_tasks_release.py:59` 和 `overseas_creative_policy.py:7` 同时固定海外前后端 133f16ae、schema 0028 及候选 faab6d0。以应用虚拟环境独立运行 Alembic offline，SQL 与演练文件逐字节相等。SQL 和库名、角色、版本检查见 `overseas_design_engine.py:13`、第 53、98 行。安装前旧指针及清单核验、隔离套件、指针切换逻辑见随包操作材料 `output/overseas-creative-20261121/install.py:32`、第 71、85 行。 |
| 4　海外排空、备份、数据保持 | `scopes.py:17` 和 `scope_actions.py:27` 将排空限定到海外 worker。`engine.py:162` 先停入口、排空，再停服务。`domestic_tasks_engine.py:97` 将持锁、确认停止、备份、历史快照排在 DDL 之前。备份限海外库，核对 pg_restore 目录、字节数和 SHA256，见 `operations.py:59` 和 `overseas_design_history.py:18`。六张历史表以行数和完整原有字段的有序行摘要核对，新列可空，技能绑定为空，见 `overseas_creative_history.py:13`、第 26、49 行。本地隔离 PostgreSQL 18 的实事务验证记录见下文。 |
| 5　中断和新旧事务隔离 | 新专项具有独立 MARKER、RECEIPT，旧专项及普通发布相互闭锁，见 `overseas_creative_policy.py:9`、`domestic_tasks_marker.py:25`、`release_cli.py:51` 和第 75 行。`engine.py:229` 在排空失败后恢复已暂停消费者和入口。`domestic_tasks_release.py:203` 依实际 schema 选择旧配置恢复或同候选向前续发。`domestic_tasks_engine.py:119` 验备份摘要、schema 和数据身份，第 195 行校验候选摘要。旧 schema 分支不执行数据库还原。 |
| 6　shared 前端、国内及共享后端、独立回退 | `design_shared_frontend.py:26` 要求海外前后端完成、schema 0029、共享前后端处于各自约定旧版。第 58 行只接受 shared/frontend。`scope_engine.py:35`、第 87 行限定挂载和进程范围；`domestic_tasks_release.py:107`、`scope_snapshot.py` 中的 `unchanged_other` 核对其他组的版本或进程身份。按组前端回退取该组 previous、保留原后端，见 `scope_release.py:44`。 |
| 7　运行验收与清理 | `release_cli.py:103` 的 verify 重采运行态并对比台账。`domestic_tasks_release.py:133` 在成功状态落账后执行清理。手册第 13 行要求业务 HTTP、鉴权及国内首页摘要；随包 `output/overseas-creative-20261121/live_check.py:16`、第 25 行与 `verify_http.py:28` 实现这些验收。实际生产结果不在本次离线审查内。 |

需求与交付范围匹配。新增内容属于已有正式工具的海外专项入口，文档第 3 行的初始空绑定和历史身份处理与 `Product-Spec.md:1643` 及迁移实现一致。此候选只修改发布工具、测试及手册，没有新增业务页面或 API，未触发页面设计比对。

## Stage 2 · 质量及测试

- 现有状态机继续承担加锁、排空、恢复和按组切换，新策略集中保存候选与摘要，新历史模块只验证迁移前后数据，见 `domestic_tasks_release.py:55`、`overseas_creative_policy.py:7`、`overseas_creative_history.py:67`。八个待审 Python 文件各自低于 300 行。
- 对八个文件扫描了常见密钥前缀、危险求值、HTML 注入、shell=True 等模式，扫描无命中。数据校验 SQL 拼接的表名、列名均来自模块常量，见 `overseas_creative_history.py:6`、第 15、27 行。外部命令以参数数组调用，数据维护连接使用本地套接字，见 `overseas_design_engine.py:39`、第 103 行。
- 此次独立运行海外策略、共享前端和引擎的 19 个用例，另跑恢复、备份、重启策略及既有海外策略的 83 个用例。两组有重叠。临时 PostgreSQL 18 使用独占 Unix socket、关闭 TCP，在六张表分别插入历史行，实际调用本次 capture、迁移执行器、verify。核验了空绑定、新列、实际权限及存量摘要。该实测使用最小合成基线与实际 SQL，未调用生产。
- LOW。共享准备参数错误时，两条命令均提示旧命令名 `design-shared-prepare`，见 `release_cli.py:85`。正确的参数由同处校验；该提示不影响门禁或事务结果。

独立核验和编译的原始成功输出如下。

```text
overseas 613 470bcc288ca530adcad81b8a6d219662b5bf875a605137e151361397fcc5f77f
shared 629 8eece2f8f055b3a35eb5468deafbe6e39fe811c054ca6d37e4d34b8a6ba405f9
Exact verified deltas: 29 backend paths, one migration; both package manifests accepted.
8 release Python files compiled
Alembic offline SQL SHA256 78b04ea29df9834afd16fd3127a520771d2185c40a013ae902cf009d17bc507e
PostgreSQL 18 private socket: 0028 -> 0029 committed once; six seeded tables retained; bindings empty; grants verified
...................                                                      [100%]
19 passed in 3.25s
........................................................................ [ 86%]
...........                                                              [100%]
83 passed in 5.08s
```
