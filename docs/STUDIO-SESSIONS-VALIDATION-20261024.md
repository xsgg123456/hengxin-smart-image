# 多会话正式功能验证 · 2026-10-24

## 范围与隔离

正式前端源码接入真实Studio API，在127.0.0.1:3032验证；API在8032，使用独立临时SQLite和MemoryStore、明确标记的离线图片。身份仅在该回环测试服务内注入，无生产数据库/对象存储/模型连接。测试未调用付费模型。真实并发锁与迁移另由隔离PostgreSQL验证，SQLite页面测试不替代并发证明。

## 浏览器验证

- 创建A/B：A文字草稿在新建、切换后保留；B发送后仍可切回A发送，两会话均排队，消息彼此独立。
- B重命名成功；后台结束A后保持选择B，A显示新结果；停止B只取消B。
- A离线图片按SKU A归档到同一任务，弹窗明确任务名与来源会话；归档状态和本任务成品入口恢复。
- 完成确认后全部会话只读，仍可切换查看；原草稿保留。取消解冻保持完成态；确认解冻恢复所有会话编辑、保留图片与草稿，无新轮次自动创建。
- 连续新建至10个后按钮禁用并显示上限；删除确认明确历史/工作文件范围及归档保留，取消无变化。
- 390×844实际视口下，会话面板可收起，输入区与发送按钮可达且未裁切；document.scrollWidth=382、innerWidth=390。验证后恢复默认视口。
- 测试途中源码热更新曾重建页面；最终稳定源码重新验证归档、完成和解冻。测试身份到期后重新启动临时服务验证窄屏，未修改真实身份状态。

截图：`output/studio-sessions-release/parallel.png`、`completed.png`、`reopen-confirm.png`、`limit-ten.png`、`mobile.png`。

## 自动化与构建

- 前端：`pnpm typecheck`退出0；`pnpm test`365项通过。
- 正式构建：`VITE_VERSION=0.2.50 pnpm run build`退出0，4672模块、33.40秒；日志`output/studio-sessions-release/frontend-build.log`。
- 后端Windows关键集139通过/5跳过，最终会话专项7通过/1跳过；POSIX与真实PG结果需以Linux验证补充。
- 发布脚本29专项通过；连同既有打包/发布相关回归160通过、48 subtests通过。
- 前端依赖审计critical=0，既有high=37、moderate=37、low=3；本次未新增或升级依赖。完整结果`output/studio-sessions-release/npm-audit.json`，不将此结果表述为“无漏洞”。
- 新增受控故障浏览器脚本仅完成语法检查，未运行；上述交互证据来自CUA真实页面操作。

## 正式复审前修复与复验

- 旧版浏览器全局待确认请求按原会话恢复，旧body哈希与幂等键保持；不再误投新会话或清理另一会话草稿。前端12项新增回归，最终全量377项通过，typecheck退出0；正式0.2.50构建退出0，46.87秒。日志 `frontend-tests-final.log`、`frontend-build-final.log`。
- CSS复验：1920桌面Skill宽265px，与批准预览一致；390窄屏宽207.1875px，scrollWidth382，无横向溢出，验证后恢复视口。
- Linux首轮完整后端：2446通过、121跳过、5失败、29夹具错误。3项迁移测试失败分别为新增字段断言未同步、scope唯一约束断言未同步及新夹具参数name冲突；修复后隔离PG验证全部通过。29错误是测试源码包漏带infra配置，与应用运行无关，补齐重跑中。另2项既有process supervisor失败正在单独基线诊断，不将首轮写作全量通过。
- Linux真实PG最终会话集（`studio-sessions-test-e2542d9f2c`）：25通过、0跳过，24.14秒。包括并发抢建第10会话、跨会话实际领取执行、相同会话互斥、旧请求重放、归档/删除隔离。日志`output/studio-sessions-release/linux-sessions-final.log`。
- 隔离PG（`studio-sessions-test-06e4c5635a`）迁移4项均通过：带12个历史会话的0020→0021、重复迁移原字段不变、既有0004历史升级、既有0016可见性升级；另以生产发布脚本原函数验证真实历史数据迁移前后指纹/列定义/新增来源值，断言通过。

