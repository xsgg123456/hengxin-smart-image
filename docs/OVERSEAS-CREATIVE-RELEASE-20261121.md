# 海外创作工具集生产升级

本次授权涵盖海外应用、海外数据库 0028 → 0029，以及识别非设计人员的共享登录前端。海外工作台从八个入口创建任务。Skills 初始绑定为空，由管理员手动配置。历史创作者缺少身份依据时保留空值。

## 发布顺序

1. 从已审应用提交用 `scripts/release/intranet/package_release.py` 分别构建 overseas 和 shared 包，核验清单、来源提交和 SHA256。生产使用 `hengxin-prod` SSH 入口，主机必须为 `hengxin-ai-245`。
2. 将两包上传到 `/opt/hengxin-lan/` 的独立文件，核对哈希，用当前生产工具的 `stage.py` 分别暂存。
3. 在发布锁内核验旧工具指针及文件哈希，安装已审专项工具并运行隔离测试。工具必须识别固定基线、候选和 SQL 摘要。
4. 运行 `release.py creative-prepare --scope overseas --mode full --release <已暂存海外路径>`，再运行 `creative-deploy --scope overseas --mode full`。工具排空海外任务、核验备份，锁定库名、所有者和历史迁移版本后，在一个事务内执行 DDL。核验既有任务、SKU、归档、成品图、岗位和技能记录；新字段允许为空，新绑定表初始为空。
5. 中断时先查 `release.py creative-status --scope overseas --mode full` 和台账，使用 `creative-recover --scope overseas --mode full`。迁移提交前恢复原海外服务，提交后使用同一候选向前恢复。排空失败须恢复接单，禁止将数据库恢复到旧时间点。
6. 海外切换完成后，通过 `creative-shared-prepare --scope shared --mode frontend --release <已暂存共享路径>` 准备共享前端，再执行 `deploy --scope shared`。共享前端按组独立回退。国内组与共享后端须保持发布前的运行版本。
7. 运行正式工具的 `verify`、`status`，核对版本、待处理事务、清理回执，以及通过业务 HTTP 入口实际提供的资源摘要、海外 API 鉴权和国内首页摘要。

所有生产命令均使用 `/opt/hengxin-intranet-tools/current/scripts/release/intranet/` 下的工具。
