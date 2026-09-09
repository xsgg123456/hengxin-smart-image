# Phase 7 验证记录

日期：2026-09-09。依据 Product-Spec v0.17、DEV-PLAN Phase 7、PHASE7-PLAN.md。

## 交付

- 模板接 PostgreSQL：创建、编辑、停用、共享逻辑删除、分页搜索排序、文件引用校验和版本冲突；有序图片及实际 Skill 引用保存在不可变版本中，历史只读查看。
- Skill 接私有 MinIO 和 Linux Worker：真实 ZIP 校验、上传、依赖检查、独立目录安装、失败重试、启停与模块默认配置；四角色共享模板，仅超级管理员管理 Skill。
- 通用 Job/outbox 支持任务种类、租约与心跳、旧认领失效、终态停止派发。安装卷持久化；Redis 中断恢复和进程重启使用真实容器验证。
- 前端沿用模板卡片、对话框、ArtTable 和 Element Plus；补历史查看与默认绑定。绑定按用户确认规则解析并冻结，无可用版本保留草稿。

## 审查闭环

第一轮后端 Stage 1 通过，Stage 2 发现两项 MEDIUM，见 PHASE7-BACKEND-REVIEW.md：

1. 默认选择在锁定前缓存旧 available 状态。锁查询增加 populate_existing，回归以两个独立事务在解析和锁定之间真实停用版本，保存必须422。
2. MinIO 写入失败后版本号被永久占用。未完成上传禁止安装，允许同校验和原包重传，成功版本仍不可覆盖；分别测试写对象前/写入后断连。

修复后独立最终审查见 PHASE7-REVIEW.md：Stage 1 PASS、Stage 2 PASS，未关闭 HIGH/MEDIUM 为0；一项 LOW 可维护性建议不阻塞验收。最终审查已汇合真实容器、浏览器稳定截图和编译证据。

## 当场执行证据

| 检查 | 命令（相应代码目录） | 输出 |
|---|---|---|
| 前端全套单测 | `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts` | 41 tests，41 pass，0 fail/skip |
| 类型编译 | `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` | exit 0，无错误 |
| 生产构建 | `node node_modules/vite/bin/vite.js build` | 3300 modules，built in 1m 6s，exit 0 |
| Python 编译 | `python -m compileall -q app migrations` | exit 0，无错误 |
| 独立 Linux 全套后端 | `python -u infra/verify_phase7.py --browser` 内的 `pytest -q` | 108 passed，2 warnings，5.82s，无skip；PHASE7 INTEGRATION PASS |
| 原队列回归 | `python -u infra/verify_phase5.py` | 108 passed；PHASE5 INTEGRATION PASS；四个隔离卷检查通过 |

构建日志：仓库根 output/playwright/phase7-build.log；队列日志：output/playwright/phase7-queue-regression.log；Phase7完整日志：scripts/phase7/integration.log。Windows 使用本机显式 Node/Python/Docker 路径运行，命令语义如表。

## 功能与隔离

真实API/Worker：空库与重复迁移、真实 ZIP 成功安装/缺依赖失败保留旧版、Redis停机期间受理后恢复、终态不再派发、Worker/PG/MinIO/API重启保持版本和安装文件、默认切换冻结、无Skill草稿、类型错配422、CAS409、共享编辑/停用/删除审计均通过。详情见 PHASE7-INTEGRATION.md。

浏览器入口 `scripts/phase7/catalog-flow.js`：实际上传安装和默认设置、图片上传、新建模板、排序编辑、409错误保留表单、只读历史、窄视口、跳转使用模板和确认删除。409提示通过受控注入验证表单保留，实际并发由PostgreSQL竞争测试证明。最终输出 `PHASE7 BROWSER PASS: upload/install/default/template/edit conflict retained/order/history/narrow/delete; pageerrors=0`，随后 `PHASE7 INTEGRATION PASS (four isolated volumes)` 和 `PASS isolated Compose volumes cleaned`。

稳定截图位于仓库根output/playwright/phase7-skills.png、phase7-history.png、phase7-neighbor.png；等待加载遮罩与消息消失后采集。主Agent已实际查看默认配置、历史对话框与相邻图片处理页：沿用既有卡片、侧栏、表单和表格，1024宽视口无横向溢出。白色缩略图是隔离测试使用的2×2白色PNG，不是业务占位图。

所有写入测试使用随机Compose项目、独立凭据和端口、独立数据库与四卷、独立浏览器会话；finally清理并检查残留。开发库未写入测试包或测试模板。开发API8008已更新到Phase7，前端3008保持真实HTTP模式，原文件与身份保留。

## 边界

仍使用服务端显式开发身份；真实钉钉会话属Phase12。没有真实业务Skill包，隔离测试包不进入开发库。Phase8任务持久化和Phase9 CLI图像执行尚未开发，合法任务提交仍501。本阶段安装不执行包内脚本，也不联网安装依赖。

依赖警告为既有Starlette/httpx与anyio弃用提示，以及既有登录页动静态双导入构建提示。没有以这些提示掩盖测试失败。未提交或推送Git变更。
