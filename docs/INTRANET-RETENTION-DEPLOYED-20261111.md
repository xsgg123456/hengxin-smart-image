# 内网自动保留两版：安装与清理验收

2026-11-11，用户授权的发布工具更新和存量清理已完成，仅操作 `192.168.1.245`。

- 最终批准快照：`db983d1ec16eb1a0958f5a557c1e62f28a36584070aae43c818dfedfbf444b1e`。完整审查及名称复用增量均两阶段 PASS，见 [完整报告](reviews/INTRANET-RETENTION-FINAL-20261111.md)、[最终增量报告](reviews/INTRANET-RETENTION-NAME-GUARD-20261111.md)。初轮失败项已修复，不使用失败快照交付。
- 内网入口 `/opt/hengxin-intranet-tools/current` 已切换到 `releases/db926bde69b81916`；19 个安装文件逐项 SHA256 验证。此次只更新工具，没有重发应用。
- 后续 full/frontend 发布均在运行验证通过、成功台账保存之后自动清理。失败/未完成发布不清理，清理失败不回退成功业务；`cleanup` 默认预览，`cleanup --apply` 可重试。目录名称不可重复使用，避免新候选被旧历史误识别。
- 实际预览及执行均只选中 `/opt/hengxin-unified-releases/unified-20261111`；执行返回 `status=complete`、`errors=[]`。保留 `lan-20261111-0a1cee0`（当前后端、上一版前后端）与 `lan-20261111-6501351`（当前前端）。没有删除原生依赖目录、镜像、业务数据、上传包或备份。
- 清理前后统一源码根目录实际分配空间：134,033,408 → 97,505,280 字节，释放 36,528,128 字节。新增清理回执占用 4,096 字节，新工具目录占用 237,568 字节，扣除后净释放 **36,286,464 字节，约 34.6 MiB**。本任务未启用的中间工具目录和隔离测试目录均清理，没有为被删版本生成副本；不把测试临时空间回收计入此收益。统计不混入运行中业务数据的磁盘变化。
- 前后比对：17 个容器 ID/启动时间/重启次数/镜像不变；7 个原生服务 PID/启动时间不变；24 个运行配置文件及发布台账摘要不变。最终 `verify` 返回后端 `0a1cee0`、前端 `6501351`、previous=true、pending=null，两侧 `RUNTIME_OK`。当前及上一版清单、原生解释器/依赖、数据容器身份和健康检查均通过既有验证入口核验。

## 验证命令与结果

最终安装候选内，使用真实 Linux worker 解释器执行隔离测试：

```text
PYTHONDONTWRITEBYTECODE=1 <worker-python> -B -m pytest -p no:cacheprovider scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py --basetemp=/var/tmp/hengxin-retention-tests-db926bde69b81916 -q
124 passed, 7 subtests passed in 2.88s
```

本地命令 `hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py -q`：`84 passed, 40 skipped, 7 subtests passed in 13.03s`，40 个 Linux 文件系统及 /proc 用例由上述真实 Linux 运行补齐。16 个工具/测试 Python 文件均经 `compile(..., 'exec')` 编译通过。没有修改业务前端或后端，未重跑收费模型、UI 全量 E2E 或生产回退故障演练。

隔离测试覆盖实际删除与容量核对、前后端目录分离、在用/停用容器、systemd vendor/非 service 单元/路径别名、父目录 bind mount、进程相对参数、危险链接/权限、未发布候选保护、清理失败不回退、部分删除凭据续清及篡改拒绝、历史名称复用阻断。

原始日志与安装/前后基线位于本地 Git 忽略目录 `output/intranet-retention/`；服务器清理回执位于 `/var/lib/hengxin-release/intranet-cleanup.json`。备份和旧依赖不属于本次自动清理范围，已打开页面兼容资源继续按原策略保留。
