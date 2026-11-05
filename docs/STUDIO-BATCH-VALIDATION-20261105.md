# 海外批量标注与逐图参考图验证

本轮目标0.2.64；需求依据 `STUDIO-BATCH-ANNOTATION-20261105.md`，发布步骤见 `STUDIO-BATCH-RELEASE-PLAN-20261105.md`。

## 本地验证

- 前端 `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`：527 passed，0 failed，0 skipped。日志 `output/batch-annotation-preview/production-regression.log`。
- `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：退出0；生产 `vite build` 退出0。正式包另从固定Git提交重新构建，包内来源记录为准。
- `node tests/studio-batch-annotation.browser.mjs`：26项检查通过。真实正式Vue组件、独立浏览器上下文、拦截测试API；包括仅第2/4张、三种参考用途、自定义多行、原始上传字节、确认前核对、不自动发送、上传失败原子回填/重试、跨会话隔离、刷新恢复、未知响应原请求重试、历史冻结。
- 截图已目视检查：`output/playwright/studio-batch/{batch-desktop,single-desktop,history,batch-1440,single-390,batch-390}.png`。1440/390批量截图前等待六张真实图片blob加载且尺寸非零。未将加载态截图作为完成态证据。
- 后端新引用/旧标注定向55 passed；Studio范围904 passed、40 skipped（本地缺隔离PG环境）。新增PG用例在Linux隔离环境另验，不能将跳过视为通过。
- 全后端 `python -m pytest -q`：2726 passed、430 skipped、9 failed。对原始提交0713d71独立导出源码、复用同一Python依赖运行四个失败文件，完全复现同9项失败（43 passed）。其中7项POSIX安全文件读取在Windows不可用、1项创建symlink缺权限、1项既有接口白名单未更新。原始日志分别为 `backend-regression.log`、`backend-baseline-failures.log`。本轮未改无关原有断言或降低安全读取要求。
- 生产依赖审计：critical 0、high 39、moderate 35、low 5；均为未改动的既有依赖。本轮没有新增依赖，不能宣称全部依赖零风险。
- 发布回归：本轮40项、复用36项，共76项通过。实际worker队列前提、恢复真实guard/stop/restore的中断重入和固定Git构建来源有覆盖；发布计划记录各组命令与范围。主Agent复跑本轮40项日志 `output/batch-annotation-preview/release-tools.log`。

## 交付边界

Linux补验：使用固定生产基线镜像的真实UID10001与已安装Python依赖，仅只读挂载候选app/tests；独立`--network none` PostgreSQL容器、独立匿名卷，测试容器共享该隔离网络，不注入生产配置。127 passed、0 failed、0 skipped，105.04秒；包括全部3项新增PG引用/历史冻结/旧幂等集成测试，以及Windows受限的图片协议与历史回归。临时PG容器及卷已清理。日志 `output/batch-annotation-preview/backend-linux-postgres.log`。这属于候选源码集成验证，正式发布镜像仍须再做安装测试。

本地浏览器发送只写测试内存；不调用真实付费生图。线上验收只打开现有任务和画布，不提交业务修改。生产安装测试、部署结果与审查结论执行后记录；未执行的项目不标为通过。

正式发布补充：实际镜像106项安装测试通过、0.2.64已部署；服务与公开资源校验通过。线上参考图选择与完整视觉验收受电脑操作工具中止限制，详见[部署记录](STUDIO-BATCH-DEPLOYED-20261105.md)。
