# 最终回复收图验证 · 2026-09-17

## 范围

保持两个业务 Skill 原样；提示词只包含 Skill 名称、实际图片和修改意见。每任务私有 Skill 发现目录只读挂载完整版本，后端从本次最终 assistant 回复中的本地图片引用收取完整结果，不再要求 Skill 写平台 manifest 或成品哈希等于原生候选。新执行控制证据记录 final-reply-v1，旧执行恢复保留旧来源协议。

## 已执行验证

- Windows 后端 `python -m pytest -q`：711 passed，146 skipped；跳过为 PostgreSQL/真实 CLI/特定 Linux 等显式环境条件，不视为已验收。
- 首轮执行专项：102 passed，2 skipped；复审修复后的收图/runner/返工/恢复专项：87 passed，1 skipped。包含真实 HTTP 接纳、素材准备、修复图收取、存储/下载、单张及整套返工、恢复、取消和重投。
- WSL Ubuntu `RUN_LOCAL_SKILL_LINUX=1 python -m pytest tests/test_local_skills_linux.py tests/test_final_delivery.py tests/test_execution_workspace.py -q`：76 passed；真实 bwrap 验证完整 Skill 两处只读可见、邻居目录隔离和链接拒绝。
- 用先前 VPS 成功实验的原始 events.jsonl 与四张最终 PNG 回放本机隔离 HTTP/runner/测试存储/下载流程：1 passed，四张下载字节均与真实成品一致。回放未再次调用生成模型，未写生产数据库。
- `python -m compileall -q app tests` 通过。
- 前端 `npm run test`：110 passed；`npm run build`（含 vue-tsc）通过。前端代码未改。

## 边界

已按用户授权部署 `final-reply-20260917-59d22f5`，生产核验见 [发布记录](FINAL-REPLY-DELIVERY-DEPLOYMENT.md)。网页生产新任务真实生成仍待验收，不能以真实成品回放替代在线生成。来源改为“本轮最终答复明确交付、本轮目录及文件有效性”，不再声称成品字节有原生生成回执证明，也不把像素尺寸安全检查当作视觉效果验收。缺少完整图片引用直接失败；不自动重跑，不从候选目录猜测成品。

## 独立审查

前两轮报告 FINAL-REPLY-DELIVERY-REVIEW.md 和 FINAL-REPLY-DELIVERY-FINAL-REVIEW.md 发现编号变体（包括带说明标题、纯数字标签及编号列表）和预览/下载重复计数问题，已修复并新增回归。最终候选 `59d22f5a86e4d5cde79d48205c0c2765552296f38fdb2a231c7588b30b3304bb` 两阶段独立复审均 PASS，见 FINAL-REPLY-DELIVERY-CLOSEOUT-REVIEW.md。独立复测专项109通过/1跳过，归档回放与故障5通过，乱序编号HTTP到下载端到端变体1通过；编译通过，批准登记对应同一快照。
