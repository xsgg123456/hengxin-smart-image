# 原生服务配置保留修复审查

- candidateId：`8c99788f55aaa8793b7d39a089ff829ae7fb0b93bd7565035701f70a89d42ce8`
- 最终结论：**Stage 1 PASS；Stage 2 PASS**。仅适用于此快照；初审发现已修复并从 Stage 1 重新验证。
- 范围：本次 `scope_engine.py`、`test_scope_engine.py`、`test_scope_flow.py` 和 `docs/INTRANET-RELEASE-TOOLS.md` 差异；关联引擎仅追踪配置摘要、恢复和分组边界。
- 依据：发布工具文档第19行的“只替换 WorkingDirectory、逐字保留其它配置、结构异常准备阶段拒绝”，以及交接要求“严格单 Service、单 WorkingDirectory”。产品需求未变；未重复审查已提交的工作台功能。
- 初审快照为 `034cc2b7fa7745d239dd30c44531d408efa090a9c8e56f8ca705f0cca8def1fd`；主 Agent 根据发现修改了解析器及拒绝测试，重新 prepare 为本报告最终 candidateId。审查员读取新旧差异并重新执行全套测试。未修改代码、未操作远端、未读取凭据。

## Stage 1：PASS

### 完整实现

- 标准既有配置的保留与恢复：`scripts/release/intranet/scope_engine.py:98` 从原配置备份构建候选，仅替换匹配的目录行；第107行更新候选摘要。`test_scope_engine.py:116` 实际走 prepare/apply/recover，断言发布门禁、工作台目录和含空格环境项保留，恢复后逐字等于原配置。独立运行该目录全套测试通过。
- 原备份和恢复校验未被移除：`scripts/release/intranet/engine.py:71` 校验备份摘要，第76行校验候选摘要，第212行恢复入口继续绑定已启动事务；没有恢复数据库或修改另一业务逻辑的新增分支。
- 分组与纯前端边界保持：`scope_engine.py:85` 仅 full 模式选择本组 native，第102行只遍历该集合；`test_scope_engine.py:90`、第187行和第258行分别验证国内/海外、失败恢复时其他 drop-in 不变、共享纯前端。全套隔离测试通过。
- 异常结构和重试：`scope_engine.py:17` 至第22行补充含空白赋值计数、Service 首行与续行拒绝；`test_scope_engine.py:136` 覆盖6类拒绝。审查员额外通过实际 engine.prepare 注入空白重复／段外赋值，两次均抛出结构错误，没有服务切换、没有 started.json，直接 apply 也被 scope binding 拒绝。`release.py:103` 仅 prepare 成功才推进为 prepared；第119行及第217行保留准备失败后的恢复／取消流程，后续使用新事务重试。
- 无产品功能漂移：差异仅配置生成、回归 fixture 及发布说明；无页面、API、表、依赖或迁移新增。UI、设计稿及邻居页面视觉比较不适用于此范围。

### 已关闭的初审发现（不属于最终待修问题）

**MEDIUM，已关闭 — 初审单 WorkingDirectory／Service 内归属校验不完整。**

- 初审位置：`scripts/release/intranet/scope_engine.py:15`、第16行、第17行。以下为旧快照问题和复现，最终实现已拒绝这些输入。
- 要求：原配置结构异常在准备阶段拒绝，严格单 Service、单 WorkingDirectory。
- 实际：正则只数行首精确 `WorkingDirectory=`，不识别 `WorkingDirectory =`，并未检查目录指令位于 Service 段之内。以下输入均被接受：

```text
[Service]
WorkingDirectory=/previous/backend
WorkingDirectory = /previous/backend
```

```text
WorkingDirectory=/previous/backend
[Service]
Environment=X=Y
```

- 独立复现实测原始输出：

```text
spaced duplicate b'[Service]\nWorkingDirectory=/new/backend\nWorkingDirectory = /previous/backend\n'
assignment before section b'WorkingDirectory=/new/backend\n[Service]\nEnvironment=X=Y\n'
```

- 影响：第一种输入保留了额外的有效目录赋值，不能保证新候选实际工作目录切到目标源码；第二种输入不满足声明的结构要求。systemd 官方说明等号前后的空白被忽略：[systemd.syntax](https://www.freedesktop.org/software/systemd/man/latest/systemd.syntax.html)。当前联合升级生成的标准格式能通过，未声称生产已经出现此种格式。
- 修复结果：最终 `scope_engine.py:17` 至第22行已保守拒绝上述输入及续行；`test_scope_engine.py:136` 已补齐对应拒绝用例。初审缺口关闭。

### 未实现

本范围无未实现或部分实现条目；无未解决 HIGH／MEDIUM 问题。

## Stage 2：PASS

- 结构、命名与错误处理：`scope_engine.py:13` 为独立转换函数，保守拒绝未知输入；第98行复用原准备和摘要机制。生产文件126行、直接新增回归文件280行。`test_scope_flow.py:119` 仅补足模拟 baseline 的 configs/dropins 字段，没有放松生产校验；该测试文件385行，超过300行标准是既有情况，本次只净增1行，不因此要求扩大本轮重构。
- 测试真实性：`test_scope_engine.py:123` 至第134行实际走引擎 prepare/apply/recover，并比较候选和恢复原字节；没有只用模拟返回值证明保留成功。第187行及第207行的既有故障注入仍覆盖失败、恢复和中断。`test_scope_flow.py:113` 的轻量状态机 fixture 不承担原生配置内容验证，这部分由前述真实引擎回归覆盖。
- 安全扫描：对3个变更 Python 文件扫描 eval、innerHTML、暴露前端密钥、密码字面量和常见真实密钥前缀，无匹配。`scope_engine.py:23` 至第24行仅构建配置字节，无 shell 拼接执行；第105行读取既有受控事务备份，不打印其内容；`engine.py:71` 和第76行备份／候选摘要保护仍在。
- 视觉比较：无 UI 变更，邻居页面实际渲染比较不适用；不将其记录为已测试。
- 边界：测试模拟 Docker/systemd 操作，证明配置、事务和命令选择，不证明真实生产进程已采用新环境；上线验证仍由主 Agent 执行。

## 独立验证原始结果

命令：`wsl -- /tmp/hengxin-domestic-studio-python/bin/python -m pytest /mnt/d/Work_Project/hengxin-smart-image/scripts/release/intranet -q`

```text
........................................................................ [ 18%]
............s........................................................... [ 36%]
...................................ss..........s........................ [ 55%]
....s............................................................ [ 71%]
................................................................ [ 88%]
...............................................                          [100%]
387 passed, 5 skipped, 15 subtests passed in 12.78s
```

使用同一 WSL Python 对三个变更 Python 文件执行 `compile(path.read_bytes(), str(path), 'exec')`，退出码0，原始输出：

```text
COMPILE_OK scope_engine.py
COMPILE_OK test_scope_engine.py
COMPILE_OK test_scope_flow.py
```

全套测试包含5个跳过项；不将隔离测试称为生产运行核验。

## 补充：安装脚本只读查看

主 Agent 另提供 `output/explicit-skill-install-tool-fix.py`（不在候选快照内）。静态看到持官方锁、无 pending 检查、源清单摘要核验、新目录内测试、台账/旧入口复核和原子切换；本审查没有执行它，亦未核验远端实际环境，不将此脚本登记为本候选批准内容。
