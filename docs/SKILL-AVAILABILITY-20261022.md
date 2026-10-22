# 海外 Skill 开关实施与验证（2026-10-22）

## 已批准行为

全部已安装 Skill 保留在管理目录；AI 设计工作台只显示开启项。迁移 `overseas_0020` 仅初始化 `amazon-new-product-image-set`、`amazon-new-product-aplus` 为开启，其余没有状态记录时为关闭。按安装声明名称保存，刷新/更新包不重置状态，新安装默认关闭。开关写入版本和操作者审计；已冻结作业和重复请求核实不受影响。

## 账号绑定与发布接线

本次已通过生产浏览器现有登录态的 `/api/overseas/v1/auth/me` 只读核实当前成员，显示名为张帅。使用唯一海外成员 ID，不能以姓名或超级管理员身份替代绑定。对应部署环境片段在本机 Git 忽略目录 `output/skill-availability/owner.env`，未把个人标识硬编码进产品代码。

后端环境变量 `OVERSEAS_SKILL_TOGGLE_OWNER_ID` 接入 OverseasSettings 与海外 Compose 公共环境；空配置禁止所有人切换。管理 API 同时要求现行 `skills.manage` 权限，普通系统设置 API 不接受此绑定字段。生产发布时需将已核实片段合并到海外实际环境并重建 API，在海外独立数据库执行迁移；使用原生环境启动的 API 亦须设置同名变量。worker继续使用既有冻结包，不按新开关追溯阻断在途任务。不得重置当前数据库或删除安装包。

本轮未执行生产迁移、环境修改或服务切换。正式发布须沿用既有隔离、排空、备份和版本验收流程，验证当前账号 canToggle=true、另一管理员为false、工作台初始只列两个目标。不能用本地测试结果声称线上已经生效。

## 实现参考

采用现有执行 gate 串行化切换与新任务冻结，并用 populate_existing 刷新已缓存状态，遵循 [SQLAlchemy ORM 查询文档](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing)。不升级框架。

## 验证记录

本轮测试及独立审查证据如下；全量回归边界在末节列明。

### 本轮已获得证据
- 当前前端全量：`node --import tsx --test tests/*.test.ts`，351 passed，0 failed；`pnpm build:overseas`，vue-tsc通过、vite built 36.75s。日志 `output/skill-availability/frontend-tests.log`、`frontend-build.log`。
- 后端Windows专项：94 passed、9 skipped（PG/宿主条件）；另配置绑定用例1 passed。已补真实PG：`test_overseas_skill_availability_migration.py`、`test_overseas_skill_availability_postgres.py`、`test_overseas_management_postgres.py`、`test_overseas_database.py` 共18 passed，日志`postgres.log`。独立WSL PostgreSQL18只监听127.0.0.1:55439，库名hx_skill_availability_test，各fixture另建随机库/schema清理。
- Linux相关全链路：availability、owner_configuration、installed_skills、installed_titles、management、management_freeze、studio 共63 passed，21.29s，日志`linux-focused.log`。此前Windows safe open unavailable 属平台能力，不修改产品或跳过以掩盖，已在Linux验证该旧执行用例通过。
- 浏览器通过cua运行真实Vue和隔离API：所有者开启/关闭，其他账号只读，409刷新、503读回不假成功、加载失败；工作台过滤、旧选择同会话刷新/整页刷新均禁发且保留草稿，清空后可发送。1366×900和390×844无横向溢出，按钮裁切检查为空。截图在`output/skill-availability/`，是隔离验收数据，不是线上配置成功凭据。
- 全后端Linux回归及独立快照审查已完成，最终结论和边界见下节。

### 最终回归边界与结论
- 全后端Linux运行：2347 passed、24 skipped、1 failed，392.11s；日志`linux-full.log`。失败为未修改的国内 `test_api_retry_gate_pg.py::test_oversized_retry_after_survives_postgres_json_and_admin_resume`，隔离PG默认Asia/Shanghai把UTC年9999上界转成+08年10000导致驱动解码失败。
- 用 `git archive HEAD hengxin-smart-image/backend` 创建独立原始代码基线，同环境同用例复现完全相同失败，日志`head-timezone-baseline.log`。只把本次隔离测试数据库时区调整UTC后，当前代码的整个 `test_api_retry_gate_pg.py` 6 passed（5.63s），日志`retry-gate-utc.log`。未修改国内产品逻辑、未修改用例、未修改生产时区。该既有非UTC极端日期边界另记，不能将原始全量结果写成零失败。
- 独立code-reviewer对本轮Skill范围两阶段PASS；报告`docs/reviews/SKILL-AVAILABILITY-20261022.md`。独立复测后端19项、前端25项、PG并发2项、迁移1项均通过，并独立对照真实桌面/窄屏与相邻页面样式。
- 当前代码仅本地交付，前一轮附件草稿恢复与素材批量移除变更保持；生产尚未迁移/切换。发布后才会使账号专属开关和初始两项在正式页面生效。

