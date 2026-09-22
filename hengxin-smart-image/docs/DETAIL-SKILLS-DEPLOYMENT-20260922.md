# 详情屏幕 Skill 生产安装 · 2026-09-22

用户授权将提供的两个完整目录安装到本项目生产 Codex CLI，并同步到 Skill 管理列表。沿用 2026-09-21 轻量目录管理规则，不添加人工版本号。

## 计划与验收

1. 核对源文件、名称与依赖，保存逐文件 SHA256；原始 10 个文件保持字节一致，仅额外添加平台处理类型及依赖清单。
2. 生产根目录 `/opt/hengxin-skills` 新增 `jd-detail-screen-swap` 与 `jd-detail-screen-swap-790x1500`，管理员所有、执行用户只读；若同名目录已存在则停止覆盖并检查。
3. 补齐实际隔离 Python 所需 NumPy，Pillow 已安装；通过真实 Bubblewrap 挂载/依赖检查，核对安装文件哈希。
4. 调用现有同步业务入口，由生产 Worker 完成目录扫描与快照保存。验收两条新记录均为 wallpaper / available、描述来自原 SKILL.md、原默认绑定与两条既有 Skill 保持正常。

普通详情 Skill 保持输入原尺寸；另一项要求 790×1500。仅安装、依赖和同步验收，不包含付费生图效果验收，不修改应用代码、CLI 模型或并发。

## 回退

若新增项校验失败，保留异常证据并修复安装；需要回退时仅撤销新增目录和登记，不触碰既有 Skill、任务快照与默认绑定。新增系统依赖不自动卸载，避免影响其他使用者。

## 状态

部署前已直连 `racknerd-058889d`：CLI 0.153.4、Worker active；原两条 Skill 存在。

## 已完成

- 两个目录已按平铺结构安装，10 个原始文件 SHA256 全部一致，另加两份 `hengxin-skill.json`（wallpaper 类型及 Python 依赖）。目录 root 所有、codex 不可写。
- 系统 Pillow 10.2.0 已存在。Ubuntu NumPy 包在隔离内因 BLAS 链接不可见而无法导入，最终使用带内置 BLAS 的 NumPy 1.26.4 wheel，安装在 `/usr/local/lib/python3.12/dist-packages`；未扩展隔离挂载。系统 apt NumPy 包保留，不影响 wheel 优先加载。
- 真实 codex 用户、现有 Bubblewrap 隔离内，两份 Skill 的只读完整树与依赖检查通过，三个脚本启动通过；790×1500 随附 14 项合成回归通过（62.172 秒）。首次 60 秒测试上限不足，改用 300 秒验证上限后完成；未改 Skill 原件或生产任务超时设置。
- 通过现有 `catalog_service.queue_sync` 同步业务入口登记作业，由原生 Worker 执行扫描、检查和快照发布；沿用现有活跃超级管理员维护身份，未创建登录会话或绕过网页认证。
- 同步作业 `25430ba5-150c-468f-b291-4dab0f8c9cf7` 成功，无错误。新项 `jd-detail-screen-swap`（`dfd7b194-167e-4aef-aed1-f589e74359bd`）与 `jd-detail-screen-swap-790x1500`（`dd2f9f8f-2816-4444-9e77-0e7b65478037`）均 wallpaper / available，描述读取自原 SKILL.md。
- 当前目录共四条可用 Skill，既有两项的名称、类型、描述、状态及默认标记核对不变；模块默认绑定未变。
- 服务器证据：`/opt/hengxin-releases/detail-skills-20260922/source-manifest.json`、`sync-result.json`，同目录保留本次安装与验证脚本。本地材料：`output/detail-skills-20260922/`。
- 未触发真实付费生成；安装可用与脚本回归不代表实际图片效果已验收。
