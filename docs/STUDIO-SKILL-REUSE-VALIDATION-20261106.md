# 同会话技能复用验证 · 2026-11-06

## 本地证据
- 前端 `pnpm typecheck` 退出0；`pnpm test` 527 passed、0 failed、0 skipped；`pnpm build` 退出0、53.86秒。无前端源改动，构建产物不发布。
- 后端 `python -m compileall -q app` 退出0。
- 新增三文件专项：50 passed、10 skipped（Windows缺符号链接权限、POSIX权限及Linux/Bubblewrap条件）。Linux必须补验，不把skip记成通过。
- 全后端 `python -m pytest -q`：2725 passed、430 skipped、10 failed，556.47秒；原始证据 `output/skill-reuse-backend-full.log`。其中1项为旧persistent_mounts测试要求round/skills且fixture不是实际UUID目录，已调整为真实目录结构及本轮cache契约；业务校验未放宽。
- 修订后的5文件（3个cache测试、test_studio_skill_trigger.py、test_studio_persistent_mounts.py）定向回归：63 passed、11 skipped，15.76秒。覆盖实际materials.prepare接线、两来源AA/ABA/内容升级、并发、失败重试、篡改/链接拒绝、不同会话隔离、历史字节和inode/mtime、当前技能只读挂载、取消选择、整会话删除兼容；Linux受限用例待安装补验。
- 其余9项全量失败：从未改的HEAD e8a3af4通过git archive导出app/tests/pyproject，在隔离目录复用同Python依赖执行4个失败文件，完全复现同9失败、43通过，5.80秒。证据 `output/skill-reuse-head-failures.log`；主要为既有Windows安全读取/链接条件及接口清单断言。未改无关断言掩盖失败。
- 发布工具 `python -m unittest discover -s scripts/release -p test_skill_reuse_release.py -v`：10 passed；覆盖双代理匹配、旧worker期限、absent备份/恢复、源范围与漂移、会话元数据和API重启身份检查。真实Linux部署尚未执行。

## 生产交付边界
用户已授权提交与部署。无数据库迁移、UI变更、模型调用或历史删除。实际Linux安装、真实已安装技能探针、独立审查、生产排空和会话保留验证执行后在本文件/部署记录追加证据；当前不声明已上线或所有会话已做真实模型续聊。

## 首轮独立审查与修复
首轮candidate `04df81b5439075f37d5a0675d36cb70ab301525f0660abe7f6ef7879b3735ec8` Stage1 FAIL，Stage2未执行：发布测试target/vendor受umask077影响不可遍历；gate初始idle失败留下owner而recover缺少GATE_STARTED。已修复目录根显式chmod755和未开始切换时核实原状态后取消的恢复分支。业务代码未改变。新增实际main/gate/recover与漂移保护回归。主Agent在WSL Ubuntu运行 `python3 -m unittest discover -s scripts/release -p 'test_skill_reuse*.py' -v`，15/15 PASS（0.422秒），其中真实nobody UID在umask077下导入候选app/vendor通过。Windows同套14通过、1Linux条件跳过。复审candidate为 `fe2bb8c483ca7ef2298789c9fdcfbf38ba6cd09c1db2f0d2602bd43fa52ec826`，等待独立结论。

## 最终源码审查
`STUDIO-SKILL-REUSE-FINAL-REVIEW-20261106.md` 对上述复审candidate给出Stage 1 PASS、Stage 2 PASS，主Agent已用review-approve登记同一快照。独立复跑WSL发布测试15/15、Windows后端63通过/11环境跳过、18文件编译及真实临时文件恢复通过。正式Linux安装、真实catalog和生产保留验证仍待执行，未用本地结果替代。

## 首次服务器隔离安装
代码提交731c84e，包SHA256为79df247b6b454fc661daada439195d4e70a4b3a4d6ce46a50e49aa40032bdd89，prepare成功且生产服务未改变。candidate测试在导入pytest时失败：`ModuleNotFoundError: No module named 'py'`。实际API镜像pytest9.1.1中存在`site-packages/py.py`兼容模块，发布vendor遗漏该单文件模块。仅修发布工具：白名单补入py.py并保留0644；Linux普通UID回归fixture实际让pytest导入py，防止只测目录可读而漏依赖。WSL15/15通过（0.558秒）。业务三个模块未变，生产仍未关门/切换；修复重新审查提交打包后重试。

## 第二次服务器隔离安装
单文件依赖修复经独立两阶段PASS（VENDOR-REVIEW报告），提交db56bf1、包SHA256为5612ce54ca5d62610287c8eac3c16b2f19c9195c3ddb1c5564699067e41ff869。真实服务UID999从候选安装目录跑完74/74（6.44秒，无skip），包括实际Bubblewrap挂载。额外root测试2项失败：invoke给所有0700临时根都设为服务UID，root用户命名空间中无法遍历该根。仅改invoke使临时根属主等于该次执行UID/GID；新WSL实际chown测试覆盖root/nobody，全部16/16通过（0.407秒）。在服务器仅调整原失败的隔离测试根属主为root，原正式包测试和候选代码原字节重跑，两项2/2通过（1.51秒），证明根因；这是诊断证据，不替代新固定提交的完整安装测试。生产服务仍未关门或切换。
