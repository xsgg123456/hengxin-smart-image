# 正式工作台本地验收 · 2026-10-13

## 已完成的验证
- Linux隔离容器（--init）全量 pytest：1923 passed、162 skipped、15 warnings，230.07s。日志 output/studio-linux-final.log。跳过为现有环境条件用例，不算已验证。
- 后续引用历史/流式上传补测：test_overseas_studio.py 6 passed；独立审查也重跑通过。
- 前端 pnpm test：311 passed、0 failed；output/studio-frontend-final.log。
- pnpm build（含vue-tsc）：退出0，Vite built in43.00s；output/studio-build-final.log。
- 真实隔离PostgreSQL迁移到overseas_0012；身份、原始PDF/DOCX/XLSX/CSV、退回重提、并发幂等预审、国内隔离HTTP全通过。
- 新studio_checks真实PG/MinIO：并发同key一轮、不同key拒绝、原件和TXT字节、跨任务拒绝、排队取消、持久事件游标通过。

## CUA页面实测（1280×720）
- 无海外首页菜单，超级管理员仅一个角色；成员编辑为单选。
- 完整Skill ZIP上传并发布成功；历史版本显示SKILL.md、references/context.txt及assets/sample.bin。
- 原始图需三文件可全选引用；移除本轮引用不会删原件。
- 三张离线测试图全选3/3；指定SKU归档后均标记已归档，任务仍可继续对话。
- 统一上传区上传TXT成功；选择Skill并引用指定图发送，出现真实排队状态。
- 整页刷新后，消息/Skill/文件/引用图片及排队状态仍在；停止后显示已停止。
- 独立确认完成后任务只读；成品库显示1套归档、指定SKU和3张图（archive-library.png）。
- 原图查看器成功打开。默认布局发送按钮bottom659.5小于720；展开视图正常。
- 截图：output/studio/workbench-final.png、expanded-final.png、original-view.png、single-role.png、skill-package.png。

## 验证边界
未调用收费Codex模型，执行层使用受控假进程验证真实prepare/resume/产物采集。界面三图由PIL生成并标明OFFLINE UI FIXTURE，不作为AI生图成功证据。外部桌面文件真实拖入/粘贴未做CUA原生拖拽测试，相关处理由代码与专项测试覆盖。未部署、未迁移生产数据、未导入用户真实Skill包到生产。

Windows全量初跑的旧POSIX安全读图与无init容器的孤儿回收失败均未通过放宽安全逻辑解决；改用与运行方式相符的Linux --init容器完成全回归。
