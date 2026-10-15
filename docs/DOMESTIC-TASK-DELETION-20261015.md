# 国内 API 换套图执行提示与真实删除

状态：已完成开发、独立两阶段审查、Git提交、打包与生产部署；0.2.37于2026-10-15 16:31（北京时间）恢复服务并通过上线验收。

## 产品合同

- 换图记录及详情图片卡片分别显示 CLI「等待修改」「图片修改中」；执行结束后消失，原 API 状态、统计及筛选保持原义。
- 仅空闲任务可删除。API、CLI 排队、执行、重试、收图、停止中和状态待核实均禁止删除；候选结果或待答复会话必须先确认进程退出。
- 既有确认框展示任务名及永久删除范围。确认后删除任务、专属原图/素材/结果/版本、CLI 会话与任务私有工作资料；受其他任务引用的共享资料保留。
- 后端再次校验并持久封锁新执行，原生删除服务完成文件、对象与数据库清理后才报告成功。失败保留回执，可重试；不追溯清理以前的软删除任务。
- 不清理共享 Skill、全局认证、运行时或其他任务。生产验收不删除真实任务、不发起付费模型调用。

## 已核实的生产基线

- 前端 0.2.36；国内数据库 0028，海外数据库 overseas_0016。
- 国内五项 API/队列/图片执行服务和身份服务当前镜像均为 `hengxin-smart-image-backend:overseas-20261013-da722ad`；发布只更新国内五项服务。
- 国内原生 Codex Worker 使用 codex 用户；工作目录来自独立 native release，保留既有环境文件与 Codex 模型配置。
- 当前没有专用删除服务；此次新增原生服务只处理明确提交的删除回执，不启用自动历史保留期清理。
- 发布必须保留完整 Compose 配置链、海外上传限额与国内/海外/身份三组镜像台账。

## 验证与发布次序

1. 后端单元、故障和真实 PostgreSQL 并发测试，Linux 路径/符号链接测试。
2. 前端完整测试、类型与构建、隔离浏览器交互及视觉验证。
3. 国内发布脚本隔离测试、依赖与产物隐私审计、独立两阶段审查。
4. 按批准快照提交中文 Git commit，构建版本 0.2.37 安装包；从包内执行实际镜像测试。
5. 国内入口临时停止接纳请求，等待在途执行排空，备份并验证恢复，迁移 0029，切换国内服务及前端。
6. 健康、安装哈希、原生服务、正式页面与未受影响服务核验；成功后登记镜像台账。未知状态不强制停止任务。

## 实测结果

- 前端首轮完整测试367项通过，类型检查及生产构建通过；修复真实DTO合同后的最终结果为下述368项通过。
- 隔离浏览器 `scripts/api-activity/browser.mjs`：报告 `output/playwright/api-activity/report.json` 无错误。覆盖关闭详情后列表继续轮询、重开详情与正式 V1 保留、390px 标签边界、确认取消、受理不冒充成功、失败重试、刷新恢复及完成后移除。截图已目视检查窄屏状态标签。
- Linux 后端首轮 2446 通过、187 跳过、17 失败。9 项旧删除契约需随需求更新；其余 8 项为测试容器缺少 `--init`，测试进程成为 PID 1，旧进程管理器按孤儿保护逻辑取消执行。已定位原因，最终复验使用 `--init`，不放宽进程保护。
- 最终全套、审查快照与提交结果见下文；服务器安装测试及生产验收单独记录。
- 真实 PostgreSQL 现有 API 执行回归 2 项通过；删除竞争专项 5 项通过。Linux 新删除专项 52 项通过，包含真实 uid1000 无权删除、uid1001 可删除和执行进程退出核验。
- 依赖审计：critical 0、high 70、moderate 48、low 5，与既有基线一致；本次未修改依赖版本。包预检（去除非运行必需的打包工具后）1336 个文件通过隐私检查，仅保留既有2处精确合成负例豁免。
- 独立首轮审查发现两项阻断：真实删除 DTO 的 `message: null` 与前端校验契约不符；新打包白名单包含隐私检查器自身导致预检失败。修复与复审通过前不提交或部署。
- 冻结后端完整 Linux 回归：`docker run --rm --init ... /app/.venv/bin/python -m pytest -q -p no:cacheprovider --tb=short --junitxml=/reports/domestic-backend-final.xml`，2515 通过、195 跳过、0 失败（313.30s）。原始结果 `output/domestic-backend-final.xml`。
- 打包修复保留本地 helpers 必须已提交的检查，仅从服务器运行包移除这些非运行文件，没有放宽隐私规则。新增真实选中文件源码扫描回归；国内发布专项 21 项通过。完整发布回归 493 通过、1 跳过、189 子测试通过，仍有1项既有 `test_release_native.py::test_frontend_manifest_matches_seven_native_files` 失败：旧测试期望20260924 annotation为最后overlay，而原脚本已有后续materials overlay。相关三份历史脚本均与HEAD一致，本次未改，不作为新国内发布入口的通过声明。原始结果 `output/domestic-release-tests.xml`。
- 前端合同修复后最终验证：完整测试368通过/0失败；typecheck exit0；0.2.37生产构建exit0（34.20s）。`ApiDeletion.message` 明确为必填 `string | null`，缺失/非法字段仍拒绝。浏览器完整DTO复验lists=10、deletes=2、errors=[]；DELETE 202、GET处理中、失败、重试与最终完成均使用真实完整消息字段；非法完成回执不会移除任务，合法deleted/null才出现成功提示。原始日志为 `output/api-ui-{tests,typecheck,build,browser}.log`，报告记录全部回执。
- 首轮两项HIGH已修复，重新固定候选 `899a00b62e7b111b3a033b7599fc30f910608fc137c4c796f88f6a09e090c378`；最终独立审查 Stage 1/Stage 2 均 PASS，报告 `docs/reviews/DOMESTIC-TASK-DELETION-20261015-FINAL.md`。复审独立后端专项55通过、国内发布21通过、前端客户端与轮询5通过、类型检查通过，隔离浏览器lists=11/deletes=2/errors=[]，同组件空闲邻居与活动渲染、窄屏、删除失败及完成截图已目视核对。此前失败报告仅保留审查轨迹，不作为批准依据。

