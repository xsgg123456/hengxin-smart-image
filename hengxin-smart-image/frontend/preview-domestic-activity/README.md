# 国内调用与执行 · 独立交互预览

用户于2026-11-11要求基于当前真实前端一比一制作合并页，先看效果再确定实施。随后用户已认可此预览作为正式合并页的外观与交互基准；已确认需求见根目录 Product-Spec「国内管理中心轻量化」。本目录仍是独立示例预览，不是正式数据接入或已上线实现；以下为原预览制作范围及验证记录。

1. 复用正式 ArtSidebarMenu、ArtHeaderBar、ArtPageContent、Element Plus、prototype.css 与既有页面样式，沿用真实品牌、导航、页签及主题。原版对照直接渲染 ApiUsage.vue / monitor.vue，使用本地演示适配器。
2. 合并为「调用与执行」单入口；默认按人员统计，同页切换执行记录。人员/北京时间日期/生成类型共享；点人员保留日期及类型下钻；点顶部状态清空其他筛选查看全部时间对应状态，范围显式展示。
3. 概况按执行记录条数统计，执行中包含收图、取消中、等待重试；API请求与已启动CLI轮次分开计算。人员生成数与执行记录可对账；累计图片是首次+修改，不重复计算采用/恢复。
4. 任务详情和服务详情放抽屉。服务未知不显示在线或零；底层各阶段、心跳、并发仅在详情显示。模拟记录明确标记；手动刷新具有加载反馈。
5. 有正常、空、加载、错误、服务异常预览场景。筛选、分页、日期、查看记录、详情与原版对照可操作。不实现成员页或历史待核对移除（已单独记录）。
6. 全部数据内存模拟；无生产API、无代理、无生产写入。不提交、不部署，不修改正式业务文件或Spec/Brief/DEV-PLAN。

验收：独立vue-tsc与Vite构建；1920×911原版/新版对照、1280×800及390×844布局；浏览器验证下钻、状态筛选清空条件、空/错/加载/异常、分页、详情、刷新；核查无业务API请求；独立两阶段审查。

运行：frontend下 `node node_modules/vite/bin/vite.js --config preview-domestic-activity/vite.config.ts --mode demo`，打开 http://127.0.0.1:3041/preview-domestic-activity/index.html。

## 本轮验证

- `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-domestic-activity/tsconfig.json` 通过。
- `node node_modules/vite/bin/vite.js build --config preview-domestic-activity/vite.config.ts --mode demo` 通过，21.48秒。
- 浏览器21项检查通过：6人人员汇总、50张图片合计、人员下钻8条、今日过滤2条、类型叠加1条、状态下钻清空筛选且汇总4种执行中阶段、执行抽屉、20条分页及第二页、关键词空态、错误/重试/加载/空数据/服务异常、两个真实原版组件、零业务API请求、零浏览器运行错误。
- 1920×911、1280×800、390×844检查文档宽度均等于视口宽度，概况、服务状态、筛选及汇总区均在水平可见范围；窄屏表格采用原生横向滚动及固定操作列。桌面和窄屏实际截图已查看。
- 证据在仓库 `output/domestic-activity-preview/`：typecheck.txt、build.log、browser-results.txt、layout-results.txt，以及merged/baseline/records截图。浏览器是本机独立会话，不继承生产认证。
- 仅验证该独立内存交互预览；没有后端集成、生产数据验证或正式上线。用户决定最终设计后再同步正式源文档和实施计划。
