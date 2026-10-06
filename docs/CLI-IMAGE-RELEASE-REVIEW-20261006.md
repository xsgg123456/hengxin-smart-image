# CLI 单图多轮修改发布增量审查

日期：2026-10-06。candidateId：`7b8b90cbb0da8c770d1c20681d89c8316166509b8a64b2e5cb6290b62405db88`。

**Stage 1：PASS。Stage 2：PASS。** 本结论批准发布代码增量，不代表尚未执行的生产发布已经验收。

范围：相对已批准 `4fca61a4301e3381b08db8ba117adedeb1c86b3bcaee1d0ba1a27cb3cb6be062` 的 9 个受控文件：前端 package.json、四个 api-edit 发布/打包脚本与四个测试文件。review-status 确认业务代码无新增差异，功能审查沿用 `CLI-IMAGE-CONVERSATION-REVIEW-CLOSURE-20261006.md` 两阶段 PASS。依据用户新增提交/打包/部署授权及 `CLI-IMAGE-RELEASE-20261006.md`，继续 code-review 闭环。仅审查、测试及写报告，没有提交、生产操作或登记批准。

## Stage 1：发布要求

| 要求 | 结论与证据 |
|---|---|
| 固定本次版本与基线，拒绝误部署 | 完整实现。scripts/release/api-edit-deploy.py:36–42 校验 release、0023 和 0.2.17；api-edit-runtime.py:51–60 校验当前完整 compose 链、五服务镜像0784c97及运行配置；deploy.py:66–68 校验安装测试镜像 ID、旧 schema0022、未暂停且无在途。错误 schema 的本地测试通过。 |
| 关闭接纳、排空，不强停未知执行 | 完整实现。api-edit-deploy.py:73–80 停 web/API/outbox、暂停 API 通道、排空 API/native，复查 pending 后停 variants；image-inputs-worker.py:52–74 核实消费者/active/reserved/scheduled 与数据库；未知排空进入 deploy.py:114–122 关闭入口且不重启执行者。本地故障用例通过。 |
| 备份成功后才迁移0023 | 完整实现。api-edit-runtime.py:74–94 dump并用pg_restore --list校验、备份native/前端/compose/nginx，最后写COMPLETE；api-edit-deploy.py:81–84 在备份返回后用新镜像 migrate、断言0023。备份失败不迁移测试通过。 |
| 回退保持会话数据，恢复代码与配置 | 完整实现。backend/migrations/versions/0023_api_cli_conversations.py:12 仅新增三表，:17 降级不删数据；api-edit-deploy.py:123–154 恢复native/前端/配置、旧compose服务，保留schema。partial front/安装失败测试验证恢复旧代码并保留0023。 |
| 接纳重开后失败不能切回旧执行器 | 完整实现。api-edit-deploy.py:99、106–113 保留新代码并关入口；回退本身失败由:155–162 关入口。对应两类故障用例通过。 |
| native和五容器同步，依赖及既有资源限制不漂移 | 完整实现。api-edit-runtime.py:64–70 override只改image/build，拒绝pyproject/uv.lock漂移；:97–110 同步全部app Python及三固定提示词、权限/属主；deploy.py:87–94 验证native/依赖后启动新容器。11层overlay保留与native资源用例通过。 |
| 白名单包与隐私检查 | 完整实现。package-api-edit.py:15–35 仅后台代码/测试/迁移、固定资源、四发布脚本及两Nginx配置；:74–110 要求已提交、批准快照，归一并核对commit/本地字节，扫描源码及静态资产，排除demo-images；:39–51 防穿越并逐字节核验归档。隐私/压缩/归档测试通过。 |
| 安装镜像隔离测试及固定镜像身份 | 完整实现。api-edit-deploy.py:57–66 镜像内pytest使用--network none，不传生产连接，记录实际image ID；:14–22 仅排除依赖仓库前端/infra的测试。Dockerfile.backend:6–8 锁依赖并复制白名单backend。此处验证脚本行为，真实安装镜像测试尚待发布阶段执行。 |
| SSE配置随包发布，保留挂载inode，失败恢复 | 完整实现。package-api-edit.py:16、122 两配置必需；api-edit-runtime.py:115–116 在web停止期间copyfile到原路径，保留已有文件inode；deploy.py:137–140 恢复同一路径配置，:100–101 开web并reload；api-edit-verify.py:64–65 校验两文件哈希。部分前端发布故障测试确实修改并恢复nginx.vps.conf、删除原不存在的media配置。 |
| 发布后健康、内容哈希、鉴权、只读会话/SSE冒烟 | 工具实现完整，实际部署验收待执行。api-edit-verify.py:49–83 检查五镜像/backend字节/native/前端/Nginx/schema/配置；:86–99 验证ready、公网HTML/入口资产及匿名401。会话/SSE真实生产只读冒烟由发布计划后续执行，不把本地mock视为该证据。 |

