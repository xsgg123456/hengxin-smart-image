# Skill 轻量管理生产发布 · 2026-09-21

用户授权提交Git并部署，发布至 https://zhitu.qhhengxin.top/ 。

- 功能提交：`f02b1e07f744df39a939ae98877cfb617fcea6c0`，`feat: 简化 Skill 管理并保留任务执行快照`。
- 批准快照：`ea3d522e40ef2c8a7800ede8ae208c1596fe98f0b5541990ca3182e0d28e7004`；发布编号 `light-skills-20260921-f02b1e0`。
- 白名单包534文件、4673253字节，SHA256 `782c4bc8b740befb51b65ce37ced85df2dc3cefee27f336567c585092fcbe483`。扫描无开发者路径、私钥、环境文件、数据库或会话文件。使用已通过正式构建的HTTP前端产物。
- 依赖审计critical=0，既有high62/moderate39/low5；本轮未更改依赖。
- 发布目录 `/opt/hengxin-releases/light-skills-20260921-f02b1e0/`，部署退出0、`DEPLOY_COMPLETE`。
- 备份目录 `/opt/hengxin-backups/light-skills-20260921-f02b1e0/`；包含数据库、旧应用和配置、Worker配置及systemd覆盖文件。数据库备份137069字节。切换前两次确认无在途任务。
- 数据库0013升级0014，Skill目录、状态、当前快照和软移除字段已存在。API/Outbox镜像切换为本发布，原生Worker active；五并发环境值及systemd进程池配置保留。
- 原生代码及前端534文件哈希一致，API/Outbox各124后端文件哈希一致。公开ready为PG/Redis/MinIO全部up，首页200，匿名管理目录接口401。
- 登录生产浏览器验证Skill管理列表、描述展开全文、默认绑定、引用保护和取消版本入口。两条现有Skill均可用。点击一次“同步 Skill”，原生Worker真实接收并完成新同步作业，页面退出同步状态且Skill继续可用。

## 边界与回滚

现有管理员Skill目录未修改，旧`<name>/<version>`布局继续兼容；这次生产同步验证旧目录兼容链路，新平铺目录及完整对象快照的校验见本地Linux/API回归记录。未更改模型、默认绑定和五并发，未自动创建付费生成任务。

回滚先关闭接纳、确认无在途任务，再恢复备份应用及配置、旧镜像并验证健康。0014新增字段保留；若已有自动快照，禁止直接降级删除`catalog_snapshot`等字段，旧应用不支持这些新快照时需评估任务兼容。不可用旧数据库备份覆盖发布后的新业务数据。历史本地Skill发布树始终保留。
