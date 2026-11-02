# 指定五位设计人员权限验证

范围与边界：`WORKFLOW-COLLABORATORS-20261102.md`。消息实际发送人与回复时间目前仅讨论，未实现。继续不提交Git、不部署、不安装Skill；本地准备的授权尚未在生产生效。

## 当前验证

- 后端17个相关文件239通过、3条Windows POSIX文件读取跳过；新增授权22项覆盖身份、范围、撤权、管理隔离、API/native恢复读取、工作台及legacy流程。随后实际Linux/PG完整85模块回归两批全部通过，共751项、零失败零跳过：A批42模块382通过（289.09秒），B批43模块369通过（245.12秒），包含Windows跳过的3条legacy安全文件测试。
- 完整日志 `output/workflow-ci/run_batch_a.stdout`、`run_batch_b.stdout`。测试归档A SHA256 `847726706a4bd7fc2d07d5c4a751bb8fb72fee2ba8b4b69a2c653a2fffeef613`，B SHA256 `282c9ac0c5a3fed97854b315e18bb62a23f60958ea425b585a1ddbc6b5bee16c`；两批在独立无外网临时PostgreSQL容器内运行，测试/PG容器已清理，生产服务与数据未更改。
- 前端441项单测、类型检查、生产构建通过。证据 `output/playwright/workflow-collaborators/unit-tests.log`、`build.log`。
- 最终构建preview上的新增浏览器测试通过：本人创建/本人负责任务各触发12次工作流操作，纯他人任务0写；消息、附件、输出及图片可读，隐藏上传input/drop/paste、旧会话pending重试不能绕过只读。同一actor/role/session/taskVersion仅撤销scope标记触发任务重新GET，旧操作禁用。证据 `browser.log` 及同目录 `{created,assigned,other}.png`。
- 浏览器使用受控mock API；附件测试仅读取预检和发起下载事件，真实下载字节由后端HTTP测试验证，不宣称浏览器生产端到端下载已验收。
- OUTON与既有平台发布工具65项通过；16脚本内存编译通过；实测生产基线15项（14运行文件+新迁移null）与白名单匹配。证据 `output/workflow-access/release-tools.junit.xml`。
- 五人均通过只读身份核查，私人绑定和授权env位于Git忽略目录 `output/workflow-access/`，源码无硬编码个人ID，不调用原全权限授权配置。

## 审查

最终快照 `b79034980d927ef5a919ac073b3ae96c9e4fe1c99a264b2001c1f639f85ff554`，独立code-reviewer两阶段均PASS，HIGH 0、MEDIUM 0、LOW 1（测试截图退出动画时机，已补稳定截图核验）。报告见 `reviews/WORKFLOW-COLLABORATORS-20261102.md`。仅登记本地审查凭据，不提交或部署；实际五人授权尚未在生产生效。
