# Phase 8 验证记录

2026-09-09；技术验证通过，待用户验收。依据Product-Spec v0.17 REQ003/004、第9.2节、DEV-PLAN Phase8。

## 验收矩阵

| 要求 | 验证方式 | 状态 |
|---|---|---|
| 三入口冻结模板/Skill/素材/要求，输出数准确 | PostgreSQL与浏览器三模式API；模板真实编辑/删除后原快照、版本和输出数不变 | 通过 |
| 同键重放同一202、异内容409，HTTP不等待执行 | 并发HTTP同键六次，确认总任务/轮次/请求/outbox只有一条；受控8秒执行未结束前收到回执 | 通过 |
| 全局并发1时第二任务排队 | 双Worker运行同一测试环境，两不同任务保持running/queued，完成后释放 | 通过 |
| 同任务最多一个未结束轮次 | PG内部轮次受理服务由不同操作者竞争，部分唯一索引阻止绕过；返工HTTP未开放 | 通过 |
| 重复消息仅一次启动 | 并发上限2，双Worker重复消息与独立PG连接竞争；不同任务实际同时执行 | 通过 |
| 短锁，可查询和取消 | 未结束作业持续运行期间GET及时返回，DELETE保存取消意图 | 通过 |
| 排队/运行/已上传未发布取消与旧token屏障 | 真实事务与故障注入，任务不复活，无迟到图片版本；取消重启后仍生效；第二输出非法时版本/当前指针/轮次/outbox全部回滚 | 通过 |
| 状态待核实不自动重启 | 先确认前序任务终态，再对目标执行中Worker发送SIGKILL；租约过期转uncertain，重启重投不增加执行数，不允许新轮次/旧结果发布，保留并发占用 | 通过 |
| 任务状态与结果持久化 | 关闭页面后台继续，重新进入详情可读取文件与固定槽位；fixture来源明确、无虚构会话/usage；ZIP解包原图片字节一致 | 通过 |
| 四角色共享与删除审计 | 四角色API回归；容器切换第二可信用户GET/DELETE，删除审计为实际操作者 | 通过 |
| 前端幂等和操作资格 | 51项单测；真实POST202回执被401遮蔽后重连，原key/body重放；GET401后恢复原回执、查看不新POST，数据库任务总数1；用户隔离；服务端决定操作资格 | 通过 |
| 迁移与回归 | 空库/重复迁移、144项pytest无skip、前端51项/typecheck/build、Phase7回归；独立两阶段审查见PHASE8-REVIEW | 通过 |

## 工程边界

仅APP_ENV=test可启用ENABLE_FIXTURE_EXECUTOR，默认关闭；development缺执行器时新生成503，不生成假业务任务。fixture复制冻结图片为独立可读文件，前端明确标记测试来源。真实CLI/会话隔离、实际图像处理、用户返工、归档、钉钉均按后续Phase验证，不能由本阶段测试外推。

全部写入测试使用独立随机Compose项目、独立PG测试库/schema、私有MinIO及4个测试卷、独立Vite端口和浏览器profile。最终输出 `PASS isolated Compose volumes cleaned`，进程退出0，浏览器profile和临时前端目录已清理。开发端口8008/3008只做只读预览检查；不写入验收测试包和模板。

## 命令与证据

- 构建镜像后执行 `python hengxin-smart-image/infra/verify_phase8.py --browser`：最终 pytest `144 passed, 2 warnings in 10.02s`，没有跳过项；`PHASE8 BROWSER PASS`、`PHASE8 AUTH RECOVERY PASS`、`PHASE8 RECOVERY VISUAL PASS`、`PHASE8 INTEGRATION PASS`。完整流程输出保存在 `output/phase8-integration.log`。两个 warning 为既有 Starlette TestClient 弃用提示。
- `python hengxin-smart-image/infra/verify_phase7.py`：`141 passed, 2 warnings in 9.42s`；模板草稿/绑定冻结/禁用、Skill真实安装、Redis停机恢复、重启持久化、非管理员403、跨用户审计全部通过，`PHASE7 INTEGRATION PASS` 与 `PASS isolated Compose volumes cleaned`。日志 `output/phase8-phase7-regression.log`。此轮先于最后三项任务查询/快照回归加入，后者已由144项全套覆盖。
- 前端目录执行 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`：独立复验 `51 passed`、0失败、0跳过；`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 退出0；`node node_modules/vite/bin/vite.js build` 退出0，`3303 modules transformed`、`built in 35.73s`。构建日志 `output/phase8-frontend-final-build.log`；保留既有大chunk及静态/动态导入提示。
- 后端 `python -m compileall -q app migrations` 退出0；审查新增 `test_task_queries.py` 与 `test_task_snapshots_results.py` 共3项针对性回归通过，且纳入最终Linux完整套件。
- 本地预览更新：`docker compose -f hengxin-smart-image/infra/compose.yaml --env-file hengxin-smart-image/infra/.env up -d --no-build api worker outbox` 退出0。只读 GET readiness、auth/me、tasks、templates、skills（8008）及前端3008均200；配置读取 `app_env=development fixture=False role=operator`，未写测试数据或提升权限。

前端使用已有Art和Element Plus组件；不提交或推送Git变更。

视觉证据位于 `output/playwright/phase8-{wallpaper,product,text,templates-index,detail,tasks}.png` 及 `phase8-auth-long-form.png`、`phase8-auth-accepted.png`。已滚动到长名称/SKU与恢复操作区域，确认1024宽下文字、回执及按钮没有容器溢出；对照模板邻居保持既有布局。
