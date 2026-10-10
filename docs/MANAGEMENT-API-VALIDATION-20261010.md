# 管理中心 API 统计本地验证

## 实施范围

需求依据：`MANAGEMENT-API-IMPLEMENTATION-20261010.md`。正式管理页读取 `/management/api-usage`、`/management/api-monitor`、`/management/execution-settings`，旧接口保留兼容。统计事实使用0025迁移，API独立心跳使用0026迁移。

已核对真实配置：API准入5套、每批10图，请求180秒、下载60秒、租约360秒；CLI并发5、7200秒。正式页面读取其所在环境实际值，不硬编码上述数值。API CLI图片修改不加载Skill，保留旧业务Skill绑定、钉钉配置和配置审计。清理页只读显示实际开关及1天/7天规则。

## 验证环境与证据

- 生产仅完成此前只读核查，无迁移、回填、配置保存、部署或模型调用。
- 隔离PostgreSQL容器 `hx-management-pg-test`，端口64652；并发测试每项独立schema并自行回收。
- 完整后端：Linux容器 `docker run --init ... python -m pytest -q --disable-warnings -p no:cacheprovider`，同时提供 `TEST_DATABASE_URL` 和 `API_IMAGE_TEST_DATABASE_URL`，**1643 passed, 17 skipped, 15 warnings**（最终返修后全量复跑，274.41秒）。日志 `output/playwright/management-real/backend-tests.log`。17项为既有环境条件跳过，不能视为已验证。
- 随后增加监控并发说明与只读清理配置，重跑三个相关后端测试文件：**34 passed**。覆盖聚合、监控、配置保存权限与故障回退。
- 前端 `pnpm test`：**236 passed**；`pnpm typecheck`：退出0。新增测试包括真实Vue组件的加载/空态/失败重试/分页/明细/已删除禁跳。
- `pnpm build` 生成正式构建，日志 `output/playwright/management-real/build.log`。
- PostgreSQL全链迁移从空库到0026；有测试数据时降到0024再升至head，结果 `0026 (head)`；API统计仍为10个历史创建任务、230次请求、当前9个任务、10个未知请求。
- PG四线程回填不重复；实际执行、CLI预检、采用/恢复、七天清理保留统计已覆盖。自动清理不开启生产调度。

## 浏览器实测

正式development页面连接隔离后端8009、前端3026，使用专门本地测试用户与合成数据，不连接生产。测试保留的本地服务仅供本次验收。

- `output/playwright/management-real/check-usage.js`：真实数据库10天日报分页，当前库存9与历史创建10区分；230次请求含10未知，成功率分母排除未知；分页汇总不变；已删除任务无跳转按钮；503注入后不保留旧汇总，重试恢复；700px宽无页面横向溢出。
- `check-settings-monitor.js`：读取5并发/7200秒；仅在隔离库将5改4再恢复5，页面同步读取且审计版本递增；钉钉与Skill表单保留；禁用渠道显示不可用，缺心跳说明无法判断节点；480px宽截图与溢出检查通过。
- 截图：usage-empty.png、usage-execution.png、usage-narrow.png、deleted-detail.png、settings.png、settings-mobile.png、monitor.png、monitor-mobile.png。
- 控制台503仅来自有意注入的故障测试。初次热更新联调中旧响应契约导致读取失败，完整刷新与重试后通过。

## 限制与发布前步骤

首轮独立审查发现并返修两项：来源不明旧版本从已知生成量分离为 `unverifiedVersions`；CLI提交统一为固定“已提交”事件，采用同时更新执行事实。新专项覆盖源投影、回填前后计数一致、旧提交暂态修正、采用状态刷新；针对性回归29项通过，前端236项与正式构建再通过。新增浏览器截图 `usage-verified-unknown.png` 确认“来源待核实版本 1（不计生成或采用）”实际渲染。

历史无法证明的操作者/重试/类型/CLI启动保留未知标签，不补猜测数据。Token与费用无完整回执显示未提供。新API心跳需部署新Worker才有独立观测；未观测到时显示未知。清理开关不代表清理服务在线。

上线前仍需用户确认；届时需先执行迁移、运行幂等历史回填 `python -m app.modules.management.api_stats.backfill`，再按发布流程更新服务并核对心跳、汇总和API业务。当前尚未执行这些生产步骤。

## 最终独立审查

R2两阶段PASS，独立复跑41项通过。报告：MANAGEMENT-API-R2-REVIEW-20261010.md；批准候选 fe0aed04b4e36e3284a4a61441657a8f03dde11ab85305cdff99b17087ba792b。首轮问题已返修并纳入最终全量回归。
