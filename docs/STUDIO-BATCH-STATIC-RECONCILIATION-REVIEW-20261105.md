# 公共 SVG 换行对齐操作审查

- 结论：**Stage 1 PASS；Stage 2 PASS**，仅覆盖下述固定脚本及受控执行方式，不替代生产执行验收。
- 主 Agent 提供产品 candidateId：`6b97aef93e64853191bd2afab7fe8679667e3500f24309d6b35a29cfe13ec387`；产品提交 `68afe2a`。本报告不重新批准产品功能或扩展该候选快照。
- 独立审查对象：`output/batch-annotation-preview/reconcile-static-newlines.py`（下称 S），SHA256 `E9FFD8BE2B13C8C66CF58E4A935C1AFEB464D631590A9E683D76DA259185F769`。审查前后哈希一致；未修改脚本或产品代码。
- 范围：将既有 0.2.63 前端的 favicon 与 12 张 sample SVG 从 CRLF 对齐为已签发布包的 LF，备份后可恢复；不改包、manifest、部署运行器或业务内容。产品部署授权依据 `Product-Spec.md:1`；操作验收依据本次主 Agent 交接。
- 执行约束：主 Agent 已确认使用 `env -u PYTHONOPTIMIZE python3 -B`，不使用 `-O`，以启用脚本所有 assert 门禁；完成后仍运行原 frontend 全量门禁与 resume。

## Stage 1 — PASS

| 交接要求 | 结果与证据 |
|---|---|
| 固定版本、manifest 与来源字节 | 完整：S:13–17 校验 prepared manifest 摘要、release/mode、旧版 0.2.63；S:24–28 校验所有前端来源文件摘要。 |
| 首次碰撞集合恰好 13 个 | 完整：S:8 固定集合，S:23–30 扫描 manifest 内所有前端文件，排除入口后要求集合严格相等；额外 JS 碰撞与缺失 SVG 均实测拒绝。 |
| 只改变换行 | 完整：S:31–35、48–50 要求旧字节仅 CRLF→LF 后严格等于新字节，并拒绝新文件中的 CR；非格式差异实测拒绝。 |
| 私有备份全部原字节后再改目标 | 完整：S:36–43 创建 0700 备份目录，逐文件复制并核对原摘要，最后原子发布 receipt；S:20 拒绝不完整备份。 |
| 写入前重新检查、逐文件原子替换 | 完整：S:44–51 对全部 13 个记录重新验证备份、来源、目标；S:52–63 使用同目录独占临时文件、fsync、chown、chmod 和 replace，最后核对全部新摘要。 |
| 中断恢复与范围约束 | 完整：S:51 接受原/新两种已知摘要，S:54 跳过已完成文件，S:56–58 拒绝未知临时内容；实测替换途中失败后恢复，备份仍等于全部原字节。S:52 只迭代固定 13 项。 |
| UI、业务漂移 | 不适用新增页面视觉审查；S:34、50 保证内容仅换行差异，S:8、52 限定静态资源，无新增 API、页面或业务行为。 |

无部分实现、未实现或 HIGH 问题。首次完整碰撞扫描不在 receipt 恢复分支重复；恢复只验证登记的 13 项（S:19、44–51），因此后续原 frontend 全量门禁是本操作流程的必要步骤。

## Stage 2 — PASS

- 质量：64 行、单一操作职责；所有异常中止执行，不静默吞掉失败（S:1–64）。压缩排版不影响本次有限范围核验。
- 安全：固定生产路径与名称集合（S:4–8），禁止路径及祖先符号链接（S:10–12），无 shell/eval、凭据或网络调用；未知目标摘要和临时内容均拒绝（S:51、57）。安全门禁依赖非优化 Python，执行方式已明确。
- 权限：备份根目录 0700（S:36）；替换文件继承原 UID/GID 和普通权限位（S:55、61）。`& 0o777` 不保留特殊权限位；已读取主 Agent 的生产只读权限证据 `output/batch-annotation-preview/static-newline-permissions.log:1`，13 个文件均为 0644、UID/GID 0/0，末行 `NO_SPECIAL_PERMISSION_BITS`。Windows 替身未动态验证 POSIX chown/权限，不宣称已验证生产写后权限。
- 失败边界：部分替换失败会保留完整备份和已写入文件，支持重跑，并非自动回滚（S:43–62）。fsync 覆盖临时目标文件，未提供主机掉电后的完整事务保证；本报告不作该承诺。
- 测试真实性：`output/batch-annotation-preview/reviewer-static-newline-test.py:39` 仅将 ROOT/TARGET AST 常量替换为本地临时目录，Windows 的 chown 用记录调用替身；其余脚本逻辑原样执行。成功、拒绝及中断路径见该文件第 69、83、103 行。测试工具初次运行因 Windows 路径分隔符比较错误失败，修正测试键为 POSIX 相对路径后通过，未修改被审脚本。

## 编译与测试原始输出

命令：`python output/batch-annotation-preview/reviewer-static-newline-test.py`；退出码 0。编译由测试第 13 行直接 `compile` 固定脚本，未执行任何生产路径。

```text
COMPILE PASS; SHA256 matched; assertions_enabled=True
PASS success: 13 replacements, 13 exact backups, index/other assets unchanged, idempotent rerun
PASS rejected without target writes: semantic_difference
PASS rejected without target writes: extra_collision
PASS rejected without target writes: missing_svg
PASS rejected without target writes: source_hash
PASS rejected without target writes: manifest_hash
PASS rejected without target writes: wrong_version
PASS rejected without target writes: incomplete_backup
PASS rejected without target writes: unknown_temp
PASS injected mid-replacement failure: verified complete backups; resumed successfully
ALL LOCAL SURROGATE TESTS PASSED; POSIX ownership and mode not dynamically verified on Windows
```

本 reviewer 未部署、未 commit、未登记 review-approve、未写 `.needs-review`。
