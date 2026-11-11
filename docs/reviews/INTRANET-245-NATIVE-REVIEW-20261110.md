# 原生服务候选首次审查

candidateId：`e99809885e786aa559d1a84a91984f27a1fa2f6dce9eda9822901b0af6aaf088`。

审查者：独立 native_review；本记录由主 Agent 根据其返回报告保存。

范围：`build_native.py` 与配套测试。Stage 1 **FAIL**；Stage 2 未执行。

HIGH：WorkingDirectory 和 EnvironmentFile 使用 ExecStart 的双引号格式；systemd 255 直接解析路径，无法将该格式解析为正确的绝对路径，七个候选服务不能可靠加载。原测试只验证生成字符串，没有验证 systemd 解析，未发现此问题。

要求：分离路径与命令参数格式；对路径使用严格绝对路径验证及适用转义；增加真实 systemd 正向验证和旧错误格式负向验证。修复后重新固定快照审查。本候选未部署。

参考：[systemd 255 路径解析源码](https://github.com/systemd/systemd/blob/v255/src/core/load-fragment.c#L2400-L2493)。
