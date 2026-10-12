# 海外二期部署准备清单

这是Phase25的交付准备文档，不是部署完成记录。本轮只使用本地随机命名测试资源，未推送、未改生产、未调用收费模型。正式上线另行确认；以下未勾选项须在目标主机验收。

## 目标环境与权限

- [ ] 固定本次批准Git快照、前端构建和后端镜像digest，保存前一版本及真实Compose覆盖链。现有`compose.overseas.yaml`基础拓扑不含原生CLI服务，不能把API ready当作执行服务已就绪。
- [ ] 核定同机CPU、内存、磁盘空间/IO、PG连接、模型账户配额；海外作业全局最多5，系统配置还受部署环境上限约束。512MiB磁盘准入只是最低保护，不能代替实际资源预算。
- [ ] 独立海外数据库、owner/app账号、私有桶及应用凭据、带密码Redis、网络和执行/Skill目录；应用只持DML权限，不持数据库owner或MinIO root秘密。按`infra/.env.overseas.example`配置，实际env不入Git。
- [ ] 身份服务提供海外专属服务密钥和可信同源入口；国内成员权限不能继承。真实钉钉企业、回调、容器免登、Cookie与HTTPS在目标域名验证。
- [ ] 以核实的企业ID和用户ID执行`python -m app.overseas.members.bootstrap`，确认首位海外超级管理员；不能从国内管理员自动授予。管理员要做运营或设计动作需另授相应角色。

## 迁移与执行接入

- [ ] 关闭写入口并暂停领取，等待running/collecting/cancelling退出；uncertain保留占槽，核实PID、boot身份及启动时刻，不能按租约过期盲重跑。保存当前作业和outbox对账。
- [ ] 完成独立数据库与对象备份，在独立恢复目标核对记录数、哈希、私有访问和图片版本引用后再迁移。
- [ ] 使用owner执行`alembic -c alembic.overseas.ini upgrade head`，确认海外`overseas_0009`、国内`0027`；应用账号不能改DDL和版本表。0008负责既有方案的图片槽位回填，0009新增Skill/配置/审计及可空usage，保留既有payload。
- [ ] Linux主机配置固定CLI二进制/版本、Bubblewrap、海外认证文件与执行目录，参考[执行运行说明](OVERSEAS-PHASE21-RUNBOOK.md)。迁移应使用当前head，旧运行说明中的0006仅为Phase21历史节点。
- [ ] 独立worker与outbox共用海外目录和相同PID视图/节点名；不同节点名不得相同。配置`OVERSEAS_ENABLE_CODEX_EXECUTOR`只在前述准备通过后启用，fixture/dev identity/test jobs保持关闭。
- [ ] 同一模型账号也不共用可写HOME/session目录。将来换海外账号只修改海外认证材料，停排空后验证，国内配置不变。
- [ ] 正式域名验证五角色菜单/API/文件授权、真实资料、方案、生图、单图返工、审核归档下载及改派即时撤权。另行授权小额真实模型验证，记录质量、耗时、超时及额度；离线fixture不能证明这些能力。

## 备份、恢复与回滚

- [ ] 制定并确认备份频率、加密、异地副本、保留期、RPO/RTO及恢复负责人；本地演练不代表生产灾备指标达标。
- [ ] 在写入静止且执行排空后，使用匹配服务端主版本的`pg_dump -Fc`备份海外数据库，并同步所有正式资料、图片版本及归档所引用对象；保存对象key/size/SHA-256清单。备份也包含成员、会话、Skill文本和审计，按敏感数据保护。
- [ ] `pg_restore --exit-on-error`只恢复到新建空库，使用独立空桶恢复对象；对比所有表记录与全部对象checksum，再用隔离API核对归档版本、授权下载和管理配置。绝不直接覆盖当前生产库或将测试账号带入生产。
- [ ] Redis仅承担传递/会话等运行状态，作业和outbox以数据库为准；恢复后重新投递queued允许幂等领取，uncertain必须先核实旧进程。身份/业务会话的失效策略应单独确认，不假设恢复后继续有效。
- [ ] 回滚先停写/排空，再回退应用镜像/前端/原生执行代码与配置；迁移未提供破坏性downgrade，禁止盲目降库。若需恢复备份，先保全新增业务数据并制定回放/切换方案。
- [ ] 正式资料、生成图片、返工历史与归档默认长期保留；自动清理保持关闭。没有明确保留策略及恢复验证，不启用清理任务。

逻辑备份与自定义格式恢复用法依据[PostgreSQL pg_dump文档](https://www.postgresql.org/docs/17/app-pgdump.html)及[pg_restore文档](https://www.postgresql.org/docs/17/app-pgrestore.html)。本地流程拓扑为PG17，隔离资源Compose使用仓库固定PG16镜像；生产演练须匹配实际版本。
