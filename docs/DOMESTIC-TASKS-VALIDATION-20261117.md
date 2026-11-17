# 国内任务与管理员任务中心验证记录

本记录是开发与隔离验证证据，尚不表示已部署生产。业务版本0.2.74；用户确认的独立预览为 `hengxin-smart-image/frontend/preview-task-center/`。

## 功能与构建

- 前端 `pnpm test`：584项通过；`pnpm typecheck`：exit 0。证据 `output/task-frontend-unit.log`、`output/task-frontend-typecheck.log`。
- `vite build --mode production`、domestic scope：48.86秒完成，产物位于 `output/tasks-production-build/`。证据 `output/tasks-production-build.log`。构建生成的无关全局组件声明删减已恢复，不改变海外组件声明。
- 两个正式浏览器回归脚本使用隔离浏览器、截获API：五业务入口、逐轮Skill的15次发送、独立草稿与幂等、1920/1000/390宽度裁切；管理员37个只读请求、分页/筛选、消息/附件/实时同步、删除与撤权反馈通过。证据 `output/playwright/task-explicit-skill/report.json`、`output/playwright/task-manager/report.json`。这些结果不冒称真实模型调用。
- 主Agent另用真实FastAPI、独立PostgreSQL schema及正式前端联调：必填创建任务后0会话、显式创建两个方案、独立草稿与刷新恢复；真实发送入队时完成按钮禁用；测试端模拟执行终态后完成任务变只读，重开后方案草稿保留。没有连接生产数据库或调用收费模型。
- 管理真实接口查看其他成员任务与切换方案前后，Task/Conversation/Turn/Job四张表全字段JSON的SHA256相同；管理员自己的任务也无设计输入/新建入口。管理空会话不暴露未提交草稿。证据 `output/tasks-live-{before,after}-management.json`、`output/playwright/tasks-real-admin-detail.png`。
- 独立审查发现状态筛选会误缩小汇总计数，已修为按业务/成员/名称范围统计全部/进行中/已完成，再独立计算状态筛选后的列表total。新增真实HTTP用例覆盖普通及管理入口，排除其他成员、业务和名称；相关最终11项通过，证据 `output/tasks-backend-final-targeted.log`。

## 后端与历史迁移

- 完整Linux后端原始结果：3419通过、256跳过、2失败，656.95秒；两个失败均为隔离容器缺Bubblewrap。证据 `output/tasks-backend-full.log`，跳过项不称已验证。
- 安装Bubblewrap后发现默认Docker seccomp禁止测试所需user namespace；独立派生测试容器无网络、源代码只读挂载，允许该沙箱测试创建namespace后，原两个用例均通过（3.78秒），没有修改产品沙箱实现。证据 `output/tasks-bubblewrap-isolated-final.log`。环境配置依据 [Docker官方seccomp说明](https://docs.docker.com/engine/security/seccomp/)。
- 新增真实PostgreSQL测试覆盖0044前后历史字段/FK、同业务双任务各10会话、跨任务读写/文件拒绝、新旧API完成门禁、并发上传与完成/删除、持久删除失败重试、原目录真实净回收及归档独立副本保留。
- 生产仅作只读版本/历史采样；上线时须排空停止后重新采样，不能把在线采样代替迁移前后对账。

## 审查与发布门禁

初次专项发布审查发现两项HIGH：实际启动调用绕过重启策略恢复、成功核验遗漏非目标配置漂移。已修复并补充最终验收/台账异常关闭国内入口及可重试恢复。修复后完整发布工具套件504通过、15子测试通过；4个可选Docker跳过用例已在宿主独立Compose实际执行，4项全部通过。真实独立PostgreSQL迁移进程锁、UID1001、publisher沙箱及pg_dump/restore均执行通过，具体证据见专项维护方案。

最终快照 `bdc78af52f5564caa852690e03d2626b14a94ce73ff07e295256dcc2bff51fe5` 的产品及专项发布工具均通过独立两阶段审查，详见 [合并审查凭据](reviews/DOMESTIC-TASKS-20261117.md)。发布复核另独立执行专项90项、scope/engine/catalog/GC回归139项及8个子测试、真实Docker4项，全部通过。安装稿已静态复核，但实际安装和生产切换尚未执行。依赖审计critical为0；既有high73/moderate51/low11，本次未升级依赖、不宣称全库无漏洞。

数据库0043→0044影响、备份、停止围栏及前向恢复方案见 [专项维护方案](DOMESTIC-TASKS-MAINTENANCE-20261117.md)。生产执行与验收须另记实测结果。
