# 海外 Skill 文件夹管理生产交付

2026-11-03。用户明确授权开发、Git提交及生产部署。

## 已部署制品

- 功能提交：`7c4d1ce`，前端0.2.63。
- 已审功能快照：`78d1119ef880fd732715e5943492586eb703dd8fe2670cc1977979a447d2c892`，报告 `docs/reviews/skill-folders-approval-20261103.md` 两阶段PASS。
- 发布包：`skill-folders-20261103-7c4d1ce`，5,090,320字节；SHA256 `c3b6b4c2de87a737842b6f57a7bbe891dfb85b74f64a3d2e2958cdaa9645c736`；已提交干净源码及隐私检查通过，服务器解包前再次核验。
- 服务器固定源与私有工作目录：`/opt/hengxin-skill-folders-releases/skill-folders-20261103-7c4d1ce/{source,work}`。
- 生产API镜像：`sha256:bd981ca42788da650871879f4effb376062c5090ffefa1b3824387479c4246b5`，healthy。
- DB仍为 `overseas_0026`，没有迁移；native只更新两个Skill reader，worker/outbox均active。

## 发布步骤及证据

`output/skill-folders-release/production-*.log`记录 prepare、test、gate、backup、native、publisher、api、frontend、resume。正式安装环境51项全部通过；停止接纳后排空，在途任务确认空闲，数据库备份已隔离restore核对；保留旧API镜像、旧前端静态资源、native原文件与私有备份。

API技能目录继续只读。独立root publisher无公开端口，socket root:10001/0660；API以UID10001实际检查目录不可写及服务连通。现有Skill树及业务配置通过发布保护比对，17包保留；未新增/更新/删除真实Skill测试，未执行付费生图。

## 网关异常与恢复

第一次正式公网API检查为502，而本机18018 readiness为200。网关错误记录仍指向旧API地址172.24.0.3，新API的edge地址为172.24.0.5。固定网关 `hengxin-vps-staging-web-1` 的 `nginx -t` 通过后执行一次 `nginx -s reload`，仅平滑刷新DNS，无配置改动。公网随后HTTP200、status ready，PostgreSQL/Redis/MinIO均up，证据 `production-public-health.json`。

因此没有将最初脚本的静态资源成功误报为最终上线成功。后续发布工具补充网关身份检查、配置检查、一次平滑重载与有界公网readiness，覆盖发布和恢复路径；该修复不改变已部署业务代码，不需要重复切换API。

## 正式页面验收与边界

登录后的正式Skills页已实际显示17个Skill及原平台分组、新上传入口、每行保存为文件夹/删除。上传弹窗沿用页面样式且说明完整目录和限制；删除弹框显示名称、影响、取消及确认，实际点击取消后原Skill保留。

正式页面点击“保存为文件夹”已触发原生目录选择，但Windows自动化工具因无法可靠确认浏览器URL中止控制；未绕过工具限制，未声明Windows原生选择与磁盘保存已经验收。已向用户给出手动选择/取消指引。隔离浏览器的真实目录句柄保存、111项全量读回校验、同名拒绝覆盖及重试冲突保护均已通过，详见 `SKILL-FOLDERS-VALIDATION-20261103.md`。

本次下载只有保存为文件夹，无ZIP；新上传默认关闭且不分配平台，用户自行开启和分配。现有配置保留，未替用户切换开关。
