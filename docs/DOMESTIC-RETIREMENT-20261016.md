# 国内五个旧模块彻底移除 · 2026-10-16

## 授权与边界

用户已授权：先梳理依赖和删表清单，再删除图片处理、任务中心、模板库、成品库、国内Skill管理的专属前后端业务代码及数据库表；保护API换套图所有能力及海外业务，完成完整回归、独立审查、中文Git提交、打包和生产部署。此授权覆盖本次必要的国内迁移、备份、排空和服务切换，不授权删除API/海外图片、会话、业务数据或共享认证。

API保留矩阵：身份与权限、新建换图、素材上传、原图/素材管理、生成调度与重试、记录/筛选/分页、图片修改、文字修改、文案修复、标注画布、CLI对话/续聊/候选采用、历史版本、下载、主动删除、24小时/7天自动清理，以及管理中心用户、配置、执行监控、调用统计。海外全部现行功能保留；生产海外服务及数据库不升级、不重启、不迁移。

## 有序实施及完成标准

1. 依赖与表清单：扫描全仓库引用、数据库外键和运行作业，列出专属删除项与共享保留项；当前旧业务为空仍须在生产迁移前复核。禁止DROP CASCADE掩盖遗漏引用。
2. 共享能力拆出与后端删除：保留API的执行互斥、心跳、文件/对象引用保护及海外Skill校验；移除旧业务路由、服务、模型、调度分支和专属测试。管理统计和配置收敛到现行业务，不伪造旧业务零值接口维持死功能。
3. 前端删除：移除五模块页面、菜单/搜索/路由、客户端与专属类型/mock/测试；清理已持久化旧标签和旧默认入口，旧链接回现有API入口。保留共用上传、预览、标注和海外组件。
4. 数据迁移：保留历史Alembic链，新增0030执行确定的删表与专属状态清理；共享表/现行业务行必须保持。新库完整升级和0029带业务数据升级均用隔离PostgreSQL验证；非空旧数据或未知引用拒绝破坏性升级，先报告而不扩大删除。
5. 完整验证：后端全部现存测试、API专项、海外专项、真实PG迁移/并发、前端全测试/typecheck/build、隔离浏览器核心交互及旧入口回收；删除旧功能测试须逐项说明，不能删掉API/海外失败用例凑绿。
6. 发布：用已审代码快照提交中文Git，打包隐私审计及实际镜像安装测试；关闭国内入口、排空执行与删除/清理工作，保存完整数据库备份并隔离恢复校验，迁移后逐表核对保留数据，切换国内API/执行器/删除及清理服务、共享前端；验证公开健康、身份/海外未变、实际页面。失败保持入口关闭并依据阶段恢复，不自动恢复旧数据库或回退到依赖已删表的旧进程。

## 依赖调查当前已确认

- CLI worker/outbox承担API图片对话，必须保留；只删除generation、skill_install/check/sync等废弃分支。
- API执行门控和国内CLI心跳须移出旧tasks包；API文件清理不能再查询已删模板/Skill表。
- 海外复用Skill包验证器；将纯共享能力抽出，海外业务记录/安装目录保留。
- 当前自动清理服务已启用，API展示开关true；发布必须停止旧清理进程后迁移，并指向新后端恢复原开关和每小时扫描，禁止重置已登记宽限期。
- 发布时当前前端0.2.39、国内schema0029、海外schema0017；必须重新只读验证，不能沿用旧domestic发布脚本的0.2.36/0028基线。

## 已固定的删除及依赖清单

0030删除22张专属表：archive_requests、archive_images、archives、task_requests、execution_usage、execution_attempts、execution_sessions、task_sources、image_versions、result_slots、execution_rounds、task_records、template_images、template_versions、templates、module_skill_bindings、skill_versions、skills、skill_audits、files、deletion_records、cleanup_objects。先解除execution_rounds.base_version_id与image_versions的循环外键，按依赖逆序删表，不使用CASCADE。生产迁移前复核所有表；旧业务图片/任务/清理回执非空时拒绝，不能依据先前空表报告跳过检查。

