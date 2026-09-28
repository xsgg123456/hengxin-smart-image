# 前端清理发布增量独立审查

- candidateId：`90fbb673eebe3c41d4830652fe84dfaf3d7dfbf6b36bc12cf434b5909f9d6bc5`
- 范围：`frontend/package.json` 版本、`scripts/release/frontend-static.py`、`scripts/release/test_frontend_static.py`。下述脚本路径相对仓库根目录，frontend 路径相对 hengxin-smart-image。
- 依据：`DEV-PLAN.md:3-7`、`hengxin-smart-image/docs/FRONTEND-CLEANUP-RELEASE-20260928.md:5-16`。业务清理已在 `7b41062` 审查，本轮不重复业务/UI审查，不连接生产。
- 结论：**Stage 1 PASS；Stage 2 PASS**。这是发布增量代码的审查通过，不代表生产安装、线上健康或页面验收已通过。

## Stage 1：Spec Compliance — PASS

| 要求 | 结论与证据 |
| --- | --- |
| 前端 0.2.11 → 0.2.12 | 完整实现。`frontend/package.json:3`；`frontend-static.py:39-41,71-73` 固定产物版本并验证生产基线。Git diff 只有版本字段变动。 |
| 只发布前端，不重启后端/执行服务、不迁移数据库 | 完整实现。`frontend-static.py:25-43` 归档只收 dist、前端 package、部署脚本与清单；`:68-120` 只写前端目录、FRONTEND_RELEASE 和备份。无服务/数据库执行命令；`test_frontend_static.py:37-43` 验证 API_RELEASE 不变。 |
| 已提交且已审代码门禁、隐私与归档校验 | 完整实现。`frontend-static.py:20-21,33-37,49-50` 检查提交、批准快照及源码字节；`package-delivery.py:65-71` 拒绝未批准快照。`:26-32,40-43` 调用资产扫描及归档回读；`package-text.py:38-79` 实现扩展名/敏感内容扫描和归档字节比对。独立执行 483 资产扫描和归档回读通过。 |
| 校验哈希后发布，拒绝同名不同内容资源，保留旧资源 | 完整实现。`frontend-static.py:54-58,69-80,92-98,112` 实现源/安装哈希和碰撞拒绝；不会删除旧哈希资源。`test_frontend_static.py:37-55` 覆盖成功、损坏包和资源碰撞。 |
| 备份入口和元数据，资源先落盘，原子替换入口 | 完整实现。`frontend-static.py:81-90` 备份并逐文件校验；`:61-65,92-111` 先落资源后用 os.replace 替换入口及元数据。原子性是单文件替换，HTML/gzip/package 并非一个文件系统事务；新旧哈希资源同时保留。 |
| 失败恢复入口、package 和发布元数据，不恢复数据库 | 完整实现。`frontend-static.py:113-119` 恢复存在项并删除原来不存在项；`test_frontend_static.py:57-69` 注入切换后的安装校验失败，验证 HTML/gzip/package 恢复及新发布清单删除。 |
| 发布后线上资源、页面、健康、Skill 核验 | 属于主 Agent 后续部署验收，当前未执行；准备记录 `FRONTEND-CLEANUP-RELEASE-20260928.md:16` 如实标记待完成。不得据本报告宣称生产已验收。 |

部分实现/未实现：本轮代码范围内无。Spec 漂移：未发现新增业务页面、接口或数据结构。UI 一致性、占位引导及邻居页面视觉比较：本增量不修改 UI，适用业务审查见发布记录第 14 行；本轮没有伪称重新执行浏览器验证。

## Stage 2：Code Quality — PASS

- 结构与错误处理：`frontend-static.py:11-120` 分离摘要、打包、校验、原子复制、安装；130 行，测试 73 行，未超过 300 行。安装异常走恢复路径；未发现本轮新增密钥、动态 eval、SQL 拼接或前端暴露凭据。
- 测试真实性：`test_frontend_static.py:15-31` 使用临时目录构造真实旧入口、gzip、资源与版本；`:37-69` 实际调用 deploy，故障注入在入口切换后的 installed verify。独立重跑 4 项通过；这些测试证明本地文件切换行为，不证明生产权限、Nginx 行为或服务健康。
- 安全/操作边界：`frontend-static.py:54-58` 校验清单项，`:75-98` 安装遍历 dist，脚本自身没有拒绝额外未列入清单文件。因此 PASS 适用于本次主 Agent 明确的可信包流程：上传前后归档 SHA 一致、新建空 src 目录、解包前拒绝非 regular file/绝对路径/父目录穿越、使用 data filter，并核对归档成员恰好等于 manifest.files 加 release.json 及其哈希。该流程为主 Agent 承诺的后续步骤，本 reviewer 未连接生产验证；不将脚本描述为可直接接受任意外来目录的通用安装器。
- 构建来源边界：`frontend-static.py:26-32` 读取现有 dist，源码审批本身不覆盖被 Git 忽略的 dist；本次有 0.2.12 构建日志和独立资产审计支撑，打包前后不得另行改写 dist。脚本使用 assert，执行应采用普通 Python，不能使用禁用断言的 `-O`/`PYTHONOPTIMIZE`。
- 既有依赖告警：发布记录第 13 行报告 critical 0/high 33/moderate 30/low 1；本增量未修改依赖，本 reviewer 未重跑网络 audit，也不将这些既有告警计为已解决。

## 验证原始输出

独立命令：`python -m unittest discover -s scripts/release -p test_frontend_static.py -v`

```text
test_corrupt_archive_rejected_before_backup (test_frontend_static.StaticReleaseTests.test_corrupt_archive_rejected_before_backup) ... ok
test_failure_after_switch_restores_old_entry_and_metadata (test_frontend_static.StaticReleaseTests.test_failure_after_switch_restores_old_entry_and_metadata) ... ok
test_install_preserves_backend_and_old_assets (test_frontend_static.StaticReleaseTests.test_install_preserves_backend_and_old_assets) ... ok
test_same_asset_path_changed_rejected (test_frontend_static.StaticReleaseTests.test_same_asset_path_changed_rejected) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.106s

OK
```

独立调用既有 audit_asset/archive_bytes，并对两个新增 Python 文件执行 compile：

```text
assets=483 privacy=PASS archive_roundtrip=PASS
Python compile=PASS
```

读取现有构建日志 `output/frontend-cleanup-build.txt` 的原始首尾输出（本 reviewer 未重复运行前端构建）：

```text
> hengxin-smart-image-frontend@0.2.12 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 31.91s
```

读取 `output/frontend-cleanup-tests.txt` 原始结果（本 reviewer 未重复运行业务测试）：

```text
ℹ tests 197
ℹ suites 0
ℹ pass 197
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3395.4817
```

审查时 review-status 的 currentId 与送审 candidateId 一致，变化文件为上述三个文件。未修改代码；批准凭据由主 Agent 在再次确认快照匹配后登记，不向 .needs-review 写 clean。
