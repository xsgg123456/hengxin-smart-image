# Harness 审查交接改造

2026-09-09。用户授权修复重复审查提示。仅修改研发框架，不改变产品功能，不自动提交或推送。

## 目标和验收

1. 审查凭据绑定代码快照：prepare固定候选文件哈希；approve要求候选编号、两阶段PASS和仓库内报告，批准前重新比较当前代码。中途修改不得批准新版本。
2. 文件检测和Stop不得覆盖批准记录：当前版本与批准版本相同则放行；不同时指出差异，不笼统宣称从未审查。旧clean字符串不作为新凭据。
3. 提交前检查暂存内容：除类型检查外，比较暂存区相对HEAD的受控文件变化与已批准快照。拒绝自动改变暂存内容的commit -a/路径提交，要求先git add再检查。普通提交不使凭据失效。
4. 明确暂停：checkpoint绑定当前快照和原因，仅允许一次停止回复，不批准代码、不允许未审提交；后续修改使checkpoint失效。用于中途问答/等待/用户暂停，不用于完成声明。
5. 受控文件含源代码、运行配置、依赖清单和框架规则；排除Git忽略文件、依赖、构建和日志产物以及状态文件自身。普通Markdown报告不进代码快照，AGENTS及技能规则进入。规范化文本CRLF/LF，但不忽略空白或尾部代码改动。
6. 临时Git仓库回归覆盖初始脏改动、重审差异、审查中改动、凭据损坏、暂存与工作区不一致、提交后停止、checkpoint、配置/框架文件与生成文件。旧类型检查和自动推送保护保持通过。
7. 同步AGENTS、开发/修复/审查技能、reviewer角色及README；独立两阶段审查通过后，使用新协议登记本次框架改动。不关闭hook，不降低未审代码提交检查。

## 接口和存储

现有hooks.json注册不变。harness.py新增CLI动作：review-prepare、review-approve、review-status、review-checkpoint；使用JSON参数传递候选id、report、stage1、stage2、reason。命令行以第二个参数传JSON，不带参数的生命周期hook继续从stdin读取。

独立review_gate.py暴露run(root, action, data)、stop(root)、check_commit(root)；status返回currentId、reviewedId、changedFiles、approved，prepare返回candidateId，approve返回approved和reviewedId。异常清晰失败；Stop返回原有block结构或None，提交返回原因字符串或None。

.codex/review-state.json保存baseline、candidate、approved、checkpoint；原子写入并串行化状态变更。baseline仅表示首次接入时已存在HEAD，不冒称人工审查；首次工作区脏改动不能建立已批准基线。批准记录含报告哈希。旧.needs-review/.review-snapshot.json不再驱动状态，保留为迁移遗留，不能单写clean绕过。

这是协作门禁，批准动作仍由主Agent依据真实reviewer结论调用；不是密码学签名或服务端分支保护，普通终端绕过Codex仍需CI兜底。
