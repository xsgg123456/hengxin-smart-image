# 累计生成图片与记录分页：本地验证

## 交付范围

按用户批准的预览落实正式前后端：累计生成=首次+API修改+CLI候选，采用和恢复不重复计数；默认全部时间/权限内全部人员；移除调用统计的库存展示；换图记录和日报20/50/100分页。实施合同见 [USAGE-TOTAL-IMPLEMENTATION-20261010.md](USAGE-TOTAL-IMPLEMENTATION-20261010.md)。

仅修改统计读取/聚合/响应契约及两页交互，不修改生成执行器、采用/恢复/下载事务，不新增数据库迁移。旧库存响应字段保留兼容，新页面不使用。来源不足的历史版本继续单列待核实、不计入累计，不以库存填补。

## 自动验证

- 后端完整套件在本地 Linux 容器运行 `python -m pytest -q --disable-warnings -p no:cacheprovider`，使用隔离PG测试环境及逐测试临时schema：**1649 passed, 17 skipped, 15 warnings in 310.31s**。17项为现有环境条件跳过，不算已验证。日志 `output/playwright/usage-total-real/backend-tests.log`。
- 新专项 `python -m pytest -q tests/test_usage_generated_totals.py --disable-warnings`：**7 passed**。最后补充的56条真实列表分页用例晚于完整套件收集，另行运行通过，未把它冒充包含于1649项。
- 专项实际调用隔离API事务和执行器替身：首次10张、API修改2张、CLI候选1张=13；采用幂等、恢复、七天清理、任务删除后仍为13；ZIP下载200；分类型、分人、北京时间边界、默认跨年全量、详情分页与日报对账、历史未知及非法查询均覆盖。
- 前端 `pnpm test`：**238 passed, 0 failed**，日志 `frontend-tests.log`。包含真实Vue组件、契约校验和分页composable行为；20/50/100回首页保筛选、删除纠页、过期响应不覆盖、故障重试。
- `pnpm typecheck`：退出0，日志 `typecheck.log`；最终声明版本另行验证 `typecheck-final.log`。
- `pnpm build`：退出0，**built in 38.47s**，日志 `build.log`。构建产物仅本地。

日志目录均为 `output/playwright/usage-total-real/`。首次Docker命令因绑定覆盖Linux虚拟环境、随后因缺少仓库父路径未能启动完整套件；纠正为保留镜像虚拟环境并挂载完整仓库后，上述完整运行通过。没有安装或改动生产环境。

## 浏览器与视觉

真实development前端3028 → 本轮后端8011 → 独立PG数据库；没有预览路由或模拟前端。数据为本轮隔离合成事实：57历史任务（1已删除）、56可见任务，总产出741=570+171。

`check-usage.js`、`check-records.js` 两脚本返回 **passed:true**，日志记录实际GET参数和响应。默认全量、跨页汇总稳定、日报分页、三种生成类型/人员/日期筛选及重置、明细13=10+2+1、删除任务禁跳、执行消耗、加载/503失败/重试/空态、390px内容边界均通过。记录真实pageSize从20切50/100/20，均回第一页并保留状态及搜索。

保留 `usage-default.png`、`usage-narrow.png`、`deleted-detail.png`、`loading-narrow.png`、`error-narrow.png`、`empty-narrow.png`、`records-50.png`、`records-narrow.png`。沿用既有页面与已确认预览的组件和样式。窄屏表格保持内部横向滚动，页面控件未超出可见范围。

浏览器限制：本轮未配置MinIO，素材缩略图显示下载失败；这不是实际生产图片检测，浏览器不声称验证了下载。真实下载逻辑通过后端隔离事务专项验证，无收费生图。详细环境与命令见输出目录 `REPORT.md`。

## 收尾与发布边界

本轮8011/3028服务、Playwright会话及独立数据库已清理，旧本地服务与数据库未改。没有访问/写入生产，没有开启自动清理，没有Git提交或推送。生产部署等待用户另行确认。

独立审查见 [USAGE-TOTAL-REVIEW-20261010.md](USAGE-TOTAL-REVIEW-20261010.md)；最终快照以审查凭据为准。预存dev-builder技能改动不属于本轮业务实现。

两阶段审查均PASS，reviewer独立复跑7项专项与最终类型检查通过。已登记最终候选 `7b990a99b6a52523b93de71ce899ac2cf6ce36144fff8b0c2a2f99b9adb96b8d`，review-status确认当前内容匹配且approved=true。构建生成声明随后按开发服务器实际使用整理为ElDatePicker/ElTabPane/ElTabs三项，差异已复核，最终声明版本类型检查退出0。
