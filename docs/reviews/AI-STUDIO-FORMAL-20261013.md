# AI 工作台正式实现与单角色权限审查

## 快照与范围

- 首次 candidateId：`4a38a7789cb1a44231260c49b1af0d1d59777559a219d549d51dd83ca7aecd94`。
- 最终 candidateId：`3a46197dec16d3b836ace63f5772d69eceadb90e6e5ae41851339351f4180bd2`；review-status 已独立核对 currentId 一致。
- 范围：全部未提交正式后端、前端、迁移及新增测试；既有独立 preview 参照本目录先前审查，不以 preview 代替正式验收。
- 来源：AGENTS.md、code-review/SKILL.md、Product-Spec.md:1009、DEV-PLAN.md 末尾、docs/AI-STUDIO-IMPLEMENTATION-20261013.md 原文。
- 审查中发生代码变化：排队 reply=null DTO 修正、读取错误恢复、工作台视口布局、历史引用图片 DTO/渲染/测试。已逐处复核新版本；首次候选不得据本报告直接批准。
- 最终结论：Stage 1 **PASS**；Stage 2 **PASS**。仅适用于上述最终 candidate；由主 Agent 登记 review-approve，reviewer 未写 clean、未修改实现、未提交。

## Stage 1：逐项需求核对

以下路径均相对 `hengxin-smart-image/`。

| 条目 | 代码证据与验证 | 结论 |
| --- | --- | --- |
| 新任务预审通过进入工作台，不自动旧分析 | backend/app/overseas/tasks/service.py:56；tasks/requirements.py:62；plans/service.py:47；test_overseas_studio.py:29 | 实现 |
| 历史任务保留原流程 | backend/migrations/overseas/versions/0012_studio.py:17 默认 legacy；frontend/src/views/overseas/OverseasTasksPage.vue:35 保留 legacy 组件 | 实现 |
| 持续会话与逐轮独立目录 | backend/app/overseas/studio/execution.py:20，conversation ID 决定 HOME、turn ID 决定 work；:41 使用 resume；缺失原 session 文件拒绝替换 | 实现；真实收费 CLI 未执行 |
| 文字与任意数量图交付 | studio/execution.py:95 按最终回复链接数量收取，无 plan.json/schema 固定图数；test_overseas_studio_execution.py:84 验证三图，:62 验证文字后续聊 | 实现 |
| Skill 完整包与冻结 | management/packages.py:20 校验 ZIP；:63 保存二进制；management/settings.py:89 冻结版本；execution/materials.py:47 大小及 SHA 校验；test_overseas_skill_packages.py:28 | 实现 |
| 真实前序原件引用与新附件 | studio/service.py:51 校验同任务并冻结存储引用；studio/execution.py:49 按校验值读取原件；studio/files.py:22 格式/20 MiB 检查 | 实现 |
| 旧 DOC/PPT 转换提示 | studio/files.py:24；frontend/src/api/overseas/studio.ts 上传验证；专测覆盖 422 | 实现 |
| 统一上传、拖入、批量引用、移除、素材侧栏 | frontend/src/views/overseas/studio/OverseasStudio.vue:12；StudioMaterials.vue:5；use-studio.ts:76；最终默认/展开截图实际核对 | 实现 |
| 缩略图、放大、全选/半选、单图修改引用 | StudioTurns.vue:9；use-studio.ts:84；图片 URL 均经过任务授权 content 接口 | 实现 |
| 历史消息、刷新恢复、未知结果不自动新发 | use-studio.ts:11 持久 pending，:45 同 key 重试；后端 studio/service.py:16 幂等和状态检查 | 实现 |
| 历史修改引用不丢失 | 初版遗漏 reference_ids DTO，记录为 MEDIUM；现 studio/queries.py:70 返回 referencePictures，StudioTurns.vue:5 展示，test_overseas_studio.py:149 验证刷新及内容可读 | 已修复并独立复跑 6 passed |
| 持久执行进度与停止 | studio/queries.py:85 游标读取状态事件；studio/service.py:75 校验轮次所属任务并复用取消；执行边界保留租约/取消 fencing | 实现 |
| 每任务同时一轮、跨任务引用拒绝 | studio/service.py:26 任务锁+执行 gate；:51 校验附件与图片；test_overseas_studio.py:47、:85；infra/identity-test/studio_checks.py:7 为真实 PG 并发路径 | 实现 |
| 按 SKU 分批归档、不自动完成、不可变产物 | studio/service.py:85 校验任务 SKU、避免重复、禁止改归属；studio/models.py:45 持久产物；test_overseas_studio.py:127 | 实现 |
| 显式完成、有归档、无活动作业 | studio/service.py:109；OverseasStudio.vue:26 确认弹窗；测试覆盖提前完成/活动执行拒绝 | 实现 |
| 成品库展示与下载、旧归档兼容 | backend/app/overseas/archives/service.py:38、:65，新 studio: ID 与旧 PictureVersion 分支并存；测试验证 ZIP 内两份产物 | 实现 |
| 删除多余海外首页菜单、品牌跳任务 | frontend/src/views/overseas/OverseasPortal.vue；frontend/src/identity-main.ts 路由重定向 | 实现 |
| 五种可选角色、每人仅一个、待授权可空 | backend/app/overseas/members/schemas.py；auth/models.py:33 唯一 user_id；auth/dependencies.py:17 拒绝非法身份；frontend/src/views/overseas/admin/OverseasMembers.vue 单选 | 实现 |
| 管理员全部海外权限、不依赖创建/分配身份 | permissions.py:29 all scope；tasks/queries.py:9 可选管理员设计；materials/service.py:22、requirements.py:20、members/bootstrap.py:32 | 实现；任务状态仍受校验 |
| 历史多角色管理员收敛、歧义拒绝、保留审计 | migrations/overseas/versions/0011_single_member_role.py:25 先验全体再写；:40 审计旧值和版本；test_overseas_single_role.py:54 | 实现 |
| 最后有效管理员保护 | members/service.py:17 全权限写入 advisory lock；:87 校验最后管理员；既有成员测试与 PG 验证不以 SQLite 替代并发证明 | 实现 |
| 国内海外隔离 | overseas/db.py 独立 Base/运行域，迁移为 overseas 链；studio/execution.py 只读海外模型；无国内角色继承改动 | 实现 |

