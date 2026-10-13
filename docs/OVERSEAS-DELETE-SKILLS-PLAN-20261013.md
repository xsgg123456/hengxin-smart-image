# 海外任务删除与Skill安装开发计划

当前状态：2026-10-13用户授权正式开发，正在实施。需求来源为Product-Spec末尾三节及OVERSEAS-SKILLS-INVENTORY-20261013.md，视觉继承Design-Brief和既有页面。复用现有依赖，不升级框架。功能验收不等于真实收费出图效果验收。

## 有序步骤与完成标准

1. **归档独立与管理员删除后端。** 完整覆盖legacy/studio任务；新增增量迁移、归档独立资产/元数据与原权限归属、后台持久清理状态、停止核实、文件与业务记录实际清理、失败重试与迟到回写防护。先保存并验证归档，再清理任务，禁止删除真实生产样本作测试。文件范围：backend/app/overseas/{archives,tasks,execution,materials,pictures,plans,studio}相关删除准入、permissions.py、海外迁移及专项tests。验收：五角色拒绝/允许、无/部分/全部归档、原任务已不存在仍可查看下载且哈希一致、运行/未知状态/并发/重启/文件故障及目录越界保护。
2. **Skill安装与只读真实目录后端。** 从用户七目录整理14个唯一安装标识，完整复制资源，仅在安装副本适配必要名称自引用；海外专用目录作为来源，索引/冻结快照复用现有机制。提供受控运维安装/核对入口，不通过网页ZIP上传；管理页和工作台选项一致，实际执行仍只读挂载所选完整Skill。文件范围：backend/app/overseas/management/{skills,router,models,...}、studio/queries.py的Skill选项、plans/skills或既有Skill冻结模块、execution/materials.py、必要迁移、installer脚本及tests。验收：全部14份映射/哈希、重名共存、沃尔玛新版标签、缺文件拒绝、旧任务冻结不变、资源大包与不安全目录拒绝、网页写接口不再开放。
3. **前端交互联通。** 管理员任务删除确认/处理中/失败重试、归档独立查看与下载、Skill两列只读与工作台中文选项。文件范围：frontend/src/api/overseas/{tasks,management,studio,archives}及views/overseas相关页面、tests。验收：正常/加载/空/失败/越权及分页、长描述/窄屏布局，去除添加和版本等写入口；删除后归档图片能实际打开。
4. **联合验证与独立审查。** 先有针对性的后端/迁移/PG并发测试，再前端完整测试、typecheck和正式构建；隔离环境跑删除后归档预览下载及Skill选择流程，不写生产测试数据。按harness review-prepare固定快照、fresh code-reviewer两阶段审查、修复并复查，同一快照PASS才登记批准。验证证据写入本计划关联的验收记录。
5. **生产安装与必要发布。** 按release-builder复用现有发布流程，先只读复核环境、保护正在执行任务、备份、迁移、构建并验证再切换；只处理海外服务和必需的共用前端。安装14份Skill，校验生产目录、API目录和工作台可选择、CLI隔离环境可读。不得把宿主机文件存在等同CLI可用；不触发收费生成，不自动删除生产任务。记录安装映射、文件校验与线上结果。

## 并行责任与接口约束

- 删除后端worker负责步骤1；Skill后端worker负责步骤2；前端worker负责步骤3。主Agent负责源文档、集成、整体测试/审查和生产操作。执行worker不得commit或继续spawn，不覆盖彼此修改；共享文件先沟通，主Agent合并。
- 删除后端迁移编号0013，Skill目录无需新增迁移；发布头为overseas_0013，国内保持0027，前端0.2.28。
- Task新增删除状态/错误字段且只返回安全业务文案；专用task.delete仅super_admin授权。清理后台走已有维护进程，可恢复，禁用父任务的新操作统一守卫。
- 归档接口必须支持taskId为空/原任务已删除；独立图片查看和下载受归档自身权限约束。具体字段由后端与前端在修改前同步，不前端虚构结果。
- Skill目录返回轻量id/name/displayName/description及必需兼容字段，不返回全量指令历史；前后端共享实际安装可用性，兼容旧任务内部快照不等于向网页继续暴露写操作。

## 生产实查与发布约束

只读实查确认旧生产为前端0.2.27、海外0012。原生Worker的`/var/lib/hengxin-overseas/local-skills`与API原named volume目录不是同一inode，当前均空。以原生目录为唯一来源；新Compose overlay只替换API/migrate的local-skills挂载为该宿主目录readonly bind，保留原空volume，不更改国内或身份服务。安装目录root所有、755；Worker与API只有读取能力。

14包作为独立运维附件传输，发布代码必须核对完整manifest及SHA256，再原子安装。应用包只包含安装/读取/校验代码，不包含设计素材原件。正式开放入口前，分别以API与真实Worker身份核验同一目录device/inode、14包181文件，并逐Skill进入真实CLI sandbox检查资源哈希、只读挂载和仅选中Skill可见；不触发模型。

实现与验证记录：[本轮验收](OVERSEAS-DELETE-SKILLS-VALIDATION-20261013.md)。
