# CLI 最终成品验收整改生产发布

2026-09-27 11:14（Asia/Shanghai）上线并完成安装核验。用户已明确授权打包部署生产。

## 版本与范围

- 发布：`delivery-20260927-b1f212b`；代码提交 `b1f212b`，产品整改提交 `53e5586`。
- 镜像：`hengxin-smart-image-backend:delivery-20260927-b1f212b`。
- 镜像 ID：`sha256:b06f971d7e095f820b269e534f8d2e0339dc7af5268150b07fdd358e411211c2`。
- 包 SHA256：`84b3ce603f8e5b40f4bf338c991057ba6a4b81d1719302ee8c614a36cd49d747`，275 个受控文件，310866 字节。
- 更新 API、CLI outbox、API image worker/outbox，以及原生 CLI Worker 的 16 个源码/依赖清单文件。
- 前端保持 0.2.7；数据库保持 0017，无迁移。模型、Skill、超时、并发、凭据和运行配置保持。

本轮完整、有效、可读取的最终成品经过统一验收后冻结，再持久保存。网络历史错误、异常计量、重复终态和交付后的非零退出不再单独否决成品。暂时保存失败自动补收，不重新生成。数量、轮次归属、有效图片、安全路径、取消与发布权限仍校验。成功仍意味着持久保存和发布已完成。

## 安装与在线证据

- 产品本地回归：后端 1183 通过、171 跳过；前端 176 通过，类型检查/构建通过。详见根目录 `docs/CLI-DELIVERY-FIX-VALIDATION-20260927.md`。
- 发布脚本独立两阶段审查通过；最后批准快照 `c35e1d7114f32ec02bbfbac1150ba1dd8da1d9d8e0b1f743293d7b2a02596461`。
- 打包回归 5 项通过；真实 recover 函数的 10 种故障演练通过；Linux 原生备份恢复测试 11 项通过。
- 首次镜像测试发现漏打 JSON 测试样例，已补齐、复审、重新提交并构建；旧试包 `delivery-20260927-397819a` 未部署。
- 最终镜像断网、无生产数据挂载：1170 通过、75 环境跳过、1 deselected、15 warnings。排除依赖仓库外围 infra 的 local_codex/phase11a 测试；单独 deselect 前端源码类型对照，以上已在本地源码全量测试。未将这些排除项计为镜像通过。
- 新增 markdown-it-py 4.0.0、mdurl 0.1.2 的 OSV 查询无已知记录；原生依赖安装后 51 包兼容检查通过。未宣称执行了全部依赖的完整漏洞审计。
- 排空 API/CLI 队列后备份数据库及原生源码和完整虚拟环境，切换退出码 0。
- 四个容器分别核对 269 个后端文件 SHA256，全匹配；原生 Worker 16 个文件全匹配。四服务镜像 ID、显式环境配置和命令核验通过。
- CLI Worker 心跳、API Worker 队列与并发 5 验证通过；原生 Worker active。
- readiness 200（PostgreSQL/Redis/MinIO up），公网首页 200，匿名 `/api/v1/auth/me` 401，API 接纳恢复。
- 切换后五个执行服务日志未发现 Traceback、ImportError、ModuleNotFoundError、CRITICAL 标记。
- 上线前后任务数量一致：CLI 成功 39、失败 13、取消 2；API 成功 10。未自动改写历史失败任务，未执行收费生成测试。

本地证据在 `output/release/delivery-20260927-b1f212b/` 的 package-audit.json、installation-tests.log、deploy.log、verification.json。服务器同名发布目录保留原始证据。

## 维护与回退

发布目录 `/opt/hengxin-releases/delivery-20260927-b1f212b`；备份目录 `/opt/hengxin-backups/delivery-20260927-b1f212b`。数据库 dump 已用 pg_restore --list 校验；源码含原权限/所有者，虚拟环境 tar 含摘要。旧镜像 `materials-20260924-2cdb4ff` 保留。

维护时必须沿用以下完整 Compose 链，不能只用基础 compose 重启而退回旧版本：

1. `/opt/hengxin-smart-image/infra/compose.yaml`
2. `/opt/hengxin-smart-image/infra/compose.vps.yaml`
3. `/opt/hengxin-smart-image/infra/compose.api-image.yaml`
4. `/opt/hengxin-releases/three-fixes-20260923/api-override.yaml`
5. `/opt/hengxin-releases/cli-two-hour-20260923/api-override.yaml`
6. `/opt/hengxin-releases/inputs-20260923-b2841c7/api-override.yaml`
7. `/opt/hengxin-releases/annotation-20260924-6b43b3c/api-override.yaml`
8. `/opt/hengxin-releases/materials-20260924-e3c60c9/api-override.yaml`
9. `/opt/hengxin-releases/materials-20260924-2cdb4ff/api-override.yaml`
10. `/opt/hengxin-releases/delivery-20260927-b1f212b/api-override.yaml`

API_RELEASE.json、API_IMAGE_RELEASE.json、NATIVE_IMAGE_INPUTS_RELEASE.json 和 DELIVERY_RELEASE.json 已记录实际版本和叠加链，旧元数据在备份目录。

需要回退时先重新停止接纳并排空当前任务，再停止相关 Worker；用本次 delivery-native.py 的 restore 恢复备份源码/虚拟环境，并使用前九层 Compose 恢复旧后端镜像。恢复心跳、队列、健康后才能开放入口，并恢复旧发布元数据。无数据库迁移，不应直接恢复 dump 覆盖上线后的业务数据。部署脚本内置切换失败回退，不能把再次执行 deploy 当作回退命令。

## 发布后按用户授权恢复指定任务

用户随后明确要求恢复“丝印防窥”任务 `108e57d4-026a-486c-a931-68e32dbe8b6c`。通过已上线 `prepare_recollection` 对诊断编号 `4b841c26-5480-4cb9-baa1-0fb25f07a186` 重新准入，正常 Worker 恢复器自动补收，无代码热改、无新模型调用。当前轮次 `647d7587-a631-4120-94df-36e51c777acc` 已为 succeeded，序列化页面状态“待查看”，3个槽位各有1个当前版本，错误清空，执行次数保持1。

已逐张从MinIO读取并完整解码，长度/摘要与原成品匹配：01.jpg 544871字节、02.jpg 710217字节、03.jpg 525921字节。原任务/轮次/作业/执行记录/槽位/用量备份和补收验收保存在服务器备份目录的 `recollection-4b841c26/`。执行记录保留原失败诊断及补收标记。其他历史失败任务未改写；前述“未自动改写历史失败任务”描述发布切换本身，此处为用户追加授权的指定补收。
