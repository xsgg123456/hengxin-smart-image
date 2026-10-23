# 多会话发布 Skill 基线增量审查 · 2026-10-24

- candidateId：`c7e1e372b5f4c3ba2873cb5951b714f3ba10b1842774268cf8089058d41311d5`。
- HEAD：`39780d3c259e865423d7abbf4b64499ffd346052`。
- **Stage 1：PASS；Stage 2：PASS。未关闭 HIGH 0、MEDIUM 0。**
- 范围：`scripts/release/overseas-studio-sessions-skills.py`、`test_studio_sessions_skills.py`、`overseas-studio-sessions-deploy.py`、`package-studio-sessions.py` 四文件。只审查并写报告；未修代码、提交、部署、登记批准或写 clean。
- 依据：code-review skill、`docs/HARNESS-REVIEW.md:7`、`docs/STUDIO-SESSIONS-IMPLEMENTATION-20261024.md:5` 与 `:30` 的保留既有 Skill/权限和实际安装包约束。

## 快照与继承证据

使用 `.codex/hooks/review_files.py:118` 的 snapshot 和 `:45` 的 identity 独立读取1909个受控文件，重算当前candidate完全匹配。与 `.codex/review-state.json:1` 中原批准快照 `7140363213468c8532014cd6fbde22557bdac57d35980f0d479bbea8242dc6f3` 逐项比较，**只有上述四文件变化**。原批准报告原始字节SHA256与凭据一致。AGENTS.md与原批准快照一致，用户预存修改未被覆盖；本报告不授权将其纳入发布提交。

`git diff`显示两个既有文件仅增加 verifier 加载/替换、部署 REQUIRED 和打包 REQUIRED；两个新增文件全文已读。旧 `scripts/release/overseas-skills-runtime.py`、安装器、应用/UI、数据库迁移、所有其余运行配置均与原批准快照一致。因此继承 `docs/reviews/2026-10-24-studio-sessions-approved.md:18` 的全部12项合同结论及各自代码证据，逐项为：会话上限/历史/删除；互斥/并行/停止/未读；数据与凭据隔离；选择/草稿/滚动/迟到响应；归档来源与删除后下载；完成/解冻；批准UI与窄屏；DTO/API/上传；旧未确认请求；删除清理重试；0021迁移；发布隔离恢复。最后一项的Skill verifier变更由本报告重新审查。不存在以旧结论覆盖未核对代码的情况。

原干净发布工作树 `30f56852654ada041e74a86924e05781db59fc4ecf858213e030e928b2b206e8` 的核对记录见 `docs/reviews/2026-10-24-studio-sessions-package-snapshot.md:10`；本报告批准当前主树增量，不声称旧上传包已经包含新文件。

## Stage 1 · Spec Compliance

| 检查 | 结论与证据 |
|---|---|
| 固定真实已安装集合，不安装旧集合 | 完整实现。新 verifier `scripts/release/overseas-studio-sessions-skills.py:9` 固定 release `8ea5d6ffc55e6508a1f4003a8f5bed4ffc3ca4b25de42cba29f8724a8488c339`、15包227文件，与直接读取的 `output/studio-sessions-release/skills-baseline.jsonl:1` 三端摘要相符。不是取消集合校验。 |
| 三端完整性、同目录、只读和非root | 完整实现。新 verifier `:14`–`:27` 对native/API/sandbox分别核对release/包数/文件数，比较device+inode，固定API bind源/目标且RW为False，检查sandbox非root、结果15条、名称唯一、文件总数227、全部只读。保留旧 verifier `scripts/release/overseas-skills-runtime.py:91` 原有约束并增加结果完整性。 |
| 核验真实字节而非只信摘要 | 完整实现。沿用 `hengxin-smart-image/backend/app/overseas/management/skill_install.py:216` verify分支与 `installed_catalog.py:34`、`:57`、`:95` 的manifest摘要、精确目录项、包校验和/条目验证；`skill_probe.py:16`、`:38` 使用真实沙箱逐文件摘要并尝试写打开，要求失败。probe仅创建临时诊断工作区，未调用模型或修改Skill内容/指针/开关。 |
| 仅本次发布替换verify，旧发布语义保留 | 完整实现。`overseas-studio-sessions-deploy.py:21`–`:22` 仅替换本次导入的m.skills.verify；`member-release-runtime.py:11` 为独立模块加载，不修改旧helper源文件或install/preflight函数。原 `overseas-archive-deletion-deploy.py:167` 在PREPARED前调用verify、`:171` 写凭据的顺序保持。排空、迁移、切换和恢复代码无差异。 |
| 打包与运行时必要文件 | 完整实现。`overseas-studio-sessions-deploy.py:39` REQUIRED及 `package-studio-sessions.py:13` REQUIRED都包含新helper；`test_studio_sessions_skills.py:54` 实际导入两入口，断言函数绑定、双方REQUIRED和selected映射。`package-overseas.py:150` 仍拒绝缺失必要文件。 |
| 产品行为、引导与UI | 无增量变化。由精确快照差异继承上述12项和原报告实际页面/邻居页面视觉对照；本轮未重开浏览器，不冒称新增视觉实测。 |