没有发现核心需求 HIGH 缺失。未授权生产部署、生产数据迁移及收费模型调用，不以本地 mock 证明真实模型可用。

## Stage 2：Code Quality — PASS

- 已检查新 studio 模块、Skill 包处理、权限与归档 diff：职责分文件；本轮正式 app/src 文件未发现超过 300 行；新增 TypeScript 无 any。
- 安全静态扫描未命中新加 eval、innerHTML/dangerouslySetInnerHTML、前端密钥变量或硬编码密钥。ZIP 路径、重复项、链接/特殊文件、压缩比、文件大小均有校验（management/packages.py:20）。
- 业务文件通过同域鉴权路由读取，校验任务归属（studio/queries.py:14、:30、:44）；输出复用最终回复收图校验，不直接信任任意路径（studio/execution.py:95）。
- 测试真实性：runner 专测仅替换进程边界，执行实际协议准备、状态发布和收图器；明确不是实收费 CLI。Skill 专测二进制资源校验并故意损坏对象验证失败。单角色迁移用旧表结构重建，避免在新唯一约束前提下伪测历史多角色。
- 未发现本轮新增无需求依据的业务功能。管理统计增加 studio 类型属于新执行接线。
- 已实际打开 `output/studio/expanded.png`、`single-role.png`、`skill-package.png`：正式工作台与管理邻居页的 Element 控件、蓝色主按钮、白色面板、边框/圆角一致；展开界面缩略图、侧栏、附件与发送区均在画布内；单角色编辑与完整包资源历史可见。
- 已实际打开最终 `output/studio/workbench-final.png`、`expanded-final.png`、`original-view.png`：默认 1280×720 的上传框、Skill 选择、发送按钮完整可见；展开模式保留资料侧栏；三张图均显示归档 SKU，原图查看器可见，邻居页面布局和色彩保持一致。布局证据对应 OverseasStudio.vue:44 视口高度计算及 studio.css:7，最终候选已包含此修正。
- 主 Agent 的 CUA 实查还覆盖选择 Skill、TXT 上传、引用图片、发送、整页刷新恢复、停止后已停止；浏览器连接真实隔离后端，图片是明确标注的离线验收 fixture，不声称模型生成已实测。代码路径证据：use-studio.ts:27、:45、:68；backend/studio/service.py:45、:75。
- 无未解决 HIGH/MEDIUM；已关闭历史引用遗漏和默认视口布局问题。范围内未实现项：无。真实付费 CLI 与生产部署属于本轮授权外验证边界。

## 已读取/执行的原始验证输出

Reviewer 独立执行四个专项文件：

```text
....................                                                     [100%]
20 passed, 2 warnings in 7.40s
```

主 Agent 提供日志已读取，`output/studio-frontend-tests-final.log`：

```text
ℹ tests 309
ℹ suites 0
ℹ pass 309
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8930.8086
```

`output/studio-frontend-build.log`（含类型检查+正式构建）：

```text
✓ built in 45.24s
```

首次 Linux 全回归 `output/studio-linux-tests.log`：

```text
8 failed, 1915 passed, 162 skipped, 15 warnings in 238.14s (0:03:58)
```

失败集中既有 supervisor/孤儿进程测试；加 Docker init 后专项 `output/studio-linux-supervisor-tests.log`：

```text
26 passed, 1 skipped in 43.64s
```

最终候选的全量 init 复跑 `output/studio-linux-final.log` 已读取：

```text
1923 passed, 162 skipped, 15 warnings in 230.07s (0:03:50)
```

最终候选前端全量 `output/studio-frontend-final.log`：

```text
ℹ tests 311
ℹ suites 0
ℹ pass 311
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8437.0125
```

最终候选编译 `output/studio-build-final.log` 原始命令与结果：

```text
> hengxin-smart-image-frontend@0.2.25 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 43.00s
```

历史引用修复后 reviewer 独立复跑：

```text
......                                                                   [100%]
6 passed, 2 warnings in 3.54s
```
