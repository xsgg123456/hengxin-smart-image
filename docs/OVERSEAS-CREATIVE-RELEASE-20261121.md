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

## 生产验收

2026-11-21T14:58+08:00 完成正式生产入口核验。海外前后端及共享登录前端均运行 `faab6d0434dcab1f42ef743d60d4fd32160fc714`。专项工具源提交为 `20e3d28`，生产安装版本为 `b056e0ae4da64d89`。共享后端为 `2bc8acc7ecf4`，国内前后端均为 `009a1808f5c4`。

- 当前海外数据库为 `overseas_0029`，国内为 `0046`。已校验海外备份 847,008 字节，SHA256 为 `6291470897344099245455b5e3fb2c6f90ca057647e3b47ecbc54e550fe42e6d`。
- 迁移前后逐行摘要一致，涉及 8 条任务、8 条任务 SKU、6 套归档、159 条归档图片、9 条岗位及 24 条技能状态。新绑定表为空。
- 海外包 SHA256 为 `470bcc288ca530adcad81b8a6d219662b5bf875a605137e151361397fcc5f77f`，共享包 SHA256 为 `8eece2f8f055b3a35eb5468deafbe6e39fe811c054ca6d37e4d34b8a6ba405f9`。正式 HTTP 入口的海外 96 份、共享 105 份前端资源均与包内摘要一致。
- 正式工具 verify、status 成功，发布事务已结束，三组均保留上一成功版本。海外和共享事务的自动清理均完成，分别净释放 23,908,352 和 9,363,456 字节。
- 国内和海外就绪接口及共享身份配置返回 200。未登录请求访问我的创作、成品筛选和工作台 Skills 管理均返回 401。国内首页摘要与发布前一致。
- 八个入口、身份隔离、成品下载与选图归档在隔离业务环境验收。生产验收使用只读请求，未创建测试任务或调用模型。
