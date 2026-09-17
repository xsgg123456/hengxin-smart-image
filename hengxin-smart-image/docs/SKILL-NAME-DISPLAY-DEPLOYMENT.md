# Skill 名称播报修复 · 2026-09-17

## 范围与验证

长英文标识脱敏规则曾把35字符的普通版名称及优化版名称隐藏。修复使用当前已准备工作区的 `skill_name` 精确豁免名称；普通文本及行内代码名称可显示，路径、任意其他长标识、凭证、命令和推理内容仍受原过滤规则约束。Observer在读取事件时取得名称，兼容先创建Observer、后准备Skill的调用顺序。

本机 `test_public_messages.py`、`test_observation.py` 和 `test_codex_runner.py` 合计66通过，修改模块compileall通过。覆盖两种Skill、四种名称写法、合法尾连字符名称、持久化到API展示及敏感内容过滤。审查发现末尾单词边界无法精确保留尾连字符名称，已改为标识字符集边界并回归。前端与依赖未修改。

历史已脱敏播报不猜测回填；新执行使用新规则。独立两阶段审查PASS，见 [审查报告](SKILL-NAME-DISPLAY-REVIEW.md)。

## 已上线

- 发布 `skill-name-20260917-79892f0`，批准快照 `79892f0418655e7a45b90dc1794920cac38ef0c79d962b4884cf499769c0532e`，基于工作区快照发布，未新建Git提交。
- 发布包SHA256 `4abbd310876a5965eb7d22d5f1bf547b92afdc9523a6cce21f690205232e87c3`，531文件；相对上一生产版本仅两个播报模块内容变化，未改模型、提示词、Skill或依赖。
- 备份 `/opt/hengxin-backups/skill-name-20260917-79892f0/`；日志 `/opt/hengxin-releases/skill-name-20260917-79892f0/deploy.log`，DEPLOY_COMPLETE且退出0。
- 原生Worker active，API/Outbox健康，公开ready中PG/Redis/MinIO均up，匿名身份接口401。
- 安装后的531文件哈希一致，两个容器各118个后端文件哈希一致。
- 安装产物核验两种Skill四种名称写法可见，敏感标识仍过滤；一条留存真实agent_message回放显示完整Skill名称。未回写历史播报、未触发新的付费生成。
