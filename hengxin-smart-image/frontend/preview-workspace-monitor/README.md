# 工作台会话 · 独立交互预览

2026-11-17：用户已确认本预览与超级管理员只读方案，现作为后续正式实现的视觉与交互基准，范围见根目录 Product-Spec.md、Design-Brief.md 同日条目。正式实现已接入独立管理接口，验证与部署进度以根目录 DEV-PLAN.md 为准。

本目录仍为独立预览。所有人员、会话、状态和图片均为演示，未调用业务、认证或模型接口；预览本身不改变正式路由、权限或生产数据。

沿用真实 Art 外壳、菜单、顶栏、页签、Element Plus、prototype 与 studio 样式。在管理中心新增「工作台会话」。支持成员/工作台/名称/状态筛选、只读会话详情、同成员会话切换、附件预览和演示文件下载、生成结果示意、正常/离线/空态/权限场景。演示进度由详情底部按钮推进；自动同步仅更新时间，不代表生产连接。刷新页重置演示进度。

启动：在 frontend 目录执行 `node node_modules/vite/bin/vite.js --config preview-workspace-monitor/vite.config.ts --mode demo`。

地址：http://127.0.0.1:3036/preview-workspace-monitor/index.html#/management/workspace-sessions

原有业务菜单仅保留外壳和占位说明；不提供管理员代发、删除、停止用户任务操作。图片使用项目 public/samples 中的 SVG 示意素材。