## 发布记录

最终上线包：`domestic-20261015-4c64c1a`；功能提交 `217926d`、发布等待修复提交 `4c64c1aa59e37498662b7cbb3b90a704146ce038`。归档1337文件、5,654,494字节，SHA256 `5127996e079f0752ace9abcc08ecc46f3b89d271575ab421df8da36e9dcf1082`，隐私/归档校验PASS。增量审查报告 `docs/reviews/DOMESTIC-PROXY-WAIT-20261015.md` 两阶段PASS，最终受控快照 `5396e6962780aecacb48f0f5ba24f4cdbd8eeda9cf1bf286eabdbbf142b29164` 与批准一致。

- 新旧包实际源码逐文件核对，只有服务器运行的domestic-gate.py改变；全部backend、frontend、infra及dockerignore一致。在统一retention锁内复核619个镜像文件、安装日志SHA、旧ImageID，再新增tag、记录复用与pending保护。最终镜像仍为 `sha256:6b65ffa999af5ed1740ea066733256e2d141587af4b3a153e7b6d1fd0bdcac12`，复用同镜像2407通过/194条件跳过/1排除的安装结果；没有伪称重新执行。
- 国内关流、两阶段稳定排空成功，durable/variants/Celery/队列优先级/unacked均为空；随后完整备份并在隔离PostgreSQL恢复，逐表全行哈希一致。备份位置 `/opt/hengxin-backups/domestic-20261015-4c64c1a`，保留COMPLETE及迁移前后指纹。
- 国内迁移0028→0029仅新增空api_task_deletions表，既有业务行哈希不变；海外仍overseas_0016。国内五项服务、原生Codex worker健康，新增删除服务以codex用户运行，retention关闭，实际schema只读扫描及两轮成功空循环通过。
- 内外入口国内/海外/身份健康、正式前端入口与包一致；channel已恢复未暂停；海外及身份容器ID、其他原生目录不变。发布返回DEPLOY_COMPLETE，VERIFIED与台账completed齐全，当前包无pending/RECOVERY_REQUIRED。
- 生产列表65条、详情3张当前V1成品、永久删除具名确认框实际打开并目视核对，取消后任务仍在。截图 `output/playwright/domestic-production/list.jpg`、`detail.jpg`、`delete-confirm.jpg`。没有确认删除、没有付费生成；验收时删除回执0。活动标签及真正清理/失败重试通过隔离浏览器、真实PG与文件权限测试验证，没有伪称在生产制造活动或删除数据。
- 本地证据 `output/release/domestic-20261015-4c64c1a/POST_DEPLOY_SUMMARY.json`、`INSTALL_TEST_REUSE.json`、`package-audit.json`；服务器同发布目录保留prepare/deploy日志、排空、备份、服务就绪及镜像复用凭据。临时PG测试容器和预览服务已关闭，验收临时浏览器页已关闭。

发布证据：代码提交 `217926d`；包 `domestic-20261015-217926d`，版本0.2.37，1337文件，5,654,341字节，SHA256 `5ccbd5b4336a84a3a8a92057809399e8b64fee36ce5d56bcb0645cb75c511b93`。正式包隐私及归档内容复核PASS，已上传正确生产主机并校验相同SHA，随后验证全部归档成员是无路径穿越的普通文件再解包。最终报告收尾引用更新后已重新登记同一代码快照批准，提交内报告与冻结文件一致。

