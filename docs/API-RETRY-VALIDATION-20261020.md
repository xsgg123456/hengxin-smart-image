# API 重试与上游保护验收记录

## 范围

合同：API-RETRY-PLAN-20261020.md；前端计划版本0.2.44，国内数据库0031。只涉及国内 API 生图通道、必要的共用前端资产和国内发布入口。保留所有已有成功图片与冻结修改输入，不创建收费生图压测。

## 发布变更摘要（0.2.44）

- 新轮自动/手动重试最多20次，45分钟发送窗口，300秒请求超时及持久随机退避。
- 共用发送限速、在途预算、故障冷却和单请求探测，未知结果阻止重复生成。
- 等待任务公平调度、停止后续重试、保留晚到成功结果及数据库恢复。
- 正式页面显示真实轮次、倒计时、冷却和停止状态，历史记录兼容。

## 验收状态

实现前现有调度/适配器基线：`python -m pytest tests/test_api_image_task_slots.py tests/test_api_image_relay.py -q --disable-warnings`，30 passed（只证明既有基线）。

### 前端与交互

- 前端类型检查通过；完整单测317/317通过。
- `corepack pnpm build`最终退出码0，Vite构建37.20秒，版本0.2.44。日志：`output/api-retry-20261020/frontend-build.log`。
- 实际dist通过Vite preview运行后，`scripts/api-retry/browser.mjs`最终七组浏览器检查通过，页面错误0；接口隔离，未请求生产。覆盖倒计时、防双击、停止响应丢失后刷新确认、在途停止/晚到成功、冷却排队、历史兼容、390px布局及新建页策略说明。截图和记录：`output/playwright/api-retry/`，主Agent/reviewer实际查看宽窄屏与新建页。
- 本地真实FastAPI + 独立PostgreSQL schema + MemoryStore + 假上游的实际HTTP联调通过4项：停止入库、刷新恢复、手动重开0/20、成功文件保持及窄屏。未mock业务API；仅外部生图为假客户端。证据：`output/playwright/api-retry-live/`。临时schema及服务已清理。
- `pnpm audit --prod --audit-level critical`退出码0，无Critical；既有依赖仍报告36 High、34 Moderate、1 Low，本轮未更改依赖或锁文件，不把该结果描述为无漏洞。日志：`output/api-retry-20261020/frontend-audit.log`。

### 发布准备

- 发布脚本全量879 passed、3 skipped、309 subtests passed。两项默认跳过的Docker/PG专项已显式补跑通过，证明停止超时不强杀、0031重复迁移保留旧字段、完整备份隔离恢复、拒绝直接降级。
- 生产只读基线与执行范围见`API-RETRY-RELEASE-NOTES-20261020.md`；此时仍未生产写入。

### 后端与最终交付

- 后端API相关最终193项通过（61.21秒），含真实PostgreSQL跨进程限速、单探测、未知容量、停止竞态、旧代次结果及0031重复迁移。极长Retry-After保持持久冷却，管理员恢复不绕过；PG保存和JSON编码已覆盖。
- 首轮Windows全量2018 passed、12 failed、281 skipped。4项国内旧测试前提已修正，独立32项复验通过：未知结果需确认、永久失败可新轮、真实发出后的租约失联、0030旧schema反射插入。没有通过放宽安全断言消除失败。
- 另外8项为Windows缺少POSIX安全文件打开能力，在Linux容器只读挂载当前app/tests、禁网复验涉及的三个完整文件，21 passed；生产安全读取代码未放宽。
- 完整Linux回归启用4种独立PostgreSQL测试URL：2179 passed、25 skipped、1 deselected；唯一失败为0030迁移测试依赖完整仓库目录，而首次挂载仅有`/app`。用`/repo/hengxin-smart-image/backend`、infra与scripts真实目录结构补跑整个文件，9 passed（28.95秒），无代码修改。日志分别为`output/api-retry-20261020/backend-linux-full.log`和`backend-linux-retirement.log`。与已有安装测试入口一致，六个依赖本机Codex环境的文件不在容器运行、前端源代码字段对照项在该容器取消选择；未把跳过项计为通过。
- 最终独立审查Stage 1/2 PASS，候选`1ee4be48411bf1a532d0f4f649cbe7fc238d697745af58eb2fc96ae78bd6e04f`；报告`reviews/API-RETRY-PRODUCTION-20261020.md`。原失败和修复过程另有INITIAL报告，未隐去失败。Git提交、包审计及生产部署继续执行，不将未执行项计为通过。