部分实现、未实现、Spec漂移：本次范围内均无。修复落实保留当前Skill的既有合同，没有新增业务功能或改变Skill开关。

## Stage 2 · Code Quality

- 代码质量 PASS：四文件分别292、29、40、60行，均≤300行；新helper职责单一，失败断言在保存成功凭据之前；JSON/子进程错误沿用失败退出，不吞错。发布CLI `overseas-studio-sessions-deploy.py:290` 保留拒绝Python优化模式，断言不会在支持的CLI执行方式中被静默移除。
- 测试真实性 PASS：`test_studio_sessions_skills.py:19` 直接调用真实verify，12个参数覆盖成功、release/计数/目录身份/挂载来源和RW/root/空结果/重复名称/文件总数/单包可写；失败断言不保存成功结果。`:54` 实际加载发布和打包链。mock不证明Linux真实沙箱，本报告将其与实机证据明确区分；旧Skill测试与多会话发布故障测试一起独立通过。
- 安全扫描 PASS（增量范围）：四文件扫描eval、危险HTML、VITE密钥变量、密钥前缀、password赋值及用户绝对路径均无命中。`overseas-studio-sessions-skills.py:14`–`:18` 仅常量参数调用既有读取命令，`:28` 仅私有结果凭据写入；沿用 `overseas-skills-runtime.py:15` 海外环境白名单与 `:29` 非root执行，不新增凭据输出、网络入口或安装/删除行为。
- 视觉 PASS（继承）：应用/UI哈希全部不变，继承原报告 `docs/reviews/2026-10-24-studio-sessions-approved.md:46` 的真实邻居页面对照；本轮无UI代码需要新渲染比较。原全量验证及依赖告警/跳过边界保持。

## 独立执行原始输出

默认Python未安装pytest，首次启动失败，随后使用项目现有venv成功；未安装依赖或改变环境：

```text
C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest
```

命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_studio_sessions_skills.py scripts/release/test_studio_sessions_release.py scripts/release/overseas-skills-tests.py -q -rs`，退出码0：

```text
............................................sss......                    [100%]
=========================== short test summary info ===========================
SKIPPED [2] scripts\release\overseas-skills-tests.py:33: real production POSIX root ownership and umask required
SKIPPED [1] scripts\release\overseas-skills-tests.py:58: POSIX symlink safety
50 passed, 3 skipped in 1.26s
```

逐文件调用Python `compile` 编译实际字节，退出码0，原始输出：

```text
scripts\release\overseas-studio-sessions-deploy.py: compile PASS, 292 lines
scripts\release\overseas-studio-sessions-skills.py: compile PASS, 29 lines
scripts\release\package-studio-sessions.py: compile PASS, 40 lines
scripts\release\test_studio_sessions_skills.py: compile PASS, 60 lines
```

本轮未重复前后端全量、生产构建或生产部署。生产基线JSONL显示三端release/15/227及device64770、inode1708242一致，sandbox uid999；该文件来自主Agent实查，本reviewer直接读取，不冒称亲自连接服务器。

成稿后主Agent取回新verify成功凭据 `output/studio-sessions-release/skills-current-verification.json:1`，说明首次SSH连接90秒超时、远端完成，随后另连读取并取回。reviewer独立解析该凭据，断言三端固定release/15/227、同device64770/inode1708242、sandbox uid999、15个唯一且全部只读结果、文件求和227、modelCalls=0、sharedDirectory=true。原始输出：

```text
receipt PASS; sandbox uid=999; 15 unique readOnly results; modelCalls=0; sharedDirectory=true
final candidate: c7e1e372b5f4c3ba2873cb5951b714f3ba10b1842774268cf8089058d41311d5
```

实机执行归属主Agent，本reviewer核验结果；末次快照重算仍匹配本candidate，审查期间没有受控代码变化。源码两阶段PASS不代表部署完成；主Agent需用此candidate登记凭据，提交后生成新不可变发布包，再完成实际安装/准备/部署和生产验收。旧已上传包不得原地修改。
