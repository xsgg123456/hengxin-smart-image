# 消息署名、时间与合并发布验证

本次最新授权为完成测试审查后提交并部署；完整范围见 STUDIO-MESSAGE-METADATA-20261102.md，包含此前指定五人权限、三角色和表单清理及OUTON安装。

## 本地与真实组件

- `pnpm test`：444 passed；`pnpm typecheck`通过；`pnpm build`通过（36.62秒）。日志 `output/message-metadata-{tests,typecheck,build}.log`。
- 真实最终dist浏览器（模拟API）：1366/390px、America/Los_Angeles时区、不同发送人/更换查看人/历史缺失/完成来源/运行刷新均通过；文本可见区域与遮挡检测通过。证据 `output/playwright/message-metadata/results.json`及截图。
- 既有五人权限浏览器回归：created/assigned各12次预期写请求，other为0；授权撤销刷新禁用操作。此处为模拟API，不能代替生产身份授权或真实HTTP测试。
- 后端相关9模块Windows：113 passed、6 skipped；2个PG及4个平台分支转Linux/PG隔离环境验证。
- 发布工具 `pytest -q scripts/release/test_outon*.py scripts/release/test_skill_platform_release.py`：69 passed。证据 `output/message-release/release-tools.junit.xml`。
- 独立审查确认隔离PG临时socket服务可能误判ready；安装测试与备份恢复统一以127.0.0.1 TCP检查就绪/建库/恢复，防止临时服务关闭窗口，发布工具回归69 passed。
- `pnpm audit --prod --audit-level critical`：exit 0、critical 0；现有依赖报告39 high、38 moderate、5 low。本轮未改依赖或锁文件，此结果不等于依赖无漏洞。

## 隔离Linux/PG与生产

- 全部overseas/studio共131模块，拆两批在隔离Linux/PostgreSQL运行：A60模块538 passed（361.93秒）；B71模块1031 passed、14 failed、2 skipped（485.41秒）。原始证据 `output/message-ci/run_batch_{a,b}.stdout`。
- B失败集中四个测试文件：图片预览旧断言把创建者视为无权读取；材料、恢复与解冻测试仍写入已删除运营角色，违反角色约束。修正测试前提，保留创建者只读、无关设计拒绝与native执行中撤权验证；多角色无法通过数据库单角色唯一约束，改为数据库拒绝且事务回滚的验证。业务运行代码未修改。
- 四文件本地复验97 passed（26.62秒），`output/message-release/studio-fixture-alignment.log`。Windows专属junction边界补验1 passed，`output/message-release/windows-junction.log`。
- 随后定向Linux复验包含四修正模块、消息元信息与PG、五人授权、两跳过来源模块；不将两轮结果表述为未经实跑的“最终全量一次通过”。最终镜像安装测试纳入四个相关模块，上限按实际测试工作量调整至600秒且保留失败日志和超时阻断。

- 定向Linux10模块163 passed、2 skipped（123.86秒），`output/message-ci/run_repair.stdout`。跳过原因明确为Windows junction（已本机1 passed）和缺少可选 `STUDIO_INCIDENT_FIXTURE` 私有历史事故样本；本轮消息PG、权限及四修正模块无跳过。repair制品SHA256 `ae0a54e600875c190fd3f9d8c4b99de13ee196171c8e937c9807a8987ce92191`。

待追加最终镜像安装/生产只读验收实际结果。未执行项不算通过。