保留execution_gate、worker_heartbeats、job_records/job_outbox、所有api_*、image_variants、capacity_*、cli_retention/cli_retention_objects、用户/认证/成员申请和设置/审计。仅清理job_records/job_outbox中generation/skill_install/skill_check/skill_sync旧任务，以及image_variants的originals域和cli_retention的legacy_cli域；容量预留不能按kind=cli批量清除。保留表及允许变化协议由0030的RETIREMENT_CONTRACT明确导出，发布前后对照。

共享ExecutionGate迁至app/execution/models.py，WorkerHeartbeat迁至app/worker/models.py，Skill包验证器迁至app/core/skill_package.py，海外需要的SkillRegisterInput迁至共享contracts；四个监控健康工具迁至worker/health_state.py。运行时删除tasks/templates/archives/revisions/skills模块、旧生成与Skill工作分支、legacy retention和旧文件上传下载/业务删除路由。API清理只去旧域引用，保留API文件及冻结快照的跨任务保护。

历史0005/0006/0007直接依赖旧ORM，冻结到migrations/legacy_schema.py的独立MetaData，仅供历史revision使用，不注册到运行时Base；历史revision与依赖顺序不变，保证空库可升级。0030不宣称可无损降级。

前端删除五模块页面和专属API/types/mock/tests，清理全角色旧路由/固定标签/搜索历史/登录回跳。系统配置删Skill默认绑定及目录请求，保留其他配置。保留PicturePreview、UploadInteraction、GenerationPlaceholder、共享标注组件、download-helpers、prototype.css及API/海外预览能力；不能整删旧components目录。测试中的共享身份/上传/下载/标注/设置/监控用例继续维护，纯退役功能用例随功能删除。

## 测试范围与当前证据

- 旧模块专属后端测试删除53个套件及2个配套夹具；身份、上传、下载、缩略图、生命周期、配置、容量、提示词及并发清理等混合套件保留并改用API数据。共享执行、进程、诊断、文件收集、Skill ZIP校验测试保留。旧业务合同测试改为现行API/身份OpenAPI、分页及前后端字段一致性检查。
- 真实PG迁移与共享能力专项49项通过；0030包含9项迁移检查，并真实执行发布工具的SQL指纹比较。覆盖API数据、kind=cli容量预留、设置审计、心跳、API删除和对象清理记录。
- 隔离真实HTTP：现行海外需求审核/工作台、上传原件、归档/删除/安装Skill、统一身份与成员隔离均通过；使用测试数据库和对象存储，零收费模型调用。旧Phase25组合在Phase22的自动进入analyzing断言失败；当前流程是先审核进入工作台，原HEAD隔离副本在同一位置同样失败。Phase17—21在当前版本通过，现行工作台能力另由requirements/delete-skills流程验证，不改产品去恢复废弃自动分析行为。
- 前端旧overseas-shell脚本对国内/海外卡片主题完全相等的断言，在原HEAD与本次版本均因既有border/radius差异失败；保留基线复现，不修改主题、不弱化原断言。现行海外材料故障/权限、API对话画布和四角色旧入口回收另行通过。
- 最终Linux后端全量2024通过、25跳过；其中22项Redis和1项跨UID检查已在补跑的38项中通过（同时覆盖恢复的0024 API清理迁移测试），Windows junction另在Windows通过。唯一尚未执行的是要求已有非root hengxin WSL运行环境的开发工具启动清理用例；不得将其写成已通过。
- 前端280项全部通过，typecheck及生产构建通过；发布/维护工具691项通过、12项环境分支跳过、237个子测试通过。API对话/标注/采用/续聊、四角色旧入口回收、系统配置、海外材料与工作台浏览器检查通过。附件100/101上限和海外管理筛选脚本按现行界面更新后通过；500MB仅核对文案，未运行实际大文件上传。
- 生产依赖审计critical为0；已有high 36、moderate 34、low 1，依赖锁文件未改动，不宣称依赖漏洞已清零。最终独立审查及生产验收在下文登记；本节不代表已发布。