安装包及生产验收结果待实际部署后追加。

## Linux环境差异闭环

补齐infra的compose与公开example配置后，两份local_codex测试59项全通过（`studio-sessions-test-b72cad2921`）。独立调查确认3个supervisor文件与HEAD及远程SHA256一致：测试容器直接以pytest作为PID1，使既有`parent == 1`孤儿保护立即TERM子进程。相同资源与源码A/B仅增加Docker `--init`：无init为4失败4通过（含应exit7实际143），加init为8全通过。证据`supervisor-diag-a17f-direct.log`与`supervisor-diag-a17f-init.log`；无需修改产品代码。最终全量采用带init且完整fixture的runner重新执行。

最终隔离Linux全后端与真实PG：**2485 passed、121 skipped、0 failed、0 errors**，738.65秒（`studio-sessions-test-2f48398d0a`，日志`output/studio-sessions-release/linux-full-final.log`）。跳过项保留原测试环境条件，未据此声称未配置的国内PG集成能力通过。随后仅把会话HTTP测试helper原样抽到独立模块，将305行测试文件降至280行；测试入口保持，发布REQUIRED同步helper，Windows会话/发布回归40通过1跳过。前端迟到快照竞态另行修复及复审，不把后端全量PASS用作该前端缺陷通过证据。

## 跨会话响应排序修复

冻结新建前的旧GET响应，创建n2并输入草稿后才释放旧响应：修复前实际失败（当前选择由n2回退a），修复后通过。共享API边界在写入开始/结束时使旧读取失效，并在控制器落地前重新合并当前任务状态；并发写回执仅合并操作目标的会话行，完整列表删除以稳定读取为准。不会让B等待A的发送回执。

6项新增回归覆盖旧列表吞新会话/草稿、A回执未到时B发送、旧发送回执遇到新建、删除与完成/解冻交叉、迟到404、同轮微任务交叉。最终前端全量**383项通过**；typecheck退出0；正式生产模式`VITE_VERSION=0.2.50 pnpm run build`退出0，32.58秒。证据：`frontend-tests-final.log`、`frontend-typecheck-final.log`、`frontend-build-production.log`（此前demo构建日志不作为生产产物证据）。本地正式UI重新验证创建保留原草稿、B排队时切A发送、同时显示两个独立排队会话，截图`parallel-final.png`。实际模型并发锁仍以真实PG专项与Linux后端证据为准。

复审补充：可信稳定GET现在允许同任务版本的`archiveId:null`清除已删除成品，禁用完成入口；迟到mutation的null仍不会抹掉新归档。新增第7项回归先实际红测`archive !== null`、修复后通过。最终前端全量更新为**384通过**，typecheck退出0，正式构建退出0（4674模块、35.03秒）；以上三个final日志为本次最终结果。生产基线只读preflight再次通过。

## 安装包与生产 Skill 基线

首包`overseas-20261024-39780d3`的实际镜像安装测试2293通过、203按环境跳过、1项因未打包前端源码而排除；容量测试4通过。585份镜像后端文件摘要与包完全一致。prepare随后在旧发布helper的14包/181文件Skill固定断言处停止，未进入关流量、迁移或生产切换。

只读实查native/API/真实sandbox一致：现有Skill release=`8ea5d6ffc55e6508a1f4003a8f5bed4ffc3ca4b25de42cba29f8724a8488c339`，15包、227文件，目录device64770/inode1708242；sandbox uid999，所有Skill只读。新增本版本专用verify以该实际摘要固定基线，保留完整目录/挂载/权限核验并检查每个sandbox结果，不修改旧安装helper、不安装或删除Skill、不修改开关。发布回归50通过、3项Windows不适用跳过。应用源码与前端构建未变。


