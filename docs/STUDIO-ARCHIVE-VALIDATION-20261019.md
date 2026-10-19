# 工作台与归档信息正式发布验收

范围见 [实施合同](STUDIO-ARCHIVE-IMPLEMENTATION-20261019.md)。用户已授权开发、Git提交及生产部署。

## 本地验证

- 前端完整测试：292 passed；类型检查、正式 production 构建通过。
- 发布工具完整回归：685 passed、1 skipped、261 subtests passed。
- 后端第一轮完整Linux回归：1971 passed、83 skipped、8 failed。两个旧数据库结构断言已随 overseas_0018 更新；六个进程管理测试因容器未使用 `--init`，pytest成为PID 1，触发原有父进程退出保护。以 `--init` 修正运行方式后，数据库与两个进程管理测试文件复验 **38 passed、1 skipped**，覆盖全部失败项；未将第一轮描述为全套通过。
- 归档专项：35 passed；覆盖真实操作者快照、事务回滚、幂等、多次归档、权限、删除原任务后保留、历史未知与安全回填。
- 一次性PostgreSQL/Redis/MinIO及真实HTTP：国内0030和海外0018迁移、跨业务身份隔离、图需审核、并发幂等、归档/删除后独立读取、安装Skill资源均通过；模型调用0次。
- Chrome真实接口操作：成功轮默认折叠；手动展开后刷新保持；最终正文及3张测试图片在折叠外；Shift+Enter换行；Enter/鼠标发送均创建排队任务并可停止；归档确认与成品卡/详情显示四字段；实际测试账号与时间写入历史。
- 中文输入法组合状态、keyCode229与长按通过自动化事件测试；未宣称完成实体输入法人工测试。
- 截图：`output/studio-ux/library.png`、`detail.png`、`confirm.png`。独立预览源不进入正式构建或发布包。
- 依赖审计：production critical=0；存量high=36、moderate=34、low=1，本次未变更依赖。

## 生产发布

代码提交 `77ab69f`，发布编号 `overseas-20261019-77ab69f`。目标前端0.2.41、海外overseas_0018；国内0030保持。

发布包1198文件、5,416,799字节，隐私审计PASS，上传后SHA256一致：`43acf556510c557fd4fe571e4e080899f35cf0bef351f0176bb52653ada53b84`。

镜像第一次源码校验发现 `app/overseas/db.py` 仍为0017，发布包为0018。禁用层缓存仍复现；仅刷新该文件构建时间戳后，514项源码哈希全部一致，源码内容未改变。安装测试 **1807 passed、147 skipped、1 deselected**；跨目录合同测试已在本地验证，环境依赖跳过不计为通过。额外容量测试4 passed。

生产备份：`/opt/hengxin-backups/overseas-20261019-77ab69f`；隔离数据库恢复及逐表完整行指纹验证通过后才写COMPLETE。迁移验证文件确认只新增 `overseas_archive_events`，所有原业务表行指纹保持一致。未恢复或覆盖生产数据库，未执行收费模型调用。

北京时间11:00:52关闭海外入口，11:04:56恢复；部署脚本退出0，PHASE=complete。实际镜像 `sha256:f9caa9f7af03bcaa3d94929699fb146b5016cd652e121f25fd8fc6cbd2702699`。海外API健康，原生worker/outbox运行新代码；国内三个原生服务、国内容器、身份服务的身份与运行配置保护检查通过。备份dump143,614字节，权限0600。

公开首页及国内/海外健康、身份配置检查通过，公开首页与正式构建一致。Chrome真实生产工作台显示17条/13条历史过程默认折叠，正文和两张正式图片在外，发送提示为Enter/Shift+Enter。实际归档确认显示四字段；成品库保留1套2张原图，卡片及详情去除重复品牌、字段和审计区正常。旧工作台归档无完整操作者证据，明确显示历史记录未记录。只打开归档确认后取消，未新增生产归档或收费模型任务。

浏览器原地址曾命中旧首页缓存；使用 `?workspace=identity&release=77ab69f` 后确认新构建生效。生产截图：`output/studio-ux/production-studio.png`、`production-confirm.png`、`production-library.png`。部署记录：`output/studio-ux-production-evidence.log`；服务器发布目录保留完整安装、排空、恢复和迁移校验证据。

一次性HTTP测试容器及网络已清理，既有本地测试PostgreSQL保留。代码快照最终仍匹配两阶段审查批准编号。Git已提交，未推送远端。
