# 本地 Skill 生产站点部署记录 · 2026-09-17

## 最终重新打包发布

最新发布 `skills-20260917-1d611e9`，批准快照 `1d611e9e314d85e29487f9e07b859c6cf5d3de7bb9e7b0db1aa00f007cd1045d`。全量包 SHA256：`5f8d040385d19fd5ca3c7011f6c7548e2d0ceee351d7740f2a01403bed3cb8f2`。API/Outbox 镜像同名标签，迁移仍0012，默认 Skill 不变。

修复 tar 至7.5.19，前端110测试、类型检查与正式构建通过；独立增量审查见 RELEASE-DEPENDENCY-REVIEW.md。全依赖审计 critical=0、high=62、moderate=39、low=5（包含开发依赖，与下方首次 prod-only 审计范围不同）。未宣称消除全部依赖风险。

发布前确认无在途任务并备份数据库和旧应用，私有备份 `/opt/hengxin-backups/skills-20260917-1d611e9`，发布材料 `/opt/hengxin-releases/skills-20260917-1d611e9`。未重复删除业务记录或覆盖 Skill。540个部署文件、两个容器各117个后端文件哈希一致，Worker active、公网 ready 全部up，匿名auth/me401。Git提交归属记录到服务器 RELEASE.json；本次仍未执行付费换图。

以下保留首次发布历史。

## 实际发布

用户授权部署、安装两个完整 Skill、默认采用普通版，并永久清理已经删除的旧测试任务及模板历史，以移除旧 Skill 引用。未修改其他业务记录或服务器手工使用的全局 Skill。

- 站点：https://zhitu.qhhengxin.top/
- 发布：`skills-20260917-9146276`；批准的代码快照：`9146276c4efa3fd86d5102947dd8e93e9fd2f748a7d06aa6dced68c75c589d34`。尚未形成新的 Git 提交。
- API/Outbox 镜像：`hengxin-smart-image-backend:skills-20260917-9146276`；迁移：`0012`。
- 前端入口：`/assets/index-Bru91n64.js`；原生 Worker 服务：`hengxin-vps-codex-worker.service`。
- CLI 保持 `/opt/hengxin-runtime/codex-0.153.4/codex`，执行用户 `codex`，并发 1。开发身份保持关闭；部署环境原有 `APP_ENV=development` 未变更。

## 已安装和启用

| 标识 | 版本 | 默认 | 发布目录 |
|---|---|---|---|
| jd-main-image-wallpaper-camera-swap | 1.0.2 | 壁纸默认 | /opt/hengxin-skills/jd-main-image-wallpaper-camera-swap/1.0.2 |
| jd-main-image-wallpaper-camera-swap-it-optimized | 1.0.0 | 否，可供绑定 | /opt/hengxin-skills/jd-main-image-wallpaper-camera-swap-it-optimized/1.0.0 |

用户提供的完整目录文件保持原始字节，仅额外添加平台版本清单。目录 root 所有、执行用户不可写；版本通过真实 Celery Worker 的隔离环境检查后启用。任务内完整目录路径为 `/work/skills/{标识}/`，无需每次上传 Skill ZIP。两份 Skill 的输入要求为 4 张 JPG 底图加 1 张 JPG 屏幕素材；本次没有改写该要求。

普通版树哈希：`e211d0fb35bf3b48e014f0dce7a9993af2c3be0a0914305114f8e196cf9b7af9`。
优化版树哈希：`1f7f2ce17f0b8a6482e602a28b9bce68409dab552782d9c6d341a15212d17cb4`。

## 清理与备份

删除旧 ZIP Skill 1.0.1（`13459d3d-c276-48cc-8bba-c3317f3cdbb5`）。用户明确批准后，永久清理已软删除的“VPS真实Codex冒烟”任务及其关联历史、已软删除测试模板及版本；旧 ZIP 对象、安装缓存和该测试工作区已备份并移出活动环境。未清理其他图片对象。清理后任务 0、模板 0、新 Skill 版本 2。

私有备份：`/opt/hengxin-backups/skills-20260917-9146276`，包含迁移前数据库、清理前数据库、旧应用/配置、旧 Skill ZIP 与运行目录。备份目录仅 root 可访问。发布源与脚本：`/opt/hengxin-releases/skills-20260917-9146276`。迁移及数据删除回退必须协调数据库和应用备份，不应只切回旧镜像；未执行恢复演练。

## 验证与边界

- 生产原生文件、前端及 Skill 共 538 个文件与发布清单哈希一致；API/Outbox 各 117 个后端文件哈希一致。
- Worker active，公网 ready 检查 PostgreSQL/Redis/MinIO 均 up；匿名身份与 Skill 管理接口均 401。
- 临时维护会话完成真实 HTTP 登记、检查、启用和默认绑定，随后撤销；旧上传接口 410。
- Playwright 验证正式站点登录页正常加载。未替用户执行钉钉授权，未触发收费换图任务，未验收真实输出效果。
- 发布前代码测试及审查见 PROMPT-FORMAT-VALIDATION.md、PROMPT-FORMAT-REVIEW.md、LOCAL-SKILL-VALIDATION.md。
- 发布后补充依赖审计存在未通过项：前端依赖图 critical 1、high 40、moderate 34、low 1。critical 来自 Tailwind 构建链的 tar 7.5.1，见 [GHSA-23hp-3jrh-7fpw](https://github.com/advisories/GHSA-23hp-3jrh-7fpw)，修复版本 >=7.5.19。该 Node 构建依赖不包含在 Nginx 静态发布物中；本次未升级依赖，不能宣称依赖安全门禁全部通过。审计原始结果在本地 output/deploy/frontend-audit-20260917.json。

下一步：新建绑定普通版的模板，上传 4 张 JPG 底图和 1 张 JPG 素材，验收实际换图与返工结果；单独修复构建依赖审计项。
