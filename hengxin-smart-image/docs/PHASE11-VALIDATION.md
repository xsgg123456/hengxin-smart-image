# Phase 11 验证记录

2026-09-10；实现、自动测试、浏览器闭环及独立两阶段审查均通过，待用户验收。最终审查见 PHASE11-REVIEW.md，快照 `9d487f4582f4a518ce7b6ba840097e8ff6bdb439e940d376084fcfce8b2820b3`。

## 交付范围

- 单张下载继续经过身份与文件状态校验；服务端 ZIP 按 64 KiB 分块读取 MinIO，按顺序生成 ZIP64 条目，校验长度与 SHA256，失败不提供完整 ZIP，断开时释放全部连接。前端真实模式调用此接口，模拟模式保持独立；浏览器保存文件仍使用 Blob。
- 归档事务与返工、结果发布共用任务行锁；仅当前整套成功、所有槽位完整且无未结束轮次时受理。快照固定 ImageVersion/File 外键；返工只创建新版本，归档不调用 CLI、不清理会话。
- 同任务同版本重复归档复用现有成品，跨用户竞争也只创建一份。显式请求键保存持久回执；前端未知响应保留原身份、任务、版本和请求键，重试原动作。列表按名称搜索、类型筛选、稳定分页；任务归档标记及统计使用实际记录。
- 四角色可查看/删除他人成品；删除记录实际操作者。归档删除不删除任务图片，任务删除不破坏旧归档。
- 清理默认禁用且无调度；显式 cutoff 下只回收无引用的 staging/failed 文件及符合门禁的已删除任务材料。运行中、待核实、仍可返工或有关联归档的会话保留。存储删除失败持久保存重试凭据。所有 ready 对象和历史引用保持保护，不擅自采用 30 天回收。详见 CLEANUP-POLICY.md。
- 新增迁移 0007：archives、archive_images、archive_requests、cleanup_objects；首次迁移、重复迁移与降级保护上游表均有验证。

## 已跑验证

- 隔离 Linux 全套：`python infra/verify_phase8.py --build --browser --phase10 --phase11` 中后端 `pytest -q`：349 passed、0 skipped，29.97 秒。包括真实 PostgreSQL 独立连接归档/返工/删除竞争、清理引用写入竞争和文件/任务锁竞争。该轮 Phase 8/10 浏览器已通过，但 Phase 11 脚本因沙箱没有 URL 全局对象中断；记录于 `output/phase11-regression.log`。修复脚本后使用同一业务镜像运行 `python infra/verify_phase8.py --browser --phase11`，349 项再次通过，最终退出码 0，记录于 `output/phase11-integration.log`。
- 归档专项：`python -m pytest tests/test_archives.py -p no:cacheprovider -q`：19 passed。独立审查指出原测试未真正跨成品 owner，已新增四角色均满足操作者与归档人不同的删除、审计及引用保护用例。
- 前端 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`：60 passed、0 failed；包括归档响应丢失、401恢复、版本变化及身份隔离。
- `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：退出码 0；`node node_modules/vite/bin/vite.js build`：退出码 0，35.38 秒。浏览器结束后将 Vite 自动删减的 components.d.ts 精确恢复到既有完整声明（该文件 git diff 为空），再次运行 vue-tsc 退出码 0，记录于 `output/phase11-typecheck-final.log`。
- 首轮隔离浏览器验收因 Vite 提前退出而失败，不作为通过证据；该轮容器与卷已清理。已保留后续 Vite 日志与浏览器失败快照以定位。

## 最终浏览器与隔离环境结果

`PHASE11 BROWSER PASS`、`PASS Phase11 single/ZIP exact archived fixture bytes`、`PHASE8 INTEGRATION PASS (four isolated volumes)`、`PASS isolated Compose volumes cleaned`，最终进程退出码 0。

- 实际点击归档后故意丢失已成功的服务端响应，重试复用相同 key/body/成品 ID，无重复记录。
- 归档后单张返工生成新版本，旧成品版本列表和全部文件字节不变；执行中归档返回 409。
- 成品库实际搜索、打开旧版本预览、单图与服务端 ZIP 下载；核对单图及 ZIP 两个条目均等于原归档图片字节。
- 模拟一次 503 列表失败，实际重试到空态后恢复有数据；删除成品后详情 404，但原任务与图片仍为 200。
- 1024×768 数据态检查卡片文字及按钮的裁切祖先边界；截图 `output/playwright/phase11-archives.png`。独立审查另只读打开成品库空态和模板库有数据基准，核对布局、标题、筛选、卡片与间距一致。fixture 为纯色小图，仅验证平台，不代表真实 AI 图片效果。
- Phase 8/10 浏览器回归均通过、pageerrors=0；最终 Worker 硬退出与待核实门禁回归也通过。所有一次性 Compose 容器/卷、Vite 与测试浏览器配置均已清理；本轮 pnpm 临时缓存已删除。

## 交付边界

保留期限未确认，自动清理不启用；手工清理可能持有全表锁，应按 CLEANUP-POLICY.md 在运维窗口明确调用。真实 CLI 效果、钉钉双端及生产部署仍按 Phase 12–14 执行。
