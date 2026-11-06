# 同会话 Skill 复用生产部署记录

2026-11-06 12:17（北京时间，回执UTC 04:17:07）验收通过。用户已授权开发、中文Git提交及生产部署。

## 已上线行为
- 海外Studio同一会话同名同内容技能复用；A→A、A→B→A不重复保存A。名称或完整内容变化准备新版本，旧版保留；相同内容重新发布仍复用。
- 当前技能继续只读挂载，未选技能时旧技能不可见。不同会话隔离，两种技能来源均覆盖。
- 原始会话、转录、附件、生成图、工作文件和旧轮次副本没有删除、迁移或摘要。已有会话下一轮开始使用新库；本次阻止后续重复增长，不回收之前的重复占用。

## 固定交付
- 功能提交：`731c84eb752963bd6da9d2f7040f23f698124f2c`。
- 发布测试修复：`db56bf1119f58e7fa52c025dc4148fc0c00686c9`、`3a6e84ca2e89f3172dba4933446935a175bde494`。
- 正式包：`skill-reuse-20261106-3a6e84c`，40352字节、29文件；隐私扫描PASS。
- 包SHA256：`cf2c049bdc389195c2def7fc55e33845d011f0b5d0dfb0e34f72d5d37e336cb5`。
- manifest SHA256：`375245b03cbdcac186ce39121ce5f2e1edbee36d8677fe9eb96d7715a2241868`。
- 最终批准候选：`c0d2c7ab07263b3d2a55f85c917d5dee66d3b417c143bac8a5c9ddb8b3da63f4`；完整业务审查见FINAL-REVIEW，后续两处工具修复见VENDOR-REVIEW、OWNER-REVIEW，均Stage1/2 PASS。
- 只替换原生服务的`materials.py`、`skill_cache.py`、`skill_content.py`，实际根`/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend`。未改UI、API镜像、模型、配置、实际Skill内容或数据库结构，schema仍`overseas_0026`。

## 生产验收
1. 最新部署记录确认入口后只读取基线，正式包传输SHA一致。隔离安装使用生产原生解释器、env-i、网络隔离、真实服务UID999；74项通过（5.93秒），root真实Bubblewrap两项通过（0.86秒），零跳过。
2. 等真实在途任务自然结束，双代理海外入口503且旧nginx worker排空；pause消费并温和停止两原生服务，没有强杀业务任务。
3. 保存全部执行根元数据及8张Studio表摘要，再备份/原子替换三个模块。最终安装路径真实服务UID74项通过（5.39秒）、root沙箱两项通过（0.75秒），零跳过。
4. 候选与正式安装路径都用真实已安装`walmart-new-product-image-set-original`验证：18文件、13,358,055字节、连续两轮一份；内容校验、路径、inode/mtime及历史sentinel不变。无模型调用。
5. 切换前后63,532个文件/目录条目元数据、全部表内容摘要一致。记录计数：会话42、轮次216、转录6954、上传729、图片660、输出文件73、材料可见性17、删除记录11。计数不是单独证据，同时比对完整表摘要；文件比对类型/大小/mtime/inode/uid/gid/mode，没有读取或拷贝全部私密内容。
6. 两原生服务active：worker PID967651，outbox PID967649。API容器ID、镜像和StartedAt保持原样，API从未停止或重启。
7. verify/resume成功，双代理恢复原字节，国内与海外正式ready均HTTP200，发布owner已释放。开放入口后不再将正常用户写入与旧静态快照比较。

API保持的镜像为`sha256:30681c68650019ee8b4f5e6c3c30fe810a47f4a7de540273f03cae02eb90c943`，StartedAt为`2026-11-05T06:46:34.677895031Z`。

## 证据与恢复
服务器正式发布目录`/opt/hengxin-skill-reuse-3a6e84c/`，`work/`保留精确源码备份、会话基线及阶段回执。脱敏测试、catalog、最终deployment-receipt和阶段结果副本归档在本地`output/release/skill-reuse-20261106-3a6e84c/`（Git忽略）；不提交生产会话或配置原文。

必要时按RELEASE-PLAN执行同包`skill-reuse-deploy.py recover --work /opt/hengxin-skill-reuse-3a6e84c/work`：先关门排空/停止保护，再恢复原源码并验证，保留所有新增会话数据；不能回灌旧数据库或手工删除owner。原生源码备份和新增模块归档能力已保留。

## 验证边界
前端类型/527项测试/构建通过；Windows全后端原始结果有9项基线失败，已在未修改HEAD完全复现，另1项新契约测试已修正并复验；完整记录见VALIDATION。不以专项通过声称全仓库零失败。没有重放真实用户任务或逐个调用收费模型续聊；已验证本次技能准备、历史文件保留、隔离挂载及正式服务健康，不承诺系统未来绝无任何bug。
