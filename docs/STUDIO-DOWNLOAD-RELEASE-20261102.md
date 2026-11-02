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

## 生产静态部署结果

2026-11-02 已发布 0.2.56，源码提交 `7c6c795`，发布 ID `frontend-studio-20261102-7c6c795`。

- 制品 653 文件、4,895,969 字节；SHA256 `f963b6fe62a2d276a1256063d496b33ac90501d45dcbc20f2aa2a36113c65255`。提交和审查门禁、隐私审计、上传后全包哈希、解包逐文件哈希通过。
- 实际制品在服务器隔离安装目录完成安装逐文件校验和显式回退，恢复 0.2.55 成功，再安装生产。
- 源码制品目录 `/opt/hengxin-releases/frontend-studio-20261102-7c6c795/source`；生产备份 `/opt/hengxin-backups/frontend-studio-20261102-7c6c795`。旧哈希静态资源保留。
- 公网 index.html、入口 JS、OverseasCreate JS/CSS、OverseasStudio JS/CSS 共 6 项与制品 SHA256 一致。
- 国内、海外 `/health/ready` 均 HTTP 200。所有生产容器 ID 与发布前一致；海外 worker/outbox PID 保持 1167034/1167032 且 active，执行服务未重启。
- 发布证据：`output/release/frontend-studio-20261102-7c6c795/package-audit.json`、`deployment.json`、`production-verification.json`；前态 `output/studio-production-baseline.json`。

真实已登录浏览器四项功能验收由主 Agent 继续完成，此处静态和健康核验不能代替交互验收。

## 正式浏览器四项验收
2026-11-02 使用现有已登录Chrome从正式入口刷新后验证，任务“1030-拉通测试-张帅”，会话“OUTON_H-ZGD0008_Aplus_主图”。
- 任务名称placeholder为null，视觉为空白。
- 平台实际下拉顺序Amazon、Wayfair、Mercado Libre、Walmart、The Home Depot、Shopee；成功选择Wayfair。
- 品牌初始“请选择品牌”，下拉OUTON/OUTONLIFE/BELEEV，成功选择BELEEV；未提交测试任务。
- 空选下载禁用，选一张按钮计数1，全选计数8；实际下载两个ZIP分别含1/8张。Python zipfile CRC校验均通过，Pillow读取全部8张均PNG 1600×1600，单张与全选首张SHA256一致。
- 浏览器download事件捕获超时，但本机Downloads实际文件已生成，以上结论来自文件校验，不以事件超时判产品失败。页面console error/warn为空。
- 已目视核对正式表单和工作台，下载按钮位于归档旁。证据 output/studio-production.png、output/studio-production-downloads.json。未生成图片、归档、提交或改动已有任务数据。
