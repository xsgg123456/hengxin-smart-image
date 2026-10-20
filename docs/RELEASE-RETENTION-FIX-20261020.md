# 部署回收遗漏修复 · 2026-10-20

## 范围与依据

生产只读排查确认两处遗漏：镜像发现只按仓库标签过滤，漏掉本项目无标签镜像；失败构建记录长期停在 pending，保护旧候选并使专用 builder 缓存一直跳过回收。用户已授权修复、测试、Git 提交及服务器工具更新，要求保留三业务当前/上一版、约 2 GB 缓存及全部生产/Codex 会话数据。

## 实现

- `release-retention-docker.py` 合并仓库标签和本项目 label/dangling 查询；无标签镜像必须无摘要别名、项目标记匹配且没有保护引用。删除前重新检查，按完整 ID 非强制删除。已有标签镜像的外部别名保护保持。
- `release-retention-state.py` 保存可选成功计数和失败基线；只在验证成功且业务实际切换镜像时递增。旧台账可读，不改业务版本集合。
- `release-retention-failures.py` 处理构建/准备失败；同业务后续成功、无保留引用、无恢复快照/成功回执才自动退休，并将原记录及替代证据与解除保护原子写入台账。未知业务和进入部署/恢复的失败保留。旧失败先登记基线，再等待新成功，不按旧日期猜测。
- `release-retention.py` 在成功后的清理、手动 cleanup 接入退休；preview 只读。真正未完成候选仍阻止缓存回收。新 helper 已由所有现有 packager 的 allowlist/glob 包含。

## 本地验证

- `hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release -q`：最终 863 passed、1 skipped、309 subtests passed。
- 显式补跑默认收集器不匹配的历史 `*-tests.py`：113 passed、3 skipped、26 subtests passed。
- Python compileall、git diff --check 通过。修改未涉及前端、业务 API 或迁移，因此不重跑无关 UI 测试。
- 发布接线测试原先把只操作原生服务的 `codex-auth-deploy.py` 误当成 Docker 镜像发布入口（HEAD 同样如此）。已明确其测试范围例外，保留全部 `test_codex_auth_deploy.py` 锁/排空/失败恢复测试；没有修改该生产入口。
- Docker Desktop 29.4.3 本机隔离 smoke：临时 import 无标签项目镜像与其它项目镜像，真实 helper 发现前者、排除后者；停止容器引用时非强删被 Docker 拒绝，移除测试引用后成功删除。测试镜像/容器全部收尾。没有对生产造数据或调用模型。
- smoke 初次尝试用本机 Buildx 同标签重建造样本，旧镜像元数据被本机引擎自动移除，无法形成目标前提；最终用无标签 import 建立真实前提。Windows 子进程解码显式使用 UTF-8 后通过，不把失败尝试计为通过。
- 首轮独立审查发现裸业务名可被错误识别为允许范围；已收紧为完整业务前缀且后缀非空，新增 7 个裸名/空后缀/未知名反例，验证不登记基线、不预览退休、不改台账。最终快照重新独立两阶段审查，首轮失败报告保留。

## 服务器更新计划

在共用发布锁下，备份当前工具入口及台账摘要，安装带 Git 版本的新独立工具快照并逐文件核对 SHA256、编译与只读 preview，再原子切换 `/opt/hengxin-release-tools/current`。保留原工具版本；不覆盖历史发布包、不重放应用发布、不改数据库/会话文件、不重启服务。后续新发布包自动携带修复，历史包仍不得作为新发布入口。

验收检查三业务版本/回滚镜像、容器 ID/启动时间/挂载、原生服务 PID、会话/认证及任务目录元数据、公网/本机健康接口；更新记录在执行完成后补入本节。

## 服务器实际验收

2026-10-20 09:36（北京时间）完成工具更新，源码提交 `e6b2884be567085697d4048d9b9c82a2d94190d4`，最终独立审查两阶段 PASS，见 `docs/reviews/RELEASE-RETENTION-FIX-20261020-FINAL.md`。

- `/opt/hengxin-release-tools/current` 原子切换至 `versions/retention-e6b2884be567085697d4048d9b9c82a2d94190d4`。51 个文件记录哈希，5 个相关 helper 与 Git 提交内容逐一 SHA256 一致，语法编译通过。
- 原工具 `versions/27aa7dbce2f209544dee113125a6a42b0fdbae4804c0a200befe6374aae23bad` 保留可回退；未覆盖历史发布包。
- 安装持有共用发布锁。20 个项目容器 ID/镜像/启动时间/重启次数/挂载及 6 个原生服务 PID/启动时间一致，Compose/systemd/运行环境配置哈希一致。
- 25,561 个会话、认证、任务、CLI 环境等受保护文件的 inode/大小/mtime/链接目标一致；排除每次版本探针自然生成和过期的 `.codex/tmp/arg0` 临时启动文件，未排除真实会话目录。
- 保留台账字节未变；切换后从正式 current 入口执行只读 preview，待删镜像 0、待退休失败 0，国内/海外/身份各自 current、previous 均在保护集合，实际镜像存在。安装和切换后本机 3 个接口、公网 4 个页面/接口全部 HTTP 200。
- 本次只更新工具，没有执行 cleanup、应用部署、服务重启、镜像构建或业务数据/会话删除。约 2 GB 专用 builder 缓存策略保持，后续成功发布自动执行新回收逻辑；仍有真实在途或恢复记录时继续保护缓存。

服务器证据目录 `/root/hengxin-retention-fix-e6b2884/` 含安装摘要、切换后验证、只读预览、台账备份与前后基线；本地非版本证据 `output/retention-fix-20261020/`。Git 提交已完成，未向远端推送。
