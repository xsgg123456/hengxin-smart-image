# Harness 审查协议验证

2026-09-09，用户授权修复重复审查门禁。框架规格见HARNESS-REVIEW-PLAN.md，使用协议见HARNESS-REVIEW.md。没有改产品代码，也没有提交或推送。

## 回归证据

Windows Python 3.12执行 `python scripts/check_harness.py`，PATH含本地Python与Node。输出：

```text
Ran 60 tests in 57.267s
OK
PASS: offline harness checks. Runtime discovery/trust: inspect Codex /hooks and /skills.
```

完整日志 `output/harness-review-final-validation.log`。其中30项生命周期测试保留原提交类型检查、自动推送保护和嵌套目录真实注册命令；23项新增快照测试；7项报告恢复、技能引用和状态锁测试。所有Git写入发生在临时仓库，无远程写入，自动清理。

覆盖：已有HEAD基线与脏改动、旧clean不能授权、空白/配置/框架变动、CRLF等价、忽略产物、候选期间变动、两阶段FAIL、报告缺失/路径越界/变动、损坏状态、暂存旧版本与已审新版本差异、已审提交不使Stop失效、部分提交、一次性checkpoint与后续修改失效、报告过期后重新送审恢复、并发锁等待及超时不删除其他锁。

`python -m py_compile .codex/hooks/harness.py .codex/hooks/review_gate.py .codex/hooks/review_files.py .codex/hooks/review_store.py`退出0。`git diff --check`无错误。新旧受改Python文件均小于300行。

## 独立审查与现场登记

送审candidateId：`f99d6cb15d30998e24cfa5fb26fbf269fbfb272b55aad8474ea72817d93f225a`。初审HARNESS-REVIEW-REPORT.md发现的Shell表达式、紧凑Git参数和只读查询问题已修复并加入回归；第二轮HARNESS-REVIEW-SECOND.md发现的Windows Git大小写绕过已修复并加入回归；最终复审报告HARNESS-REVIEW-FINAL.md两阶段均PASS，独立14项抽查与7文件语法编译通过。真实工作区review-approve成功；review-status返回approved=true、currentId=reviewedId、changedFiles=[]；连续两次stop-gate均返回{}，退出0。

hooks.json注册未改变；本机继续调用相同harness.py入口。普通终端、未被匹配/识别的包装命令不属于Codex命令门禁保证，仍需CI/服务端保护。checkpoint是明确暂停，不是审查批准。本次未改变hook信任配置。

补充验证：原完整60项测试通过的日志含既有Windows GBK读取线程异常。设置PYTHONUTF8=1重跑时无解码异常，59项通过，首项test_array_command_input_is_supported遇Git进程异常超时（日志报告负数剩余时间-1805秒，工具调用同时挂起约1848秒）；该项在相同UTF8环境单独重跑0.783秒通过，代码未改变。原始日志output/harness-review-utf8-validation.log保留，不将该次整轮标为全绿。
