# CLI 成品优先验收整改验证

## 实施范围

本地整改，未提交 Git、未部署生产、未调用收费生成，也未改写历史生产任务。需求依据为 Product-Spec / DEV-PLAN 的2026-09-27章节；不改模型、Skill、提示词、超时或并发。

- 正常执行、自动续接、恢复及显式历史补收共用最终交付验收。过程 error、异常计量、重复完成和非零退出不再单独否决本轮有效最终成品；真实会话、最终性、完整数量/顺序、解码和文件安全门禁保留。
- 用 Markdown 结构解析图片和下载引用，支持引用式链接与列表内图片，继续排除代码块。新增固定依赖 markdown-it-py 4.0.0 和锁文件。
- 验收完成后将成品字节及身份/摘要原子冻结至平台控制目录，恢复不再依赖可变原文件。稳定文件ID允许对象PUT/数据库提交回执丢失后安全重试；发布仍受现有事务与执行权门禁保护。
- 保存失败保留 uncertain 执行权并自动补收，API列表/筛选/统计按执行中展示，详情显示“图片已生成，正在保存”，不出现生成失败红框；保存发布完成才显示成功。普通不确定任务、取消和失败不被该显示规则覆盖。

## 验证结果

运行目录 backend：

```text
.venv/Scripts/python.exe -m pytest -q -rs
1183 passed, 171 skipped, 15 warnings in 76.88s
.venv/Scripts/python.exe -m compileall -q app
exit 0
```

完整输出及跳过原因：`output/cli-delivery-full-tests.txt`。跳过包括需要隔离 PostgreSQL 的竞争测试、Linux/真实执行环境及Windows符号链接权限；不将这些记录为通过。警告为既有 Starlette/httpx/BlockingPortal、cookie测试弃用及NULL身份SQLAlchemy提示。

运行目录 frontend：

```text
node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts
176 passed, 0 failed
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
exit 0
node node_modules/vite/bin/vite.js build --outDir dist-delivery-check
4469 modules transformed, built in 45.47s, exit 0
```

前端产品代码无需修改，既有组件已尊重服务端label；新增状态回归测试。构建有既有登录组件混合静态/动态导入提示。本轮没有重新进行浏览器视觉验收，不把纯函数/API测试说成真实浏览器验证。

## 有意义的故障证据

`test_delivery_acceptance_flow.py` 将重连变体、异常usage、重复完成、非零退出、引用式图片和列表缩进图片分别注入正常/续接/恢复，共18组；每组最终2个版本，可通过真实测试HTTP文件接口读取，重复调度不重新调用CLI、不重复版本。

`test_delivery_recovery_flow.py` 在三路径中注入第二张图片PUT成功但回执丢失：先保留待保存状态；删除原始事件、基线、退出回执和一张原成品后，仍从已验收快照补收成功。文件记录只增加2条，第二张重试沿用同一ID，不重新生成。覆盖发布事务提交前与提交后丢回执、待保存取消不发布。

`test_delivery_snapshot.py` / `test_delivery_storage.py` 覆盖哈希/身份/路径污染、残留未提交快照、跨调用、同内容不同槽位、对象写和两阶段数据库提交前后故障、owner/deleted冲突及执行权丢失。

上述集成测试运行真实受理、材料、收图、SQLite事务、版本发布和HTTP逻辑；CLI边界与对象存储为隔离夹具，不是生产Codex或MinIO实测。不宣称SQLite测试证明了PostgreSQL多Worker竞争安全。

## 审查与上线边界

独立两阶段审查均PASS，报告为 CLI-DELIVERY-FIX-REVIEW-20260927.md，最终候选为`30fec908031bb4340fccfd915ce402f552a5d5a2056d7af1b0256247004d7810`；reviewer独立复跑91通过/1符号链接权限跳过，语法检查通过。生产上线还需安装新增依赖、受控更新Worker及API、排空旧任务并核验部署版本；本轮尚未执行这些操作。历史误判成品需在部署后显式补收，不能据本地测试宣称用户已有任务恢复。
