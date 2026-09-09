# Phase 8 隔离集成验证

执行入口（仓库根目录）：`python hengxin-smart-image/infra/verify_phase8.py --build --browser`；已有最新镜像可省略`--build`。测试代码分为独立Compose生命周期、`scripts/phase8/api_checks.py`业务断言、`scripts/phase8/task-flow.js`三入口、`auth-recovery.js`认证恢复、`recovery-screenshots.js`长表单视觉检查。

每次创建随机Compose项目、随机端口与凭据，独立PG/Redis/MinIO/Skill四卷，pytest使用随机`phase8_<随机值>_test`数据库与随机schema；两个独立Celery Worker使用真实PostgreSQL认领。浏览器使用独立命名会话，Vite代理指向本次随机API端口。finally关闭浏览器并删除会话资料，停止Vite并清理本次Compose四卷。不会连接日常8008/3008服务。

2026-09-09最终执行证据：`output/phase8-integration.log`，完整后端`144 passed, 2 warnings in 10.02s`，无skip；两个警告为既有Starlette弃用提示。

通过的真实路径：

- 新库迁移与重复迁移，三种Skill包由真实Worker安装；三入口冻结引用，MinIO读取PNG、校验CRC/像素解压与原始字节一致，结果使用独立文件ID、executionSource=fixture、sessionId=null。
- 六个并发HTTP相同幂等键返回同一202；整个task_records表仅一条，同键异内容409。限额1时第二任务排队并随后执行。
- 限额2时两个独立Worker执行两个不同任务，重复消息只能启动一次并发布一个版本集合；终态再投不重跑。后端PG多进程用例同时覆盖认领/同任务新轮次争用及旧token/上传后取消等屏障。
- Redis停机期间真实POST仍受理，恢复后任务完成；排队/运行删除产生真实操作者审计，无迟到版本，重启不复活；第二可信身份可读取并删除他人任务。
- 浏览器三入口真实提交并传幂等键，离开页面后后台继续；详情显示测试来源和服务端操作资格，实际下载ZIP中的PNG与输入字节相同；删除后GET404，页面异常0。
- 将真实POST202回执替换为401，登录界面卸载表单后同身份重新连接，60字名称/80字SKU/意见和原键/快照保留；确认原请求再遇详情401，站内返回创建入口仍保留原回执，查看原任务不新增POST，数据库搜索只有一项。
- 明确等所有前序轮次终态后启动故障场景；真实SIGKILL Worker并将该租约推进过期，outbox判uncertain。重启后六次重投不增加execution_count、不发布图片，操作资格禁止重试且限额1仍被占用。

关键输出：`PHASE8 BROWSER PASS`、`PHASE8 AUTH RECOVERY PASS`、`PHASE8 RECOVERY VISUAL PASS`、`PHASE8 INTEGRATION PASS (four isolated volumes)`、`PASS isolated Compose volumes cleaned`。最终进程退出码0，独立四卷清理成功。

截图位于`output/playwright/`：`phase8-wallpaper.png`、`phase8-product.png`、`phase8-text.png`、`phase8-templates-index.png`、`phase8-detail.png`、`phase8-tasks.png`、`phase8-auth-recovery.png`、`phase8-auth-long-form.png`、`phase8-auth-accepted.png`。长表单和受理按钮截图明确滚动到目标，避免应用内滚动导致只截页首。下载产物`phase8-results.zip`仅包含测试图片。

已修正的验证前提：pytest容器单独关闭fixture开关，避免污染既有production guard用例；Playwright沙箱使用page等待而非全局setTimeout；抽屉先正常关闭并精准选择`.hx-detail.el-drawer`；认证任务必须完成后才能进入独立Worker故障场景。每次失败也执行四卷清理。

真实CLI、返工HTTP及归档不在Phase8验证范围；fixture不代表真实Skill效果或CLI会话隔离已通过。
