# 海外工作台下载与表单调整 · 0.2.56 发布准备

用户已明确授权中文 Git 提交、上线并验证四项功能。此记录在发布前建立；实际上线结果由后续生产证据补齐，不能将准备完成视为线上验收。

## 范围与基线

仅更新前端静态资源：勾选原图 ZIP 下载、任务名称去示例、Wayfair 排在 Amazon 后、品牌三项下拉。后端、数据库和执行服务不变，无需重启或排空任务。Spec 与 CHANGELOG 已同步后续发布授权。

2026-11-02 已通过严格主机校验的 SSH 只读实查生产：前端版本 0.2.55，发布标识 image-cache-20261030-0aa5912。正式入口 https://zhitu.qhhengxin.top/ 。本轮版本 0.2.56。

## 发布前验证

- 既有本轮单测 428 项及隔离浏览器验证见 STUDIO-DOWNLOAD-VALIDATION-20261102.md。
- 版本更新后正式类型与构建退出 0，Vite 31.20 秒；output/studio-release-build.log。
- 原有允许清单和隐私扫描覆盖 650 个静态文件、10,183,888 字节，通过；output/studio-release-privacy.json。打包时再次扫描并绑定审查快照和提交。
- pnpm audit：critical 0、high 73、moderate 55、low 11。依赖和锁文件未改，本轮不声称解决历史漏洞；output/studio-release-audit.json。
- 静态发布保护 5 项通过：后端/旧资源保留、损坏包拒绝、资源冲突拒绝、失败自动恢复、显式回退。
- 用户既有 AGENTS.md 与 release-builder/SKILL.md 修改保持在工作区，排除本次提交和制品。

## 发布与回退

复用 frontend-polish.py 的既有流程为 scripts/release/frontend-studio.py。独立 review 与主 Agent 提交后运行 package；发布标识 frontend-studio-20261102-<commit7>，制品 output/release/<release>/release.tar.gz。

上传至 /opt/hengxin-releases/<release>，先在隔离安装目录用实际制品验证，再部署 /opt/hengxin-smart-image。备份 /opt/hengxin-backups/<release>，先备份入口、压缩入口、package.json、FRONTEND_RELEASE.json；保留所有旧哈希资源，只原子替换入口和版本元数据；失败自动恢复。版本基线不一致或同名资源内容冲突即拒绝。

显式回退命令：`python3 <source>/scripts/release/frontend-studio.py rollback <source> /opt/hengxin-smart-image /opt/hengxin-backups/<release>`。回退先确认当前发布清单一致，恢复旧入口及元数据，保留两代哈希资源；不恢复数据库、不重启后端。

上线后核对生产版本、入口/核心静态文件公网哈希和健康接口；主 Agent 在真实已登录 Chrome 中实际验证四项功能及页面截图。
