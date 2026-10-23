# 海外工作台多会话实施合同 · 2026-10-24

用户已批准 preview-studio-sessions（含已完成与解冻确认）并授权正式开发、中文Git提交、打包及生产部署。本合同取代此前仅预览限制；生产不得出现演示状态按钮、模拟生成或假归档。

## 产品与验收
1. 每个工作流任务最多保留10个独立Codex会话。并发新建也不能突破10；可重命名（1–30字）、删除（确认，运行中须先停止）。删除释放名额，保留已归档成品及来源信息。历史会话全部保留可切换，已有超过10的任务不删历史，只禁新建直至低于10。
2. 同会话同一时刻仅一轮排队/执行；跨会话允许实际并行，不只是前端可点击。排队与执行状态如实展示；停止只作用于当前会话目标轮次。后台完成标记新结果，不自动切换。任务完成需所有会话均无在途且有有效归档。
3. 每会话独立CLI sessionId、持久工作/输入/输出目录、消息/过程、草稿、Skill、附件与修改图片引用；切回原会话继续原上下文。任务级原始素材可显式引用到各会话，不自动注入；会话上传默认私有，模型输入/图片引用不得跨会话。账号凭据仍由既有受保护代理管理，不复制refresh令牌或放宽沙箱。
4. 用户按任务/身份记住当前会话，不共享服务器全局当前指针；切换/刷新恢复草稿及滚动位置。后台请求迟到不能改写新会话、误清草稿或误投发送。未知发送状态按原会话/幂等键核实，不能跨会话重放。
5. 归档只选择当前会话图片，弹窗说明当前任务/来源会话/SKU。归档仍归同一任务，汇总可查来源；删除会话后归档独立展示/下载。既有图片和归档不得丢失。
6. 完成态所有会话只读但可切换/查看，顶部任务完成提示。解冻确认取消无变化，确认恢复整任务全部会话编辑，不重走提交审核、不自动生成，历史会话/文件/草稿/归档保持。可再次完成。
7. UI以已确认preview-studio-sessions为准，复用真实框架与组件。保留原有素材、标注改图、交付恢复、Skill开关、权限/幂等/重试与任务归档细节。新会话列表收起与窄屏可达。

## 前后端交接约定
- Studio增加 conversations:[{id,name,version,createdAt,updatedAt,activeTurnId,status,turnCount}]、activeConversationCount、maxConversations:10；conversationId为本响应展示的会话。旧字段兼容，不全局持久化选择。
- GET studio 增可选query conversationId；指定时仅返回该会话turns和可见materials（任务公共+该会话上传）；未指定维持兼容默认选择。GET transcript同可选conversationId，游标按所选会话清理。
- Send新增conversationId（新客户端必传，旧客户端兼容默认）；POST conversations仍幂等新建（body可含name），响应conversationId指向新建项；不清除旧草稿。
- PATCH conversations/{id}: {name,version}，Idempotency-Key；DELETE conversations/{id}: {version}，Idempotency-Key；响应Studio。返回410/404表示已删除，409表示运行中/版本冲突/上限，错误清晰。
- POST files新增query conversationId，上传关联该会话；新客户端上传均传。mutation响应尽可能返回操作会话，任务级操作保留客户端选择后刷新；后端审计/权限强制taskId与conversationId归属。
- conversations各状态 queued/running/succeeded/failed/cancelled/empty；activeConversationCount统计全任务非终态会话数。task全局归档和完成/解冻版本幂等保持。
- 会话删除须清理专属记录、文件和未归档图片，保护共享任务材料、其他会话、独立归档；危险路径经既有安全文件规则；失败可重试且不假成功。服务恢复不得重新调度被删除会话。

## 工作分工与验收顺序
1. 主Agent同步Spec/Brief/计划，核实生产基线与发布路径。完成标准：合同/真实服务版本/权限配置和执行队列事实明确。
2. 后端worker独占backend：模型迁移、API、执行并行与隔离、删除清理、归档来源、回归测试。前端worker独占frontend/src及tests：API类型、控制器会话状态、真实页面、草稿与交互测试。双方不提交、不部署、不继续派生agent，不覆盖他人改动；接口变化及时报告主Agent。
3. 主Agent集成全量测试、类型/正式构建、Linux/真实PG并发与隔离浏览器测试，保留证据；独立code-reviewer两阶段审查与修复循环。
4. 主Agent维护发布脚本/版本/打包，核验生产真实基线，排空在途，备份并隔离恢复校验；中文Git提交受审代码，发布实际安装包。保留国内/身份/凭据代理、授权成员和Skill配置，不删除用户历史、不自动付费生成；生产真实入口视觉及只读验收。失败按实际阶段恢复，不覆盖生产新数据。

## 实施细化：删除与执行容量
会话删除由既有原生maintenance执行受限文件清理，DELETE受理返回Studio，conversations增加deletionStatus（null/deleting/delete_failed）和deletionError；清理中/失败仍占名额，禁止该会话发送/重命名/归档，失败可明确重试。清理成功才移除并释放名额。其他会话可继续操作。归档图片新增sourceConversationId/sourceConversationName持久快照，历史仅精确关联回填，不猜来源。现有5槽执行容量保留；允许跨会话真实并行，容量满时真实排队，10为保留会话上限。

## 升级兼容：旧版未确认请求

升级前的未确认发送可能没有body.conversationId，但浏览器保存了draftConversationId。迁移时必须恢复到该原会话，保留原请求体指纹与幂等键；已受理回执只核实，不重复创建轮次，未受理请求仅能发送到可证明的原会话。不得默认重放到最新会话、不得清理其他会话草稿。原会话缺失、已删或归属不可证明时保留原请求内容，明确提示核实且禁止自动重放。此兼容属于“迟到请求不串线”验收的一部分。

POST studio/turns 可选 query conversationId 仅为缺少 body.conversationId 的旧请求提供原会话路由，不修改原请求体哈希。回执必须核对该提示与归属；已受理只回放并绑定旧空来源，不同来源重试返回409。旧归档请求原样发送，不补写body字段；旧新建会话请求重试不清除草稿。无法证明来源的旧请求保留并提示人工核实。