未实现、部分实现、Spec 漂移：发布代码范围未发现。未新增UI布局；前端只改版本号（hengxin-smart-image/frontend/package.json:3），视觉结论沿用已批准功能快照。

## Stage 2：质量、安全与测试真实性

- **结构**：四脚本分别167/133/104/135行，均低于300行；编排、运行环境、发布后校验、打包职责分离。证据：scripts/release/api-edit-deploy.py:24，api-edit-runtime.py:48，api-edit-verify.py:29，package-api-edit.py:74。
- **安全**：子进程使用参数列表；固定release正则限制路径，部署umask0077、备份目录0700；敏感compose完整配置只保存private文件，没有打印环境值（deploy.py:34–36；runtime.py:20、61、75）。打包拒绝符号链接与敏感内容，静态gzip先解压再扫描（package-api-edit.py:55–71、87）；没有本次新增密钥、eval、shell=True或不受控SQL输入。
- **故障恢复**：静态逐支核对，独立用例覆盖备份失败、安装失败、部分前端/Nginx更新、排空未知、回退失败和重开后失败。迁移为事务内加表，无旧列破坏；回退不清空新表（0023_api_cli_conversations.py:12–18）。
- **测试边界**：本地发布测试使用临时目录和mock docker/systemctl/SQL，不等于真实生产迁移演练。Nginx hash校验分支已静态审查；这轮未运行生产校验。主线程提供真实环境只读基线，本 reviewer 未复连生产。上线阶段仍须运行安装镜像测试和计划中的实际核验，失败按脚本关闭入口。
- **依赖审计信息**：主线程报告 critical0/high70/moderate48/low5；本delta只更新package版本号，无依赖/锁文件更新，不宣称这些存量项已修复。本次审查没有将该统计当作可忽略证据，也没有把本次变更定性为新增这些漏洞。
- **业务回归补充**：主线程在功能冻结后完成独立PG全backend：1457 passed、125 skipped、15 warnings、162.98s。属于主线程证据；本 reviewer 上轮独立37专项与compileall结果详见闭合报告，未复跑全量。

本次增量未发现 HIGH/MEDIUM 阻断问题。

## 独立执行结果

命令：`python -m unittest discover -s scripts/release -p test_api_edit*.py -v` 与 `python -m unittest discover -s scripts/release -p test_package_api_edit.py -v`。所有25个测试通过；原始汇总：

```text
----------------------------------------------------------------------
Ran 20 tests in 0.348s

OK
----------------------------------------------------------------------
Ran 5 tests in 0.005s

OK
```

测试输出包含预期恢复标记：

```text
ROLLED_BACK_CODE_AND_CONFIG_SCHEMA_RETAINED
BUILD_AND_INSTALL_TESTS_PASS
POST_OPEN_FAILURE_NEW_CODE_RETAINED_INTAKE_CLOSED
ROLLBACK_BLOCKED_INTAKE_CLOSED backup=<临时测试目录>
DRAIN_UNCERTAIN_NO_WORKER_RESTART_CHECK_INTAKE
```

上段backup路径已明确简写，非真实生产路径；这些标记来自mock测试，不是生产部署状态。

编译命令：`python -m compileall -q scripts/release/api-edit-deploy.py scripts/release/api-edit-runtime.py scripts/release/api-edit-verify.py scripts/release/package-api-edit.py`。原始stdout为空，exit_code=0。主线程正式前端build31.85s PASS为补充记录，本轮没有重复构建。

## 快照交接

开始review-status：currentId为7b8b90cbb0da8c770d1c20681d89c8316166509b8a64b2e5cb6290b62405db88，reviewedId为4fca61a4301e3381b08db8ba117adedeb1c86b3bcaee1d0ba1a27cb3cb6be062，差异仅上述9文件。允许主Agent在核对一致后登记本candidate的Stage1/Stage2 PASS，再按授权提交及执行发布；实际发布结果另行记录。
结束校验：报告写入后currentId仍为7b8b90cbb0da8c770d1c20681d89c8316166509b8a64b2e5cb6290b62405db88，审查期间代码快照无变化。
