# 海外删除、归档保护与已安装Skill验收

状态：开发、测试、独立两阶段审查、生产发布与线上验收完成。业务版本为 0.2.28，发布提交 `3a060c8cebcebe876931b3b1c636ecb6bc2fb9b5`；生产细节见 `OVERSEAS-DELETE-SKILLS-PRODUCTION-20261013.md`。

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

## 最终审查与生产验证

- 独立审查 Stage 1 / Stage 2 PASS，候选 `643bdd423c44876e69ad4fce7d4bdd005a45965cefc5c9d81eabd0f4e518c781` 已按协议批准。报告 `docs/reviews/OVERSEAS-DELETE-SKILLS-FINAL-20261013.md`。reviewer 独立44项专项、54项发布测试、113文件语法编译、前端类型及新页与邻居实际视觉核对通过。
- 从受审提交打包，1408文件、8,574,604字节，所有包内文件与提交逐字节一致。生产镜像内测试1845通过、167显式跳过、1排除；日志 `output/release/overseas-20261013-3a060c8/installation-tests.log`。
- 生产14包181文件安装完成；API/native/真实uid999 sandbox目录device/inode完全一致，逐包只读检查通过，模型调用0。证据 `output/release/overseas-20261013-3a060c8/SKILLS_VERIFIED.json`。
- 线上管理页实际显示14项、名称/描述两列、没有添加入口，沃尔玛原版与新版同时存在。任务列表仍为原有2条，删除确认要求完整名称；空名称确认按钮禁用，取消后原任务保留。成品库正常显示0套。截图在同发布目录 `screenshots/`。
- 初次切换被真实worker探针发现公共Skill父目录权限700而阻止放行；仅修正该root所有的无链接目录为755后，全量复验成功，海外入口恢复，国内及身份容器不变。发布脚本永久修正新增3项真实Linux root权限测试，相关发布回归57通过；候选 `deac809ca46f4033c0ad7acd4ae1acfd3c525e9618ffbeacbd86974e4831f0c5` 两阶段审查通过并批准，报告 `reviews/OVERSEAS-SKILL-DIRECTORY-MODE-20261013.md`。

所有业务删除测试均在一次性隔离环境，测试图片由本地PIL生成，模型调用为0。生产未创建删除测试任务，未删除用户真实任务。
# 归档改派权限复核

首轮独立审查发现归档负责人未随任务改派更新，已在持有 Task 行锁的改派事务内同步 Archive.designer_id。新增真实 HTTP 的原负责人/中间负责人/最终负责人列表、详情、原图、ZIP 权限与字节验证，覆盖删除前后、幂等重放、事务失败回滚；旧版工作流归档同样覆盖改派后删除下载。真实 PostgreSQL 验证改派与删除竞争的两种顺序，删除保留最后合法负责人。专项 51 项通过，原始日志 `output/archive-assignment-regression-20261013.log`。首轮失败报告保留，新候选重新通过两阶段审查后才部署。

