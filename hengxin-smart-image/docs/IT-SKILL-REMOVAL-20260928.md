# 生产 IT 优化版 Skill 清理

2026-09-28 用户明确要求移除 IT 优化版，系统和生产 CLI 仅保留截图前三个业务 Skill；发现引用后，用户明确选择连同模板“IT测试666”删除。

## 执行与证据

- 实查主机 racknerd-058889d，生产 API 容器 hengxin-vps-staging-api-1。执行前 queued/running 作业为 0。
- 备份：`/opt/hengxin-backups/remove-it-skill-20260928T063723Z`，数据库自定义格式备份 501610 字节、两份 Skill 目录归档 34411 字节；备份目录权限 0700。
- 通过应用现有 `delete_template` 删除模板 `12990285-2590-4ce2-8c72-28559e42d566`（IT测试666）；通过 `catalog_service.remove` 移除 Skill `465f1866-ff6a-4c68-96e9-b075f1120f08`，保留正常删除与审计记录。当前引用已解除；历史任务、版本、素材及执行快照保留。
- 将 `/opt/hengxin-skills/jd-main-image-wallpaper-camera-swap-it-optimized` 与 `/home/codex/.agents/skills/jd-main-image-wallpaper-camera-swap-it-optimized` 移至上述备份根的 published/cli-user 子目录，生产可发现目录中已不存在。
- 重新同步作业 `c85f9288-cf35-4a54-9136-9d5f3eaa631e` 终态 succeeded，无错误。调用生产管理列表处理函数确认仅三项，均 available；普通主图 Skill 仍为默认。
- CLI Worker `systemctl is-active hengxin-vps-codex-worker` 返回 active。未重启服务、未收费生成、未发布应用代码。

## 最终业务 Skill

1. jd-detail-screen-swap
2. jd-detail-screen-swap-790x1500
3. jd-main-image-wallpaper-camera-swap

发布目录 `/opt/hengxin-skills` 恰好三项。CLI 的 `/home/codex/.agents/skills` 保留普通主图，`/home/codex/auth/skills` 保留两个详情 Skill；三个 CLI 搜索目录业务条目去重后恰好为上述三项。`.system` 内置技能未删除。备份、旧发布包及历史任务冻结副本不是可选业务目录，予以保留。

此次生产数据及目录变更独立于尚未提交/部署的文字默认配置和整套修改入口前端清理。
