# 国内 API 简化整改生产发布

用户于 2026-10-20 明确授权 Git 提交、打包和生产部署。产品实现与验收以 `API-RETRY-SIMPLIFICATION-20261020.md` 和 `API-RETRY-SIMPLIFICATION-VALIDATION-20261020.md` 为准；本发布不增加产品整改范围。

## 发布规划与完成标准

1. 只读核查真实生产拓扑、版本、在途工作和发布工具；完成标准是确认国内当前0031/前端0.2.44及实际配置，无凭据输出。
2. 发布版本升为0.2.45，沿用既有打包隐私白名单及发布保护，补充本轮版本入口；完成标准是原schema与API历史记录不变，仅更新国内api、api-image-worker、api-image-outbox和共用前端。海外、身份、原生CLI及其它服务不重启。
3. 发布工具测试、正式构建、依赖审计和独立快照审查后提交中文Git；完成标准是提交内容与审查凭据匹配，打包时工作区干净。
4. 打包、隐私审计、传输并核验归档；在服务器从实际镜像完成安装测试及源码哈希验证，再固定发布拓扑。完成标准是版本、镜像、归档与提交对应。
5. 关闭接纳、排空、温和停止、完整备份并隔离恢复验证、切换服务和前端、恢复接纳；完成标准是新服务健康、旧API数据及无关服务保持、正式入口视觉及只读功能验收通过。不主动提交收费生图。
6. 记录生产证据和提交号；完成标准是发布台账成功、备份可定位、仓库发布记录更新。

## 运行边界

数据库维持0031，不新增迁移，不删除历史审计字段，不顺带修改CLI核实和删除协议。历史 bounded-v2 轮次属于正常存量，发布不得要求将其删除或清零。不强杀或恢复旧库覆盖业务。

生产只读实查确认旧版存在4个已超期约两小时的 uncertain 图片，原尝试已结束；另有正常排队/重试/执行中的工作。旧“所有图片都必须终态”门槛无法结束，因此本轮按已验证持久化恢复能力交接：关闭HTTP接纳、暂停通道、停止API outbox；等待真正运行的网络/收图调用、Celery active/reserved/scheduled、broker/unacked 连续两轮为空；拒绝有效租约、running 尝试、不明状态、CLI活动与旧通道占用。仅允许没有执行权的持久排队/等待/有回执收图记录，以及租约失效且原尝试已结束的旧uncertain。保留所有原字段，不通过修改业务状态实现“排空”。

停执行器后完整备份、隔离恢复并核对全部API行指纹；启动新API/worker时outbox保持停止且broker为空，再验证schema/字段/行/轮次保持。之后才启动新outbox，由已验收的新代码恢复持久任务；此后正常恢复引起的状态变化不误判为迁移改写。成功图片和历史完成审计继续受保护。遇到不能证明安全续接的工作仍失败关闭，保持现场。

当前状态：2026-10-20 18:16（北京时间）生产切换完成，正式入口验收通过。

## 发布前实查与本地证据

- 实际生产前端0.2.44、国内0031、通道未暂停；国内API/worker/outbox均为上一版固定镜像。存在97个 bounded-v2 历史/当前轮次，4个旧uncertain的租约已超期、无running尝试，CLI活动为0。证据仅保存在忽略的 `output/api-retry-simple-release-20261020/production-baseline.json`、`active-baseline.json`。
- 0.2.45正式前端类型检查及构建通过，Vite 33.70秒，日志 `frontend-build.log`。
- 依赖审计为critical 0、high 70、moderate 48、low 5。按既有锁文件构建，本次未升级依赖；不得把该结果描述成“没有漏洞”。原始结果 `dependency-audit.json` 保留在上述输出目录。
- 发布全套测试1107 passed、309 subtests passed、1 skipped（Windows既有symlink权限限制）；冻结后补测227 passed，其中43项为真实隔离PostgreSQL交接与指纹保护测试。日志 `release-tests.log`、`adapter-tests.log`。

## 生产发布与验收结果

- 源码提交：`34fea3bca5d8bdef26a753c83710eb7dc6e9a064`。独立两阶段PASS，最终批准快照 `7454079f6ad2229cb2bc2a98ee0e00c88e0e3eff066dd719384c66ecc19e17cd`，报告见 `reviews/API-RETRY-SIMPLIFICATION-RELEASE-20261020.md`。
- 发布标识：`domestic-api-simple-20261020-34fea3b`；前端0.2.45、国内0031、海外overseas_0019。实际镜像 `sha256:89d54bb54a57a3c22ecf5488552f94695bf6b07abcbcd5780a602f449545b553`。
- 归档1241个文件、5,480,202字节，隐私审计PASS、归档验证PASS；SHA256 `f60fa43e916a48195b0c84cfa3a226712e94dc2fee0280d0553ce711afe74907`。服务器再次校验归档及1240个清单文件；镜像内544个后端源码哈希一致。
- 实际镜像安装测试：2057 passed、169 skipped、1 deselected、6 warnings，461.04秒。跳过需要额外环境的测试，排除依赖本地工具/前端源码的既有安装测试；本地数据库与前端合同另有开发验收，不把跳过计为通过。
- 生产在途工作完成后，保留494张成功、1张失败、1张排队、4张旧uncertain记录完成交接，原97个 bounded-v2 轮次保持；没有手动清状态、清租约或清任务。新outbox启动前全部API行、表列、轮次指纹一致；启动后原终态、版本及成品文件保护核验通过。
- 完整备份位置：`/opt/hengxin-backups/domestic-api-simple-20261020-34fea3b/`；`domestic.dump`为1,047,396字节，隔离恢复及指纹验证通过，COMPLETE存在。发布目录VERIFIED存在、无RECOVERY_REQUIRED。版本台账已completed、无pending，成功回执存在。
- 仅国内api/api-image-worker/api-image-outbox镜像及前端更新；配置、其它国内容器、海外、身份、原生服务核验保持。请求300秒、租约600秒、发送间隔5秒、在途10、失败阈值5、冷却60秒均未修改；未执行数据库迁移。
- 从正式域名 `https://zhitu.qhhengxin.top` 检查记录页、历史成功详情、真实失败详情、新建入口及390px窄屏，已目视截图。新建提示为“未完成的图片会自动重试”；真实旧失败图片显示“重试这张”，无管理员核实按钮。既有原图/成品实际加载，图片下载200。新建页补等通道检查和资源加载结束后重新截图确认。
- 直接读取线上应用路由确认国内管理员resolve接口不存在，单张和批量retry接口存在。浏览器无pageerror、未提交生成/重试请求；临时验收会话已撤销并验证401，临时凭据文件已删除。
- 本地原始发布证据：`output/release/domestic-api-simple-20261020-34fea3b/` 下的package-audit、upload-verification、installation-tests、final-verification、installed-routes、browser-verification及production截图。服务器build/prepare/deploy日志保留于同名发布目录。现场真实重试执行未触发收费调用；执行行为由此前隔离数据库与真实HTTP回归证明。
