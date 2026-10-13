# 海外删除、归档保护与已安装Skill验收

状态：开发、本地测试与独立两阶段审查完成；生产发布和线上验收待执行。

## 已取得证据

- `infra/identity-test/run.py --delete-skills`：两库完整迁移、真实身份/API/MinIO、管理员删除、其他角色拒绝、名称/版本校验、删除中写入拒绝、仅两张归档而第三张及图需/附件/会话目录被删、原图和ZIP哈希一致、非相关人归档拒绝、另一个任务/Skill/国内数据不变，全部通过。日志`output/delete-skills-http.log`，结束删除仅此运行创建的容器。
- 同一流程以`--serve --origin http://localhost:3022`运行，浏览器真实验收通过：归档独立查看、大图、单图下载与ZIP；管理员确认/取消/异步删除/清理后移除；四种非管理员没有入口；Skill两列只读、工作台同源选择；390px窄屏。证据`output/playwright/delete-skills/real-result.json`及截图。
- 真实安装资源：14包181文件111,321,938字节；在临时目录重复安装两次、每轮复制后逐字节对比通过。相较源件仅必要内部标识适配增加118字节。具体清单/哈希见独立安装manifest及`OVERSEAS-INSTALLED-SKILLS-RUNBOOK-20261013.md`。
- 安装目录更新后，已排队轮次仍读取旧版参考文件和完整二进制资源；网页Skill写接口不再开放；管理页/工作台返回一致目录，HTTP验收通过。
- 发布/打包/目录归一故障测试：54通过。覆盖安装或sandbox验证失败保持海外入口关闭、不回退业务数据库、共享目录inode不一致/可写挂载/旧volume/少文件/root身份探针拒绝放行。
- PostgreSQL数据库与迁移完整集合：70通过，日志`output/pg-regression-full-20261013.log`。历史测试修正为明确单角色、显式legacy分析入口、新工作台审核不自动创建Job；保留真实并发/回滚/迟到断言。新删除先/归档先锁序及历史0012→0013归档回填通过。
- 前端最终319项测试通过；正式`pnpm build`含类型检查通过，4705模块，36.42秒。日志`output/delete-skills-frontend-tests.log`、`output/delete-skills-frontend-build.log`。
- 新对象归属前缀与孤儿清理改动后，真实HTTP全流程再跑通过：`output/delete-skills-http-final.log`。
- 前端现有生产依赖审计：0 critical，36 high / 34 moderate / 1 low（`pnpm audit --prod --audit-level critical`退出0）。本轮未改依赖版本与锁文件；这些历史依赖告警未在本轮升级修复，不能宣称全仓无漏洞。
- 最终Linux完整后端：1951通过、166显式外部环境依赖跳过，15条现有弃用/SQLAlchemy警告，239.39秒；0失败。日志`output/delete-skills-backend-final.log`。海外PG依赖部分已在独立真实PG集合70项补跑通过，真实模型生成不在本轮收费验收范围。

## 未完成验证

- 独立审查 Stage 1 / Stage 2 PASS，候选 `643bdd423c44876e69ad4fce7d4bdd005a45965cefc5c9d81eabd0f4e518c781` 已按协议批准。报告 `docs/reviews/OVERSEAS-DELETE-SKILLS-FINAL-20261013.md`。reviewer 独立44项专项、54项发布测试、113文件语法编译、前端类型及新页与邻居实际视觉核对通过。
- 从受审提交打包、生产14包安装、真实Worker sandbox、线上页面视觉验收。

所有业务删除测试均在一次性隔离环境，测试图片由本地PIL生成，模型调用为0。生产未创建删除测试任务，未删除用户真实任务。
# 归档改派权限复核

首轮独立审查发现归档负责人未随任务改派更新，已在持有 Task 行锁的改派事务内同步 Archive.designer_id。新增真实 HTTP 的原负责人/中间负责人/最终负责人列表、详情、原图、ZIP 权限与字节验证，覆盖删除前后、幂等重放、事务失败回滚；旧版工作流归档同样覆盖改派后删除下载。真实 PostgreSQL 验证改派与删除竞争的两种顺序，删除保留最后合法负责人。专项 51 项通过，原始日志 `output/archive-assignment-regression-20261013.log`。首轮失败报告保留，新候选重新执行两阶段审查，未通过前不部署。

