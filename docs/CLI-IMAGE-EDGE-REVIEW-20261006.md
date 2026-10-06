# CLI 会话外层 SSE 配置补丁审查

日期：2026-10-06。candidateId：`1970aa2d5fb72d70be8c44e247d0d0df8805e370a14bc036462f687f199072c9`。

**Stage 1：PASS。Stage 2：PASS。** 批准本补丁代码，不代表公网 SSE 已修复验收；应用后必须重测。

范围：相对已批准7b8b90cbb0da8c770d1c20681d89c8316166509b8a64b2e5cb6290b62405db88仅新增scripts/release/install-cli-sse-edge.py。业务及发布脚本结论沿用前两份PASS报告。依据CLI-IMAGE-RELEASE-20261006.md新增外层缓冲实查记录；按code-review skill仅审查、内存mock与报告，不操作生产。

## Stage 1

| 要求 | 结论与证据 |
|---|---|
| 仅精准会话events路径关闭缓冲 | 完整实现。install-cli-sse-edge.py:12 使用首尾锚点、task/item各单路径段、可选尾斜线；:13 使用原18080上游，无URI替换；:20–24 清Connection并关闭buffer/cache/gzip、75秒读超时。非会话路径不匹配。 |
| 保留生产其它配置 | 完整实现。:29–37 校验唯一anchor、站点名、唯一原upstream且无已有会话配置，仅在anchor后插入BLOCK。mock断言移除新BLOCK后与原文完全一致，错误站点/anchor/已有不同会话配置均拒绝。 |
| 固定发布范围与备份 | 完整实现。:42–45 固定release正则、固定container/config和备份父目录，:56–58 排他创建备份并设0600，完成备份后才写配置。不会覆盖已有备份。 |
| 配置检查、reload、失败回退 | 完整实现。:59–67 写入后nginx -t再reload；任一步异常恢复原内容、再次-t与reload，重抛原失败。mock分别注入首次-t失败和首次reload失败，最终内容原样且恢复检查/重载均执行。恢复自身失败会向调用者报错，不伪称成功。 |
| 幂等与安装后核对 | 完整实现。:30–31 已含完全相同BLOCK返回原文；:53–55 不再写备份或reload；:69 读回全文核对。mock第二次运行只有读取，没有变更。 |

部分实现、未实现、Spec漂移：未发现。应用前真实配置校验由脚本断言把关；实际Nginx匹配优先级与公网首帧到达仍需部署后冒烟证明，不能由mock替代。

## Stage 2

- 质量：脚本74行，patch构造与执行分离，异常明确抛出，无自动扩大匹配或全站配置替换。证据：install-cli-sse-edge.py:29、40。
- 安全：无凭据；固定docker/container/config，release正则约束备份目录；写入用`cat > "$1"`的固定shell片段并以位置参数传路径、stdin传完整配置，不把配置作为shell代码。证据：:46–50。配置备份留服务器目录，不写日志；成功只输出哈希（:70）。
- 测试真实性：内存替换subprocess与备份根路径、临时文件真实写读，检查成功/二次幂等/失败恢复和原配置保留；没有连接Docker或生产。新脚本无UI，视觉比较不适用。
- 运行限制：备份已有但补丁未安装时再次运行会拒绝覆盖，这是保护原备份的行为；应由主Agent核对失败现场后处理，不能盲目重试。主线程应将真实nginx -t、reload与公网/内网SSE首帧证据记入发布记录。证据：:56、61–67。

无新增HIGH/MEDIUM问题。

## 独立测试和编译输出

内存mock原始输出：

```text
EDGE_SSE_INSTALLED sha256=18325d60b4f029b1b4d8c05117b537d320754497a19202348c0bc29a0c3cdbbe
EDGE_SSE_ALREADY_INSTALLED
PASS success_and_idempotency
PASS test
PASS reload
PASS original_preservation_and_invalid_baseline_rejection
```

进程exit_code=0。上述哈希属于合成配置，绝非生产配置。

`python -m compileall -q scripts/release/install-cli-sse-edge.py`：stdout为空，exit_code=0。

## 快照

开始review-status currentId与1970aa2d5fb72d70be8c44e247d0d0df8805e370a14bc036462f687f199072c9一致，changedFiles只有该脚本。主Agent可据两阶段PASS登记同一快照；实际生产应用和恢复验证另记。
结束校验：报告写入后currentId仍为1970aa2d5fb72d70be8c44e247d0d0df8805e370a14bc036462f687f199072c9，代码快照无变化。
