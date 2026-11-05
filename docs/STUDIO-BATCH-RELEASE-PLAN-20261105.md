# 海外批量标注与逐图参考材料发布计划

用户已授权正式实现、Git提交与生产部署。本文只规定本轮可验收步骤；发布工具准备期间没有停止或切换任何生产服务。

## 基线与范围

2026-11-05 通过明确IP `root@107.172.161.139`、密钥 `C:/Users/82358/.ssh/codex_vps_20260908_ed25519`、BatchMode与StrictHostKeyChecking只读实查：

- 前端0.2.63；上一发布 `skill-folders-20261103-7c4d1ce`（主Agent先前证据）。目标0.2.64。
- API镜像 `sha256:bd981ca42788da650871879f4effb376062c5090ffefa1b3824387479c4246b5`；数据库 `overseas_0026`，本轮不迁移。
- API实际Compose来源33个；`account-runtime.compose_info(live)`逐个保存路径及校验和，叠加仅含API image的新overlay。不能用仓库配置替代。
- worker/outbox PID分别4160156、4160154，均active，共用 `/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend`。
- 公网ready返回ready，PostgreSQL/Redis/MinIO均up。
- 基线完整代码证据存于Git忽略的 `output/release/studio-batch-baseline-20261105.json`；不包含环境变量明文。

API更新 `app/overseas/studio/{schemas,image_edits,service,queries,image_edit_history}.py` 五模块。native仅更新 `image_edits.py`：执行链路直接调用其 `prompt_edits`，其依赖只有标准库与既有FastAPI。两海外原生单元均验源、排空、重启、校验实际PID与业务环境。保留国内服务、数据库schema、现存Skill publisher容器、Skill目录及其他native源码。

## 有序步骤及完成标准

1. 本地测试、生产构建、两阶段review、中文提交。工作区干净，harness当前快照与批准快照一致；包括候选包在内全部从干净固定commit生成，正式包要求review批准。
2. 新打包器 `studio-batch-package.py` 校验源码与commit、allowlist、基线、原生模块、递归测试依赖、产物隐私与全部文件SHA256。前端从固定commit导出到全新隔离目录，按提交的锁文件安装依赖并执行生产build；不读取工作区旧dist，构建失败不出包。完成标准：`package-audit.json` PASS，release.json明确0.2.64/0026、commit、candidateId、API/native hash及构建来源；无个人数据、配置密钥、预览入口。
3. `prepare` 只构建候选镜像并记录生产资源保护快照；`test` 从该镜像实际 `/app` 路径、镜像默认身份执行全部指定测试，测试挂载只读，独立网络/独立临时PostgreSQL；无生产配置注入。必须有passed且无failed/skipped。完成标准：`INSTALL_TESTS_PASSED`绑定manifest和image。
4. `gate` 先查在途任务和草稿导入，再优雅停API、重查排空、暂停consumer，再以禁SIGKILL且统一60秒期限停止outbox和worker。超时保留保护，不强杀。`backup`导出0026数据库至私有目录并在独立PostgreSQL恢复，逐表记录/全schema一致；完成标准：`backup/COMPLETE`及`restore-proof.json`。
5. `native` 仅在两单元停止且备份验真后创建原始源码备份、原子替换指定文件，以hengxin-overseas真实身份从实际安装路径编译并执行自定义参考图/旧payload提示词绑定探针，重启与核验两单元。完成标准：`NATIVE_INSTALLED`、`NATIVE_VERIFIED`，实际服务UID999、cwd/环境和其他源码不变。
6. `api`要求native验收和原API停止，继承33份Compose，仅切API image；随即调用 `skill-folders-gateway.refresh` 对固定web容器nginx测试/重载，避免上游旧DNS导致502。`frontend`部署保留哈希资源；`resume`核对公网入口HTML及JS/CSS实际字节。完成标准：API/native就绪，国内ready不变，业务环境/Skill/其他容器不变，`RESUMED`。
7. 主Agent浏览器从正式入口验证批量标注/单图、逐图参考用途、返回卡片与已存在历史，检查1920/1440/390截图。不得为验收触发收费生成。完成标准：生产视觉与交互证据；脚本完成不替代浏览器验收。

## 可执行命令

仓库根PowerShell（构建和审核提交完成以后）：

```powershell
python -m unittest discover -s scripts/release -p 'test_studio_batch*.py' -v
python .codex/hooks/harness.py review-status
python scripts/release/studio-batch-package.py --baseline output/release/studio-batch-baseline-20261105.json
```

包位于 `output/release/studio-batch-20261105-<commit7>/release.tar.gz`。使用该真实commit替换下面值。发布到明确IP，不用本机SSH配置中指向另一台机器的别名。

```powershell
$release = 'studio-batch-20261105-<commit7>'
scp -i C:/Users/82358/.ssh/codex_vps_20260908_ed25519 -oBatchMode=yes -oStrictHostKeyChecking=yes "output/release/$release/release.tar.gz" "root@107.172.161.139:/tmp/$release.tar.gz"
ssh -i C:/Users/82358/.ssh/codex_vps_20260908_ed25519 -oBatchMode=yes -oStrictHostKeyChecking=yes root@107.172.161.139
```

