# 海外 Skill 发布父目录权限修正审查

- candidateId：`deac809ca46f4033c0ad7acd4ae1acfd3c525e9618ffbeacbd86974e4831f0c5`。
- 结论：**Stage 1 PASS；Stage 2 PASS。无新增 HIGH / MEDIUM 阻塞项。**
- 范围：相对 `3a060c8cebcebe876931b3b1c636ecb6bc2fb9b5`，仅 `scripts/release/overseas-skills-runtime.py` 的 5 行修正及 `overseas-skills-tests.py` 的 3 个新增参数展开用例；需求依据 `docs/OVERSEAS-INSTALLED-SKILLS-RUNBOOK-20261013.md:59`。此前完整范围沿用 `docs/reviews/OVERSEAS-DELETE-SKILLS-FINAL-20261013.md`，本次不重新认证生产状态或全产品。
- 开始及报告落盘后 `review-status.currentId` 均与上述候选一致，受控变化仅上述两个脚本。未修改源码、未提交、未部署、未登记批准；另一个工作流的 Product-Spec、CHANGELOG 和成员隔离计划不在审查范围。

## Stage 1：Spec Compliance — PASS

| 本补丁全部要求 | 结论及证据 |
|---|---|
| umask 077 下新建及已有 700 的发布父目录均可被 worker 遍历 | 完整：`scripts/release/overseas-skills-runtime.py:82` 创建目录，`:84` 核实 root 所有的非链接目录，`:86` 显式 chmod 755 后才在 `:87` 调安装器。`scripts/release/overseas-skills-tests.py:35` 的两种真实文件系统用例均通过。 |
| 已有非目录、链接或非 root 所有目录拒绝 | 完整：`overseas-skills-runtime.py:83` 的 mkdir 对已有普通文件报错，`:84` 在 chmod 和安装调用前拒绝链接及非 root 所有目录。真实符号链接用例 `overseas-skills-tests.py:60` 验证拒绝、外部目录仍为 700、安装器未调用。非目录及非 root 所有分支为代码检查，未宣称已动态覆盖。 |
| 仅修正公共发布目录，不放宽备份、凭据、任务私有目录或全局 umask | 完整：新增 chmod 仅作用于 `ROOT / 'releases'`，没有递归 chmod、全局 umask 修改或其他目录操作，见 `overseas-skills-runtime.py:82`。`overseas-skills-tests.py:43` 在安装调用时真实创建无关私有目录并验证仍为 700；`:55` 恢复测试进程原 umask。 |
| 保持只读共享目录及隔离边界 | 完整：未改变 `overseas-skills-runtime.py:48` 的只读 bind、`:93` 的 API/native/sandbox 验证，以及安装器 `hengxin-smart-image/backend/app/overseas/management/skill_install.py:123` 的安全目录复核。本次变更不涉及业务代码、UI 或服务重启。 |

部分实现、未实现、Spec 漂移：本补丁范围内无。UI、邻居页面视觉对比不适用，未运行浏览器。

## Stage 2：Code Quality — PASS

- 权限与链接边界：`overseas-skills-runtime.py:74` 至 `:81` 已限定真实 ROOT、无链接祖先并设为 root:root/755；新增检查 `:84` 在 chmod 前拒绝链接，不修改其指向的私有目录。父目录 root:root/755 不允许普通 worker 替换 releases 目录项。没有新增可控路径、密钥、动态执行、shell 拼接或注入入口。
- 测试真实性：`overseas-skills-tests.py:33` 至 `:69` 实际调用 POSIX umask、mkdir、chmod、chown、symlink 与 stat，仅替换安装子进程及证据写入。reviewer 在 Linux root、无网络、仓库只读挂载的容器内独立执行新增 3 例，0 跳过；没有用 Windows 跳过或模拟 stat 当作权限证明。这些测试验证安装前权限，不冒充实际非 root worker 沙箱测试。
- 结构：运行脚本 106 行，测试文件 103 行；修正直接置于既有 install 入口，无新增依赖。证据：`overseas-skills-runtime.py:73`、`overseas-skills-tests.py:36`、`:60`。

## 验证原始输出

reviewer 独立运行：

```text
docker run --rm --init --user 0 --network none -e PYTHONDONTWRITEBYTECODE=1 -v D:/Work_Project/hengxin-smart-image:/workspace:ro -w /workspace hx-overseas-delete-skills-test:local /app/.venv/bin/python -m pytest -q -p no:cacheprovider scripts/release/overseas-skills-tests.py -k "install_catalog_is_traversable or install_does_not_chmod_linked"
...                                                                      [100%]
3 passed, 8 deselected in 0.61s
```

reviewer 对两份文件以 Python `compile()` 独立编译，不写字节码，退出码 0：

```text
scripts\release\overseas-skills-runtime.py: 106 lines
scripts\release\overseas-skills-tests.py: 103 lines
PYTHON_COMPILE_PASS 2 files (no bytecode written)
```

第一次编译命令因 PowerShell 嵌套引号构造错误出现 `SyntaxError: '(' was never closed`，改用 here-string 后得到以上结果；不是源码编译失败。

另读取主 Agent 的发布脚本回归日志 `output/release/overseas-20261013-3a060c8/permission-regression.log:1`，未重跑此前完整范围：

```text
.........................................................                [100%]
57 passed in 1.58s
```

允许主 Agent 对同一 candidateId 登记两阶段 PASS。本报告不替代生产恢复证据，不批准改写原 release manifest，也不宣称已执行服务器副本留存。