服务器镜像安装测试2407通过、194条件跳过、1排除，619份后端源码哈希一致。首次发布在close-intake阶段因Nginx异步reload首次请求仍命中旧worker而中止，未停止API或执行器、未备份/迁移/发布。随后核实完整拓扑、schema0028、channel未暂停，双层关流实际已生效；恢复原代理文件并轮询两入口200，完整拓扑与原值相同，保存RECOVERED_PRE_SWITCH。补充发布门禁：开关流均使用统一30秒期限，关流轮询两路径×三个入口503，开流轮询三个入口健康200；每个请求受剩余期限约束，必须同轮全部达到预期才继续，持续旧状态或网络异常不放行。新增异步切换/网络失败/超时回归后国内发布专项25项通过。Nginx异步换worker行为参见官方文档 https://nginx.org/en/docs/control.html 。

## 失败恢复操作边界

仅发布脚本修复、镜像输入不变时，可复用已测试的同一不可变ImageID：新旧包全部backend清单、Dockerfile、dockerignore及前端/infra必须逐文件一致；核验原安装日志、原INSTALL_TEST_IMAGE_ID和实际镜像ID；在统一retention锁内给同一ID打新tag、再次inspect、记录来源与日志SHA并登记新pending保护后才能prepare。不得把复用说成重新执行测试，任何输入不同均重新构建与安装验证。

本次入口支持 `build / prepare / deploy`，没有自动 `recover`。失败后不会自动回灌数据库、停止未知任务或宣称恢复成功。以下为服务器上由操作者按实际状态执行的步骤，不是已执行的恢复记录。

先从已验证安装目录进入 Python，加载本次工具和持久证据（将 `REL` 设为本次真实发布名）：

```bash
export REL=domestic-20261015-实际提交前七位
cd /opt/hengxin-releases/$REL/src/scripts/release
python3 -i -c 'import importlib.util,json,os; from pathlib import Path; s=importlib.util.spec_from_file_location("release","domestic-deploy.py"); d=importlib.util.module_from_spec(s); s.loader.exec_module(d); work=Path("/opt/hengxin-releases")/os.environ["REL"]; data=json.loads((work/"topology.json").read_text()); print(json.loads((work/"RECOVERY_REQUIRED.json").read_text()))'
```

1. 执行 `d.gate.close(work)`；必须实际验证两层 `/api/v1/` 普通接口与事件入口均为 503。检查 `RECOVERY_REQUIRED.json` 的 phase、`EXECUTORS_STOPPED`、`PREPARED` 和备份 `COMPLETE`。不输出环境文件或私密配置内容。
2. 读取 `d.r.pending()`、数据库 schema、删除回执数及 `systemctl` 状态。执行器仍在运行时用 `d.drain.evidence(work, 45)` 取得 durable/Celery/broker/unacked 证据。执行器已停止则不能把探测失败解释成零任务；依据已有排空回执并直接复查 durable/broker，恢复有疑问时优先修复当前版本。
3. 如果 phase 为 `open-intake` 或无法证明入口从未开放，按可能接纳过新任务处理。保留新版本及 0029 删除保护，先排空并向前修复，不直接切回不识别删除回执的旧代码。回执表存在且非空也禁止回退旧应用。
4. 只有开流前、无活动任务/队列/回执，且备份完整时才可恢复旧应用。使用保存的 `data['domestic']` 原 Compose 链执行 `d.m.compose(data['domestic'], 'up', '-d', '--no-deps', '--wait', *d.r.SERVICES)`；不得重新猜测或缩短 overlay 链。原生执行器须先证明空闲再停止，仅移走本次 `99-domestic-release.conf`（保留90/95），`systemctl daemon-reload` 后启动旧原生服务。删除服务同样先证明空闲才停止/禁用，保留源码和回执表。
5. 如已替换前端，备份文件位于 `/opt/hengxin-backups/$REL/host/opt/hengxin-smart-image/`，仅恢复其中 `frontend/package.json`、`frontend/dist/index.html` 及原有 `index.html.gz`。静态 assets 保留，不删除共享目录。数据库保留 0029，不运行 downgrade、不删除回执表、不向生产恢复 dump。
6. 旧应用健康、原生及API worker核验、旧前端入口哈希、身份/海外容器及原生工作目录均通过后，恢复原 channel 值，再执行 `d.gate.open_intake(work)`。重新验证公网与本机三域入口和前端；失败继续关流。发布成功标记和镜像台账不能伪造；保留 pending 与候选镜像保护，真实恢复结果另行登记。

若只在 `build/prepare` 失败且尚未关流，不做上述服务回退；先核对原服务仍健康，修复失败阶段后再处理候选目录。对已存在 `PREPARED` 或部署 pending 的目录不得盲目重放发布。
