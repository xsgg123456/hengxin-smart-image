# 多会话工作台 0.2.50 生产交付

用户已授权正式实现、中文 Git 提交、打包及生产部署。交互遵循确认的多会话、完成和解冻预览。合同见 [实施范围](STUDIO-SESSIONS-IMPLEMENTATION-20261024.md)，开发及浏览器测试见 [验证记录](STUDIO-SESSIONS-VALIDATION-20261024.md)。

## 已交付

- 每个任务最多10个独立会话；可新建、重命名、删除、来回切换，并行提交生成。既有执行容量仍为5，满载排队。
- 会话隔离 CLI 上下文、工作目录、消息、上传、草稿、Skill 和素材引用；后台生成不因切换而停止。公共任务素材需显式引用。
- 所有成品归档到当前任务，保留来源会话快照。完成前检查全部会话，完成后全部只读；确认解冻恢复编辑，保留历史、草稿和归档，不自动启动生成。
- 既有历史保留。历史会话超过10个时不删旧记录，只禁止继续新建。

## 不可变发布包与验证

- 功能提交 `39780d3c259e865423d7abbf4b64499ffd346052`；发布校验提交 `71ed44028d1a5cb85be9655952e72066643b2999`。
- 发布名 `overseas-20261024-71ed440`，前端0.2.50；生产入口 https://zhitu.qhhengxin.top 。
- 包含1301文件（含清单），5,598,906 bytes；SHA256 `d63ce6a7425999a26f3414d1c8b7081bf96e28ba6b2fd89cbcf44bf225eefee2`。隐私审计、压缩包成员验证及服务器1300文件摘要验证通过。
- 干净发布树 candidate `2f4b9b597e376a2f487c0d4174a5b9653278c1b0e800385a24a8a95b68a07866`，独立两阶段PASS；与主树的唯一差异是未提交的用户 AGENTS.md 规范修改，未包含进发布。635份正式前端资产逐文件SHA256匹配，见 [发布快照复核](reviews/2026-10-24-studio-sessions-package-final.md)。
- 最终前端384项通过、类型检查通过、正式构建通过；隔离Linux完整后端2485通过/121跳过；真实PG会话专项25通过，含并发上限、跨会话同时执行和同会话互斥。生产未调用付费模型做测试。
- 最终包实际镜像安装测试 **2293通过、203跳过、1排除、6既有警告**，557.84秒；容量专项4通过，7.06秒。跳过/排除保留安装环境边界，不当作完整PG或本地CLI验证。
- 实际worker安装目录以只读挂载、无网络和无生产配置的容器验证，15通过，15.87秒。镜像585份后端文件摘要匹配。
- 实际镜像 `sha256:b1d785fd94bfc8fe5fb7628dcc42f25d2ed6605495d3fad4e6c63c1adb2bf2f1`。

## 切换与保留核验

首次部署在发布台账预检被拦截：2026-10-23的成员授权补丁已成功上线，但台账仍指向上一镜像。此时没有 DEPLOY_STARTED、PHASE 或新备份，未关闭流量。对照该补丁的 before/prepared/FINAL-VERIFIED 凭据、实际健康镜像和国内/身份快照，在全局发布锁内备份原台账，仅补记海外 current/previous 和历史 completed；保持 pending 与清理计数，不操作服务或数据库。维护脚本经 [独立两阶段复核](reviews/2026-10-24-studio-sessions-retention-reconcile.md)，服务器凭据 `/var/lib/hengxin-release/member-grant-reconciliation-20261024.json`。保留首次失败日志后，经原入口重新执行完整门禁。

- 停止海外接纳，API停止后两次稳定核对任务、删除操作、队列及unacked均为0；停止outbox后再次确认，再停止worker，没有强停执行任务。
- 备份 `/opt/hengxin-backups/overseas-20261024-71ed440`，隔离恢复及指纹验证完成，COMPLETE存在。
- 海外迁移 `overseas_0020 → overseas_0021`，原字段值、历史数据及新增归属值核对通过；国内保持 `0032`。
- API、worker、outbox切到新包；worker保持prefork和5并发。完整权限环境、成员授权、Skill所有者、现有Skill开关、认证代理及国内/身份服务通过保持核验。
- Skill三端核验为15包227文件，摘要 `8ea5d6ffc55e6508a1f4003a8f5bed4ffc3ca4b25de42cba29f8724a8488c339`；共享目录身份一致，sandbox非root且全部只读。
- 正式部署 exitCode=0、PHASE=complete；MIGRATION_VERIFIED、SESSIONS_PRESERVATION_VERIFIED、INSTALLED_VERIFIED均存在。两个发布指针均指向本次release，API healthy。
- 独立上线后核验：国内ready、海外ready、身份config均HTTP200；台账 completed 与实际全服务镜像快照一致，本次release不再pending，成功回执存在。

## 正式页面与验收边界

使用既有登录刷新正式任务，确认新版“会话 1/10”“新建会话”、当前会话标题、独立文件说明、归档到本任务入口、素材栏和输入区实际样式正常。原任务18份素材、四轮历史、已有可预览图片保留。Skill下拉实际显示主图、A+及1023-night三项，与本次保持原开关的原则一致。

本次生产页面只读验收，没有创建测试会话、发送模型请求、归档或完成真实业务任务。切换/并行/10上限/完成/解冻完整交互在本地真实前端加隔离API验证，后端并发与数据规则另由真实PG及安装测试验证。线上没有可用的已完成样例任务，因此不把本地完成/解冻验证写成生产点击验证。原任务已有图片补收提示在升级前存在，未作为本次修复范围。

生产截图 `output/studio-sessions-release/production-after.png`；上线独立凭据 `production-verification.json`；白名单导出的发布日志与凭据在 `output/studio-sessions-release/overseas-20261024-71ed440/`，发布包在 `output/release/overseas-20261024-71ed440/`。这些本地证据不含生产密钥，私有配置和数据库备份保留在服务器受限目录。

恢复边界：本次包含数据库迁移；不得直接降级数据库或重放发布、覆盖恢复整库。发生后续问题应基于保存的备份、台账、迁移凭据及当前在途任务重新评估恢复方案。