SSH内执行，先比对本地package-audit与远程tar SHA256；目标source/work必须是本轮全新目录。source父目录和测试目录须可供镜像UID10001遍历；work及备份保持root私有。分别逐条执行，失败即停，不能用忽略错误的循环继续发布。

```sh
release=studio-batch-20261105-<commit7>
sha256sum /tmp/$release.tar.gz
umask 022
mkdir /opt/hengxin-studio-batch-$release
source_dir=/opt/hengxin-studio-batch-$release/source
work=/opt/hengxin-studio-batch-$release/work
mkdir -m 755 "$source_dir"
tar -xzf /tmp/$release.tar.gz -C "$source_dir"
mkdir -m 700 "$work"
runner=$source_dir/scripts/release/studio-batch-deploy.py
python3 -B "$runner" prepare --source "$source_dir" --work "$work"
python3 -B "$runner" test --work "$work"
python3 -B "$runner" gate --work "$work"
python3 -B "$runner" backup --work "$work"
python3 -B "$runner" native --work "$work"
python3 -B "$runner" api --work "$work"
python3 -B "$runner" frontend --work "$work"
python3 -B "$runner" resume --work "$work"
```

不得修改source中的包内容来绕过校验；每次修订必须重新review/commit/打包并用新目录。候选包模式只准prepare/test，gate与恢复动作会拒绝；正式部署使用默认release模式。

## 恢复

- `API_SWITCH_STARTED`不存在：`python3 -B "$runner" recover-before-switch --work "$work"`。
- 已开始API切换：`python3 -B "$runner" rollback --work "$work"`。重新停止接纳并排空；停止两native单元、恢复原始源码并实际重启校验，再恢复旧API镜像和HTML，刷新网关。数据库不回灌、不降级，Skill publisher不停止。
- 原生文件替换中断：保留 `native-backup.json`。若同名 `.studio-batch-new` 留存，先比对其哈希与本轮manifest，检查磁盘/权限故障；确认后仅处理此已识别临时文件，再执行 `repair-native`。不覆盖原始备份。若native停机仍在进行，保留no-SIGKILL保护并等待真实inactive；不能强杀或撤销保护。
- 恢复按固定node、实际PID/pool/队列识别consumer正在消费或已暂停，分别检查排空；覆盖pause已成功但gate文件未写、outbox已停而worker尚存等中间状态。先确认两native没有pending stop job，再恢复consumer/native，最后开放API；pending stop保留保护且不重启API。
- 回滚native前持久化manifest绑定的恢复阶段、实际PID和目标源码hash。停止阶段仅接受记录PID或0及未变源码；原文件恢复阶段仅接受两PID均0和目标原/新hash；恢复先复制到同一原生文件系统、app树外的专用临时文件，校验hash并保留uid/gid/mode、fsync后原子替换，半写或替换前中断不污染实际源码，其余单元配置、源码、PID始终保留检查。重复停止只复用字节完全相同的no-SIGKILL保护，总期限仍为60秒；中断后可从真实state/guard重新进入。原源码及旧阶段凭据处理完成后才退出恢复阶段并启动native。
- 任何新入队竞态须先安全恢复当前native/consumer，再恢复当前API并刷新网关，待持久化任务完成后重新评估，禁止强行切版本；native替换未完成时保留保护。

## 验证记录

修复R1/R2/R3后本轮本地发布回归40项通过；复用数据库备份/恢复4项、native保护/基线22项、网关刷新10项重新执行通过，合计76项。新增回归真实调用worker CLI及其identify/idle逻辑，覆盖consumer已暂停但gate文件未写、native停止前失败、outbox已停而worker仍暂停、pending job拒绝开放API、入队竞态先恢复consumer。恢复五故障注入经真实sku.state/guard、真实停止/恢复/启动重入成功：outbox已停worker尚存、旧字节已复制而旧安装凭据尚在、凭据只退场一部分、临时文件半写、原子替换前中断；异常PID/无关源码仍拒绝，并验证停止超时保留保护。构建测试覆盖旧dist不读取、真实隔离子进程生成产物、构建失败不回退、构建源码/产物篡改拒绝及来源commit校验；测试中pnpm命令传输使用替身，不冒充真实生产构建。全部15个本轮Python文件语法编译通过，每文件最多225行，git diff --check通过。

隔离构建每一步保留本地 `output/release/studio-batch-build-<随机ID>.log`；正式包目录另附 `frontend-build.log`，审计文件记录日志SHA256和固定commit、frontend tree、锁文件及全部前端产物SHA256。构建环境仅保留工具所需系统路径，清除VITE等外部覆盖，按package.json锁定Node/pnpm版本。

真实旧HEAD隔离安装与生产构建已运行，Vite构建40.43秒完成并通过资产审计；退出清理曾遇Windows深层依赖路径超过MAX_PATH。已加入验证根目录后的扩展路径清理和有界重试，以真实超过260字符路径及暂时占用用例验证，并清理该次残留。日志：`output/release/studio-batch-build-01b7f86ab9844cb595855d52e0eb6e38.log`。本次不据此声称0.2.64正式包已构建；正式提交后打包会再次执行完整构建。

生产安装/切换结果由主Agent追加；此文不将尚未执行的生产部署、实际回滚演练或镜像安装测试标记为通过。
