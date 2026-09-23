# Development Plan — 恒鑫智图

## 2026-09-23 · API 单张修改多图参照

本地实现及验证记录见 [API单张修改多图参照验证](docs/API-REVISION-MULTIREF-VALIDATION-20260923.md)。本轮未部署生产。

1. 公共提示词：CLI壁纸输出保持原语义，API按图号拼接三/四图、原文意见和仅标注默认说明；验收CLI回归及API角色/顺序/输出要求。
2. API输入及迁移0017：冻结有序文件引用、最终提示词和规则版本；扩展relay多图并兼容旧调用。验收新轮次三/四图、旧轮次旧协议、缺失损坏失败、重试不漂移、文件引用保护和版本恢复。
3. 沿用弹框，仅更新自动参照提示；验收前端测试、类型和构建。后端隔离HTTP功能测试、全套回归、编译、迁移往返及独立两阶段审查，交付证据；不部署生产。

## 2026-09-23 · CLI 壁纸单张修改原图对照

1. 从任务冻结模板的目标槽位准备 originalPath，保留用户选定的成品版本、素材及可选标注，继续跳过Skill；验证不同槽位/历史模板与成品版本、原图不可用失败及其他模式兼容。
2. 按已确认模板拼接角色明确的短提示词，原图目录禁止作为最终产物收取；验证四个Skill统一、无标注/空意见兼容、首次与整套逻辑不变。
3. 后端回归和编译、独立两阶段审查；只更新相关Worker代码，停止接纳并证明空闲后备份切换，从安装产物验证材料和提示词，用户自行进行真实生图测试。

## 2026-09-23 · CLI两小时执行额度

1. 扩大部署/管理/前端时限上限至7200，发布示例同步7200/7800；验证越界拒绝、配置审计、新旧轮次冻结与续跑共用总时限。
2. 后端回归、前端校验与构建、独立审查；备份生产配置，排空CLI Worker后切换，核验API设置与Worker实际环境均为7200/7800。

## 2026-09-23 · 三项生产整改

1. 统一识别可恢复重连，验收重连后成功可收图、真实错误/错会话/缺失成品仍拒绝。
2. 增加专用 Worker 的 needrestart 排除项和排空后重启工具，验收忙碌或无法确认状态时绝不停止进程。
3. 完成 API 五任务调度，隔离 PostgreSQL 并发验证5任务/50图片上限与第6任务排队。
4. 编译、回归、独立两阶段审查；备份并安全切换生产，校验部署内容、服务健康与两笔成品补收。不运行新的收费模型任务。

## 2026-09-23 · CLI 优化发布与Git提交

1. 核对已批准快照和服务器基线，按文件白名单打包并校验隐私及SHA256；从解包产物运行专项回归。
2. 备份生产文件，暂停专用Worker消费并确认空闲，替换后编译/重启；检查已安装代码、心跳、CLI版本和队列。
3. 写发布与回退记录，核对审查凭据，中文提交当前CLI升级和提示词/干预改动；不自动推送main。

## 2026-09-23 · CLI 首轮换套图自动干预

1. 固化通用干预提示词和首轮范围/次数/总时限；验收初次失败可续接1次、人工返工及单张不触发。
2. 同轮双次执行共用原HOME/work/收图基线，分别保存控制日志并持久标记次数、汇总用量；验收候选复用、最终整批交付、执行播报与错误终止。
3. 验证取消、租约失效、认证/额度、会话缺失、Worker崩溃与恢复不重放，隔离数据库/临时目录测试；完整后端回归、编译和独立两阶段审查。无需数据库迁移或前端改版。本轮不部署。

## 2026-09-23 · CLI 单张成品修改简化

1. 独立拼接单张成品修改提示词，验收四个 Skill 一致、可选标注/意见、素材语义正确。
2. 材料准备仅提供冻结成品与素材及可选标注，跳过原底图与 Skill 加载；隔离本轮 Skill 发现目录，保留会话续接。验收历史版本、损坏原底图/Skill 不阻塞成品修改、失败图重试兼容。
3. 执行回归、编译和独立审查；备份生产文件并在 Worker 空闲时发布，验证部署文件及运行健康。

## 2026-09-23 · 详情图提示词区分

1. 按两个详情图 Skill 完整名称调整壁纸提示词；验收主图与其他模式原句不变。
2. 回归首次生成、返工、多素材及现有执行链，编译并独立审查。
3. 备份生产提示词文件，空闲时切换 Worker，验证四个 Skill 的实际拼接结果与服务健康。

## 2026-09-22 · API图片处理动效

1. 扩展CLI现有占位组件的可选文字、静态和紧凑模式，默认CLI行为保持一致；API结果卡片接入状态映射。
2. 验证生成/收图/等待/失败/待核实/成功及保留旧结果修改状态，检查180px图片区域无溢出、减少动态效果和真实页面渲染。
3. 完成类型、单测、生产构建与独立审查后仅部署前端，保留后端进程及当前OSS配置。


## 2026-09-22 · API 换套图正式优化开发

本机正式实现已完成：Linux后端924项通过（64项条件跳过）、前端153项通过、类型/构建/真实HTTP隔离联调及独立两阶段审查通过。已部署生产（api-opt-20260922-27d41a2），详见 [验证记录](docs/API-IMAGE-OPTIMIZATION-IMPLEMENTATION-VALIDATION.md)。

用户确认按六项范围开始正式开发，承接已审前端预览。数据迁移、接口与Worker、真实前端及验证以 [正式实现计划](docs/API-IMAGE-OPTIMIZATION-IMPLEMENTATION.md) 为准。本轮包含10张分批并行、失败重试、页面整改、ZIP、单图修改及图片历史版本。


## 2026-09-22 · 单图历史版本预览

本地预览新增图片版本保存、历史对比、下载旧版与设为当前；当前版参与后续修改和 ZIP。沿用现有蓝色主题、卡片和弹框。实施与验收按 [本轮计划](docs/API-IMAGE-VERSION-PREVIEW.md)，不涉及生产部署。

## 2026-09-22 · API 换套图优化预览

当前工作：按 [预览计划](docs/API-IMAGE-OPTIMIZATION-PREVIEW.md) 在现有前端demo/mock实现并行批次、单项重试、单图修改弹框、ZIP、操作人及静默进度展示；先状态与界面隔离并行，再类型/测试/双构建/浏览器验证及独立审查。不修改生产后端或部署；用户评审交互后再承接正式实现。

## 2026-09-22 图片处理菜单新建修复

已完成：125项测试、类型、生产构建、运行中任务场景的菜单专项及独立两阶段审查通过。提交 `b086a49` 已发布为 `ui-20260922-b086a49`，线上399文件、公网首页、健康及登录页检查通过；见 [发布记录](hengxin-smart-image/docs/NEW-TASK-MENU-20260922.md)。

1. 统一菜单跳转为三类图片处理入口创建新的newTask标识，同页重复点击也切换创建会话；其它导航不变。
2. 浏览器验证上个任务已受理且仍排队/执行时，再点击菜单得到空白新表单；同页再次点击也重置，旧任务留在任务中心。回归提交幂等及未确认状态测试。
3. 类型、构建、相关及全套测试、独立审查通过后交付；生产发布与Git状态另行记录，不把本机修复称为上线。

## Skill管理轻量化 · 2026-09-21

用户已授权提交Git并部署生产：先提交已批准快照，再白名单打包/审计；确认无在途任务并备份，升级0014、切换API/Outbox/原生Worker和前端；验证文件哈希、服务健康、目录接口和真实页面。保留历史Skill树、模型及五并发，不自动提交付费生图；失败回退应用并保留已产生新快照所需迁移字段。

本机实现与验证完成：取消人工Skill版本管理，新增目录同步与用途描述，稳定身份绑定及任务完整快照。前端119项、类型和正式构建通过；后端全套801项、最终相关51项及Linux真实隔离通过。独立审查发现的同步竞争、模板锁顺序和遗留筛选差异均已修复复核。见 [验证记录](hengxin-smart-image/docs/LIGHT-SKILLS-VALIDATION.md) 和 [审查报告](hengxin-smart-image/docs/LIGHT-SKILLS-REVIEW.md)。已提交f02b1e0并部署`light-skills-20260921-f02b1e0`，0014迁移、哈希/健康及真实页面同步验证通过，历史local发布树保留；见 [发布记录](hengxin-smart-image/docs/LIGHT-SKILLS-DEPLOYMENT.md)。

1. 后端目录与同步：扩展skills模型/契约/API、Worker同步作业及迁移；固定根目录扫描name/description、识别或选择类型、自动校验/启用、保留停用、异常与移除。验收鉴权、重复同步、缺失目录/损坏元数据、文件安全和旧登记兼容。
2. 执行快照与绑定：复用现有内部快照记录，新增任务按稳定Skill身份取当前成功内容，模板/默认跟随身份；已提交任务与返工冻结完整文件。验收不同字节更新、旧任务继续旧内容、存储失败不发布、历史ZIP/目录和移除引用保护。
3. 前端：简化admin/skills.vue、SkillDefaults、模板选择和任务摘要；展示描述全文，删除人工版本入口与版本显示，补mock/契约/错误空态。继承Design-Brief和既有Element Plus组件。
4. 验证交付：后端全套及独立PostgreSQL迁移/并发、前端全套/类型/正式构建、真实浏览器交互、独立两阶段审查；明确本机与生产边界，不触发付费任务。

## 单张返工：所见版本与圈注截图 · 2026-09-21

生产发布已获用户授权：核对批准快照与无在途任务，白名单打包并审计，备份数据库/应用/配置，升级0013并切换API、Worker和前端；核对安装哈希、健康、五并发及线上入口。不自动发起付费生成；失败时恢复应用并保留兼容的新增可空字段，避免覆盖上线后业务数据。

依据 REQ-005、AC-007A/B；先完成本机实现与验证，后按用户授权发布。复用既有 Vue/Element Plus、文件上传、异步轮次和同会话执行，不新增依赖。已发布 `single-revision-20260921-84d1bee`，0013迁移、哈希/健康及线上弹窗核验通过，见 [发布记录](hengxin-smart-image/docs/SINGLE-REVISION-DEPLOYMENT.md)。

1. 后端输入与快照：扩展 `backend/app/contracts/business.py`、`modules/tasks/` 和迁移0013，保存 `baseVersionId`、`annotationFileId`；单张校验版本所属任务/槽位与文件权限，整套不接收单张附件。失败重试沿用冻结输入，结果仍追加版本。验收历史版本选择、非法跨槽/跨任务、附件授权、重放与重试测试。
2. Worker材料：调整 `backend/app/execution/materials.py`、`prompts.py`，用指定成品作为修改基础、圈注作为定位参考，保留原模板及素材辅助参照；明确仅交付目标1张及忽略截图标记，不修改已发布Skill。验收单张原编号、历史版本映射、附件与返工提示词、整套和旧轮次兼容。
3. 前端交互：调整 `frontend/src/views/hengxin/components/ResultCard.vue`、`TaskDetail.vue`、返工会话状态、上传组件及契约/mock；点击时冻结显示版本，弹窗展示版本及预览，可选1张问题截图，支持预览/移除/替换，错误与上传中阻止提交，身份/任务切换隔离草稿，执行记录显示基础版本与截图。验收V1/V2选择、文字无图、带图、失败重试、提交不确定与其他槽位保持不变。
4. 交付验证：前后端相关及全套测试、类型检查/构建、独立浏览器交互与两阶段代码审查；记录已测与未测边界，不用mock宣称真实收费换图通过。

本机实现与验证完成：前端114通过及类型/构建通过；后端PostgreSQL隔离环境785通过/105条件跳过，0013迁移与圈注引用保护通过；浏览器验证历史V1返工产生V3、上传错误拦截及截图替换。证据见 [验证记录](hengxin-smart-image/docs/SINGLE-REVISION-VALIDATION.md)，独立审查见 [审查记录](hengxin-smart-image/docs/SINGLE-REVISION-REVIEW.md)。后续已部署生产，尚未发起真实付费模型任务。

## 生产配置：五并发试运行 · 2026-09-17

用户授权并发调至5。无在途任务后同步Worker池、部署容量和后台版本化配置，验证实际池大小及接口有效值，保留备份；用户随后提交五任务压测。见 [配置记录](hengxin-smart-image/docs/CONCURRENCY-5-20260917.md)。

已生效：Worker池5进程、API容量5、后台版本3并发5，服务健康；未自动创建付费任务，五并发生成验收待用户测试。

## 当前修复：播报完整显示 Skill 名称 · 2026-09-17

已部署 `skill-name-20260917-79892f0`，66项测试、独立两阶段审查、线上文件哈希和真实播报回放通过。详见 [发布记录](hengxin-smart-image/docs/SKILL-NAME-DISPLAY-DEPLOYMENT.md)。

1. 从已准备的任务工作区传递绑定 Skill 标识，精确保留其普通及行内代码写法；其他脱敏规则不变。
2. 验收普通版、优化版名称及事件到API展示，检查相似长标识、路径、凭证不泄露；独立两阶段审查后部署并验证安装产物。
3. 历史已脱敏播报保持原始审计记录，不猜测替换；新执行播报显示完整名称。

## 当前调整：简洁提示词与最终回复收图 · 2026-09-17

已部署 `final-reply-20260917-59d22f5`，生产哈希、健康、Skill隔离读取及真实成品收取核验通过；网页新任务生成待验收。本机后端711通过/146跳过，Linux专项76通过，前端110通过及构建通过。详见 [发布记录](hengxin-smart-image/docs/FINAL-REPLY-DELIVERY-DEPLOYMENT.md)、[验证记录](hengxin-smart-image/docs/FINAL-REPLY-DELIVERY-VALIDATION.md) 和 [最终审查](hengxin-smart-image/docs/FINAL-REPLY-DELIVERY-CLOSEOUT-REVIEW.md)。

1. 保持业务 Skill 文件不变，修改 prompt 与任务私有发现目录；验收名称调用、所有输入、返工意见和只读完整 Skill。
2. 从当前调用最终答复读取明确图片引用，收取本轮最终成品；验收修复图、候选冗余、顺序、缺图、历史图、越界及链接拒绝，不依赖 Skill manifest。
3. 新执行记录交付协议版本，runner 与异常恢复共用收图逻辑；旧执行保留旧恢复协议。验收取消/超时/重投/恢复不误发布以及整套、单张返工。
4. 跑后端全套回归、编译、独立两阶段审查，并在独立测试环境用真实实验产物贯通收图与存储；生产部署和网页真实生成验收分别记录，不把本机测试写成线上完成。

最新生产模型更新：`model-20260917-0bb0454`，新任务和返工固定 `gpt-6-astra / high`。备份、验证与边界见 [ASTRA-HIGH-DEPLOYMENT.md](hengxin-smart-image/docs/ASTRA-HIGH-DEPLOYMENT.md)。

## 固定生产模型 · 2026-09-17

1. 在真实 CLI 首次执行与 resume 公共参数指定 gpt-6-astra/high；验收两条分支参数一致。
2. 运行执行专项回归、编译及独立审查；使用生产相同隔离环境查询解析模型，不发起生成。
3. 无在途任务时备份并更新生产 Worker 代码，重启验证健康和文件哈希；不自动重试历史任务。

## 追加发布收尾 · 2026-09-17

按用户授权提交 Git 并重新打包部署。先将构建链 tar 固定到修复 critical 的 7.5.19，同步锁文件；验收 audit critical=0、前端测试/类型检查/构建通过及独立增量审查。随后以批准快照和 Git 提交标识发布，核对服务健康及产物哈希，不重复删除历史或安装 Skill，不触发付费换图。

当前部署：2026-09-17 `skills-20260917-1d611e9` / 迁移0012，两个本地壁纸 Skill 已启用，普通版默认。部署检查通过，critical 构建依赖已修复，其他级别依赖告警仍保留；真实生图未验收。详见 [发布记录](hengxin-smart-image/docs/RELEASE-LOCAL-SKILLS-20260917.md)。

## 本轮追加：自然语言任务提示词 · 2026-09-17（已部署，真实换图待验收）

1. 同步完整 Skill 到 `/work/skills/{标识}/`，兼容本地只读挂载和历史 ZIP，部署探针使用相同目标路径；验收路径安全及完整脚本/参考文件可读。
2. 按手动测试格式拼接图片角色、实际路径/张数和壁纸要求；验收商品/文字不误用壁纸文案、返工保留当前结果及 slot 对应、补充原文不丢失。
3. 跑后端回归和真实 Linux 挂载测试，固定新快照独立审查。仅本机开发，不部署、不触发付费换图；真实相同素材对照留待部署验收。

完成证据：后端645通过/145条件跳过、Linux真实隔离9通过、编译通过；独立两阶段审查PASS。详见 `hengxin-smart-image/docs/PROMPT-FORMAT-VALIDATION.md`、`PROMPT-FORMAT-REVIEW.md`，实际生成示例见 `PROMPT-FORMAT-EXAMPLE.md`。已按用户授权部署，尚未提交；生产记录见 `hengxin-smart-image/docs/RELEASE-LOCAL-SKILLS-20260917.md`，下一步对照真实图片效果。

## 本轮：人工部署 Skill 与本地登记 · 2026-09-17（已部署，真实换图待验收）

依据 Spec v0.25，本轮不改既有阶段历史结论，不自动部署 VPS。

1. 数据与登记接口：扩展 `backend/app/modules/skills/`、`app/contracts/` 和迁移 0012，保留 ZIP 字段/来源兼容；新增本地版本登记、异步检查、显式启停及引用保护的移除。完成标准：权限、重复、状态冲突、审计、迁移及旧版本测试通过。
2. Worker 校验与执行：扩展 `backend/app/worker/`、`app/execution/materials.py`、`workspace.py` 和配置；本地文件树校验、固定哈希、依赖/隔离探测、只读版本挂载；旧 ZIP 路径保留。完成标准：漂移、链接/越界、缺失、执行用户写权限、失败重试和版本冻结验证，Linux 隔离专项通过；不触发付费生成。
3. 管理界面：修改 `frontend/src/views/hengxin/admin/skills.vue` 及 API、类型、校验器、mock、测试，沿用 Art/Element Plus；登记代替上传、检查代替安装，明确历史 ZIP 来源与移除登记边界。完成标准：类型、全量前端单测/构建和浏览器正常/错误/空态无裁切。
4. 集成交付：更新 API/部署/交接说明，运行前后端回归、迁移及独立两阶段代码审查，批准同一快照。完成标准：证据说明本机验证与 VPS 未部署边界；旧任务、模板及默认版本不会静默改变。

实现与测试已完成，独立审查发现的版本说明、SemVer 和 mock 唯一键差异已修复并回归；最终两阶段 PASS，报告见 [LOCAL-SKILL-REVIEW.md](hengxin-smart-image/docs/LOCAL-SKILL-REVIEW.md)。验证环境、执行结果及明确未验收边界见 [LOCAL-SKILL-VALIDATION.md](hengxin-smart-image/docs/LOCAL-SKILL-VALIDATION.md)。本轮桌面管理页验收，现有移动端侧栏布局未调整。用户已确认张帅账号能正常登录，下方历史 50002 记录不再是当前阻塞。后续已按用户授权完成 VPS 协同升级及两个本地 Skill 发布，普通版默认，旧测试引用及旧 Skill 已按授权清理；尚待真实换图验收。

## 本轮本机开发：13.2 / 13.3 · 2026-09-16

当时授权先本机开发、后续再提交；同日晚间已提交 `99ff375` 并部署 VPS。本轮工作分为：
1. 监控：真实 Worker 心跳、队列/运行任务、脱敏失败与依赖探测；验证角色隔离、过期心跳未知及空闲不误报。
2. 配置：新增持久化版本/审计，超管修改、冲突拒绝、默认 Skill 原子校验；轮次冻结执行超时与配置版本，上传限制实际生效。
3. 前端联调：继承现有页面，显示部署容量限制和只读钉钉标识；真实 HTTP、错误/空态、测试/编译/隔离功能验证及独立审查。

并发为调度准入上限，不在线扩容 Celery pool；网页最大值受部署 generation_concurrency 限制（本机 2）。旧轮次冻结值保留，调整不终止在途执行；增加容量须另行部署。上传仍受平台 10 MiB 硬上限约束，超时上限不超过 3600 秒且受部署 codex_timeout_seconds 限制，页面展示实际部署上限。钉钉凭据和标识由部署环境管理，网页只读。

## 历史交接状态 · 2026-09-16

Phase 1–11A 已按历史范围验收；12.1 已实现并审查通过；12.2 双端授权代码、退出登录和钉钉容器免登修复已部署，真实双端业务验收未完成；13.1–13.3 调用统计、执行监控和系统配置已部署到 VPS 开发测试环境，真实角色联调待验收；14.1 VPS 与 HTTPS 已部署，三类真实 Skill、恢复演练和容量验收未完成。

GitHub 当前业务分支 `codex/management-monitor-settings` 与 VPS 业务代码基线为 `99ff375`；API/Outbox 镜像 `hengxin-smart-image-backend:99ff375`，迁移 `0011`，Worker 已重启。浏览器 state 绑定与失败防重放通过线上检查。钉钉配置接口可用；匿名 auth/me、monitor、settings 均 401。吴永杰企业成员映射通过；张帅已配置初始管理员，但实时成员读取返回 50002。

接手操作与证据见 [HANDOVER.md](hengxin-smart-image/docs/HANDOVER.md)。以下带日期段落保留历史，当前状态以本节为准。

## 钉钉回调修复 · 2026-09-16

真实登录日志确认用户资料接口认证失败；修正专用令牌请求头，新增 unionId 到企业 userId 的应用凭据核验，管理员匹配只使用企业成员 ID；登录页展示回调错误类别。认证/会话测试 12 项通过，前端类型检查及构建通过；吴永杰的真实企业成员映射核验通过。已发布 VPS 修复镜像 callback-fix-20260916，线上前端产物匹配、配置接口正常、匿名请求仍为 401。后续独立集成审查两阶段已通过，最新部署 d2e5076；认证相关回归 16 项通过。真实双端完整授权仍待验证，不标记阶段验收完成。

## 退出登录修复 · 2026-09-16

补齐工作区顶部退出入口，调用现有服务端注销接口，清理前端身份后整页进入登录页；失败提示重试。前端 89 项测试、类型检查和构建通过，本地浏览器点击退出及刷新停留登录页已验证。本专项独立两阶段审查通过（LOGOUT-REVIEW.md），前端已同步 VPS 并备份旧产物。VPS 已关闭开发身份，匿名身份、任务、模板、用户管理接口返回 401，钉钉配置接口返回 200。当前本地后端仍保留开发身份且钉钉配置接口返回 404；真实钉钉认证不算本次已验收，使用 VPS HTTPS 域名继续验证。

## Phase 13 管理中心开发开始 · 2026-09-15

用户明确将钉钉通讯录用户搜索权限 `qyapi_addresslist_search` 后置配置。此为当时前置条件；截至 2026-09-16 两位管理员 userId 已解析并配置，当前等待张帅通讯录范围和双端实测。

当前先交付 **13.1 调用统计真实接口**：把 Phase 9 已采集的执行轮次、实际操作者、结果版本和 CLI usage 接入 `/management/usage`，按上海时间自然日、个人/全员权限、日期/人员/处理类型筛选返回统计与明细；用数据库测试覆盖成功、部分失败、失败、进行中、缺失 usage、重复 usage 和越权查询。接口实现及相关测试已完成，已通过提交前集成审查并部署，真实角色联调待验收；后续进入 13.2 和 13.3。

## Phase 11A 用户验收完成 · 2026-09-14

用户确认开发机真实 Codex CLI 的双任务并发 2 已测试通过，Phase 11A 的开发机联调进入完成状态。现有证据覆盖真实 Worker、两个独立 CLI 实例、会话与目录隔离、任务结果归属及并发执行；尺寸例外仍按既定记录保留，商品/文字 Skill 和生产容量验收不在本阶段范围内。

下一阶段进入 **Phase 12：钉钉双端登录与四角色**。开工先实现服务端会话、企业身份映射、待授权/禁用状态和角色管理，再接入钉钉电脑端免登与浏览器网页授权；真实双端验收依赖目标企业配置、HTTPS 回调域名和测试成员资料，凭据只放部署环境。

## 路由体验修复 · 2026-09-14

状态：专项修复完成。Node 24.18.1 下前端 85/85 测试、类型检查和构建通过，浏览器 mock 回归及独立 Stage 1/2 审查通过。证据见 `output/route-ux-validation.md`、`output/route-ux-fix-review.md`；仅覆盖本专项，不改变既有其他 Phase 的验收状态。

依据 Product-Spec 第 5 节本日修复确认，按以下顺序执行并独立验收：
1. 任务详情与 query 双向一致，列表条件随 URL 恢复；验收打开/切换/关闭/删除/刷新/前进后退及旧 taskId 链接。
2. 成品详情地址定位、归档后直达及成品回源；验收来源不可用仍保留归档下载、筛选恢复与清除。
3. 三类新建入口、准确的功能文案及可见无权限反馈；验收实际目标和提示一致。
4. 类型检查、单测、构建、浏览器功能验证与独立两阶段专项审查。未修改既有 Phase 12–14 进度，不宣称真实钉钉或全项目上线验收。

## 品牌接入任务 · 2026-09-14

依据 Product-Spec「品牌确认」及 Design-Brief「品牌标识定稿方向」，用户已确认采用恒鑫智图方案。本任务独立于既有 Phase 进度。

1. 固定设计与素材：归档认可稿，产出可编辑 SVG、文字转路径横版、透明 PNG、favicon 与应用图标。完成标准：资源可独立使用，颜色/轮廓一致，有使用说明和预览。
2. 接入既有品牌位置：共享 ArtLogo、系统名称、登录页、启动状态、页头及浏览器元信息。完成标准：使用「恒鑫智图」「前海恒鑫」「京东业务生图」，沿用原 Art 布局与业务主题。
3. 验证与独立审查：运行前端类型检查、单测及构建，在本地检查登录、侧栏展开/折叠、浅深背景和小尺寸标识。完成标准：证据明确区分本地预览与用户正在使用的服务，独立两阶段审查通过；不据此改变其他 Phase 的验收状态。

完成记录（2026-09-14）：三项已完成。资源包位于 `hengxin-smart-image/branding/恒鑫智图-品牌资源.zip`；前端类型检查通过、79/79 单测通过、最终构建通过，独立两阶段审查 PASS，日常 3008 开发服务已只读确认新品牌展示。证据见 [品牌验证](hengxin-smart-image/docs/BRAND-IDENTITY-VALIDATION.md) 与 [独立审查](hengxin-smart-image/docs/BRAND-IDENTITY-REVIEW.md)。本次未部署生产或改变既有 Phase 结论。

> 版本 v1.21 · 2026-09-16。依据 Product-Spec.md v0.24、Design-Brief.md 和用户认可的现有原型。
> 当前状态：Phase 1–11A 已按历史范围验收；12.1 已实现并审查通过；12.2 双端授权代码及钉钉容器免登修复已部署，真实双端业务验收未完成；13.1–13.3 已部署到 VPS 开发测试环境，真实角色联调待验收；14.1 VPS 与 HTTPS 已部署，三类真实 Skill、恢复演练和容量验收未完成。

## 1. 开发方向与已有成果

前端已将认可的页面、组件和导航承接到 `hengxin-smart-image/frontend/`，保留图片处理一级菜单及替换壁纸、替换商品、替换文字三个二级菜单，以及任务中心、模板库、成品库。当前正式前端是视觉和交互基准。后端确定为 Python FastAPI + PostgreSQL，图片与 Skill 包存入 MinIO。四角色及钉钉双端接入详见 Product-Spec.md 第 13 节；钉钉电脑端和浏览器共用同一前端。设计与运营同权限已确认；主管查看全员任务及统计、模板免审批直接使用、全员查看/删除模板任务成品、编辑全员模板及返工/归档全员任务均已确认。

下表保留前端承接时的状态及当时后端待接内容（历史，不作为当前待办；最新状态见顶部交接节）；前端源码路径相对于 `hengxin-smart-image/frontend/src/`。各阶段的“关键文件”是交付规划，未来文件尚未创建不算缺失。

| 已有内容 | 当前状态 | 后端阶段需要完成 |
|---|---|---|
| ArtSidebarMenu、ArtHeaderBar、ArtWorkTab、ArtPageContent、ArtTable、主题 | 已承接到正式前端 | 接入真实身份和授权 |
| `views/hengxin/components/CreateTask.vue` 及三个页面包装组件 | 上传、模板选择、表单和异常交互已通过前端验收 | 真实文件上传、模板加载和任务受理 |
| Templates.vue、Tasks.vue、TaskDetail.vue、Archive.vue | 分页、错误状态、图片版本和归档交互已完成 | 持久化业务接口与版本关联 |
| `views/hengxin/model.ts`、`api/hengxin/` | 已分离内存 mock 与 HTTP 适配，不再使用原型 localStorage 业务库 | 后端按契约接入；生产继续禁止回退模拟数据 |
| `views/auth/dingtalk-login.vue` 及管理页面 | 登录状态、四角色视图和管理交互已完成前端验证 | Phase 6 建可信开发身份，Phase 12/13 接真实认证、授权和管理接口 |
| `views/hengxin/download.ts` | 示例图片和 ZIP 下载已完成前端验证 | 授权文件下载与服务端 ZIP |
| `docs/FRAMEWORK-DEMO-README.md` | 框架 Demo 的运行与验收说明 | 仅记录 Demo 边界，正式源码在 frontend |

前端阶段已将原型源码承接到 `hengxin-smart-image/frontend/`；Phase 5 已建立 `hengxin-smart-image/backend/` 和 `hengxin-smart-image/infra/`；整个工程沿用当前根 Git 仓库。复制时排除 node_modules、dist、缓存、演示资料，重新按锁文件安装依赖。旧原型目录已清理，正式前端成为唯一业务维护源。

## 2. 本机 Docker 检查及复用方案

2026-09-08 只读执行 docker ps、定向 inspect 和容器版本命令；没有读取或输出环境凭据，没有修改容器、数据库和存储桶。

| 实际容器 | 实际版本 / 状态 | 端口与持久化 |
|---|---|---|
| it-project-console-postgres-1 | PostgreSQL 16.15，healthy | 127.0.0.1:55432；it-project-console_postgres-data |
| it-project-console-minio-1 | RELEASE.2025-09-07T16-13-09Z，healthy | API 59000，控制台 59001，均绑定 127.0.0.1；it-project-console_minio-data |
| hengxin-smartmail-uat-api-1 | Python 3.12.10、FastAPI 0.139.2、SQLAlchemy 2.0.51、Pydantic 2.13.4、Uvicorn 0.35.0，healthy | 参考 API/Worker 分离方式 |
| hengxin-smartmail-uat-worker-1 等 | API 同源镜像，Celery 5.6.3 | 已有按队列拆 Worker 的先例，本项目初期只需一个生成 Worker |
| hengxin-smartmail-uat-redis-1 | 镜像 redis:8.8-alpine，healthy | Docker 内部 6379，无主机端口 |

配置参考：`D:/Work_Project/hengxin-devhub/it-project-console/compose.yaml`、`D:/Work_Project/hengxin-smartmail/infra/compose.yaml`。前者已固定镜像 digest、健康检查和命名卷，可沿用方式。

默认采用独立 Compose 项目 `hengxin-smart-image`，复用已缓存的镜像版本和配置模式；不复用其他业务的数据卷、库表、账号或 bucket。理由是各项目可独立启停、迁移和备份。若后续指定共用实例，则创建专用数据库、账号和私有 bucket 后连接，不混用业务数据。

本地计划端口：前端 3008、API 8008、PG 55433、MinIO 59002/59003；仅为分配方案，启动前检查占用。Redis 仅内部网络可见。框架 Demo 使用 3010，启动前检查占用。

## 3. 技术栈和执行架构

| 层级 | 选定技术与版本基线 | 依据 |
|---|---|---|
| 前端 | Vue 3.5.22、Element Plus 2.11.4、Vite 7.1.7、TypeScript 5.6.3 | 当前 pnpm-lock.yaml 的实际锁定版本；优先复用，不为规划升级主版本 |
| 前端运行与包管理 | Node.js 24 LTS、pnpm 10.x | Node 官方 LTS；已有 lockfileVersion 9。Phase 1 固定前端工具补丁版本 |
| API | Python 3.12、FastAPI 0.139.2、Pydantic 2.13.4、Uvicorn 0.35.0 | 本机已运行组合；用 uv 锁定依赖，不宣称这些都是最新版本 |
| 数据层 | PostgreSQL 16.15、SQLAlchemy 2.0.51、Alembic 1.x、psycopg 3.x | 优先匹配本机可用 PG 与 ORM；PG 16 仍受支持 |
| 存储 | MinIO RELEASE.2025-09-07T16-13-09Z，Python minio SDK 7.x | 匹配本机固定镜像 digest，使用标准对象 API |
| 后台执行 | Celery 5.6.3 + Redis 8.8-alpine | 复用现有 Python 项目技术路线；Redis 只承担消息，业务状态以 PG 为准 |
| AI 适配 | Linux Codex CLI 非交互执行，版本单独固定 | 通过适配层封装 CLI，具体二进制版本在 Phase 9 实机验证后锁定 |
| 部署 | Ubuntu 24.04 x86_64、Docker Compose、Nginx | 单机 API/Worker 分离，后续按资源实测扩执行进程 |

新依赖的补丁版本及镜像 digest 在对应阶段首次锁文件生成时固定并验证。现有版本为复用基线，不批量升级；开工和发布前检查兼容性与已知漏洞，必要修复升级需回归已有页面。

```mermaid
flowchart LR
  UI[现有 Vue 前端] --> API[FastAPI 接口与鉴权]
  API -->|同一事务保存任务、轮次和待发消息| PG[(PostgreSQL 业务状态)]
  API --> M[(MinIO 私有图片与 Skill 包)]
  PG -->|读取事务内保存的待发消息| O[Outbox 派发器]
  O --> Q[Redis / Celery 队列]
  Q --> W[Python Worker]
  W --> PG
  W <--> M
  W --> CLI[任务隔离目录内的 Codex CLI]
  CLI --> W
```

已确认异步执行：首次生成和返工接口完成校验、持久保存任务/轮次与 outbox 后返回 HTTP 202、任务 ID 和轮次 ID，不在请求中启动或等待 CLI。独立 Celery Worker 消费任务并分轮启动 CLI，完成后退出该 CLI 进程；FastAPI 和 Worker 服务常驻。仅使用 async def 或 Web 进程内后台协程不满足持久异步要求。前端先用轮询读取 PG 中的真实状态，默认执行中每 3 秒、其他状态每 10 秒，离开页面停止轮询。无可靠百分比时只展示排队、执行、收集结果等阶段。

Phase 3 前端阶段的轮询频率为任务列表每 4 秒、打开的详情每 3 秒，离开页面或关闭详情即停止；上述按执行状态采用 3/10 秒的策略在 Phase 8 接入真实后台状态时实现。

Worker 下载本轮输入与固定 Skill 版本到隔离目录，启动 CLI，收集并校验输出，上传 MinIO，最后提交 PG 图片版本。用对象键和校验和记录文件，数据库不保存永久预签名 URL；预览/下载经 API 校验权限后提供短期签名地址。

初始生成并发已确认从 1 起步，更高上限需实测后配置。20/100 是使用人数，不是 CLI 并发数；服务器基础资源已检查，带宽和负载容量未压测，不承诺容量。Phase9真实执行采用Linux原生Celery Worker和CLI，不能把Windows原生Worker测试当作Ubuntu验收。

会话规则（2026-09-09 已确认）：按业务任务分配，任务 A 首次生成和后续单张/整套返工均使用会话 A；同一运营创建任务 B 时新建会话 B。归档是后端操作，不调用 CLI。保留输入快照、会话 ID 与图片版本等基础记录，不引入复杂上下文管理。

### 3.1 会话生命周期与并发实施约束

业务规则以 Product-Spec 第 9.1–9.2 节为准。本次只规划实现，Phase 5 的短时测试队列不能直接作为真实 CLI 的并发保障。

- Phase 8 用 PG 事务、唯一约束与条件更新落实请求幂等、任务级执行互斥和轮次认领；业务锁只在短事务中持有，CLI/文件处理在事务外执行。多个 Worker 并发验证不能通过全局并发固定为 1 或 Python 线程锁替代。
- Phase 8 冻结内部执行状态与 API 操作资格，Phase 9 接入实际进程、执行代次/租约和不确定状态对账；租约过期不直接释放同任务执行权。核实旧执行停止及已有结果后，才允许按既定重试规则重新执行。
- Phase 9 保证执行环境不能跨任务读取或修改会话材料、输入、输出及临时文件，并将临时轮次输入/输出目录与持久会话材料分开，按任务映射明确 session ID；每轮进程结束退出，返工重新启动并续接原会话。需要返工的任务不使用 ephemeral 会话；原会话不能恢复时失败并保留旧结果。
- 取消、最终图片版本提交和当前版本切换共同校验任务/轮次有效性及当前认领凭证；删除或旧执行者的迟到结果不得写回。Phase 11 的回收不能清理运行中或仍可返工任务的会话材料，保留时长仍按 PRD 第 11 节管理。

早期隔离方案调研见 [Codex CLI 多任务并发与隔离评估](hengxin-smart-image/docs/CODEX-CLI-ISOLATION-ASSESSMENT.md)。Phase 9 已选用 Linux 原生 Worker 与受控 Bubblewrap，每任务独立持久 home、每轮独立 work/control；实际环境与实机证据见 [CODEX-EXECUTION.md](hengxin-smart-image/docs/CODEX-EXECUTION.md) 和 [PHASE9-VALIDATION.md](hengxin-smart-image/docs/PHASE9-VALIDATION.md)。每轮独立 Docker 容器属于早期研究建议，不能作为当前实现说明；任务之间必须隔离的已确认要求不变。

## 4. 业务默认方案与阶段入口

以下引用 PRD 第 11、13 节的阶段入口；标注已确认的事项不重复确认，其余具体建议保留未确认状态；进入相关阶段前集中确认对应一行，不能把本文建议当成用户已批准。工程骨架与接口约定可先进行。

| PRD 问题 | 计划采用的建议 | 进入阶段 |
|---|---|---|
| Q-001 上传规格 | 已确认 JPG/PNG/WebP，单文件 10 MiB，每组最多 20 张；模板输出数跟随有序模板图，文字输出数跟随输入图。建议不主动缩放；真实输出尺寸和格式兼容仍待联调 | 前端 Phase 2；后端 Phase 6/7 |
| Q-004 账号与权限 | 钉钉双端登录与四角色已确认；超管绑定成员角色；主管查看全员任务/统计，模板无需审批，全员查看/删除三类资源、编辑全员模板、返工和归档全员任务 | 前端 Phase 2–4 实现已确认规则；Phase 12 验证真实权限 |
| Q-002 Skill 管理 | 已确认仅超级管理员上传、安装、维护和启停；其他角色只绑定已发布版本。专用优先、未指定按模块默认解析，保存冻结版本；无可用版本存草稿已确认 | 前端 Phase 4；后端 Phase 7 |
| Q-008 钉钉配置 | 企业内部应用、可见范围、接口权限、HTTPS 域名/回调及初始超级管理员成员 userId 列表，见 PRD 第 13 节 | Phase 12；Phase 14 双端回归 |
| Q-003 文字输入 | 已确认：上传图片 + 自然语言修改要求，任务名称必填、SKU 可选，不增加排版编辑器 | 前端 Phase 2；后端 Phase 8 |
| Q-007 历史与归档 | 同任务整套/单张返工互斥已确认；旧版本保留、单张下载和整套 ZIP、全套完整后归档不可变快照及相同版本归档幂等仍按建议默认管理 | 前端 Phase 3；后端 Phase 10/11 |
| Q-004 删除保留 | 已确认删除失效执行且保护历史引用；回收站形式、30 天回收及临时素材清理时限仍是待确认建议 | Phase 11 |
| Q-005 服务器资源 | 部署前采集硬件及剩余空间；建议从并发 1 起步压测，实际运行上限待确认，不按用户人数猜算 | Phase 14 |
| Q-006 CLI 身份和运行限制 | 已确认 codex 专用身份、并发 1、单轮 60 分钟硬超时、自动重跑 0；记录可用 usage，账号预算仍需设置 | Phase 9/13/14 |

尚无三个真实 Skill 不阻塞 Phase 1–8 和使用测试执行器的平台功能；Phase 9 的 CLI 传输实测需要可用 CLI 认证，Phase 14 的真实业务验收需要三个 Skill 及其工具依赖。模拟输出始终标识为测试，生产配置禁止选择模拟执行器。图片效果评测、Skill 编写不在本计划工作量中。

## 5. 阶段总览与依赖

先完成前端，再开发后端；前端各组完成即交付可浏览预览，不等到全部完成才展示。下列前四阶段不创建后端应用、数据库迁移或服务容器。先定义前端数据契约不等于开发后端。

| 阶段 | 交付结果 | 依赖 | 状态 |
|---|---|---|---|
| Phase 1 前端承接 | 原有布局、组件、路由及模拟接口契约 | 原型源码 | 已完成 |
| Phase 2 创建与模板页面 | 三类处理、素材交互和模板维护 | 1 | 已验收 |
| Phase 3 任务与成品页面 | 任务详情、返工、版本、下载及归档交互 | 2 | 已验收 |
| Phase 4 管理及登录页面 | 五个管理页面、四角色视图、登录状态；全部前端验收 | 3 | 已验收 |
| Phase 5 后端基础 | FastAPI、PG、MinIO、Redis、Worker/outbox | 4 | 已验收（用户授权继续 Phase 6） |
| Phase 6 文件与用户归属 | 真实上传下载及后端测试身份 | 5 | 已验收 |
| Phase 7 模板与 Skill | 模板持久化、Skill 版本及安装 | 6 | 已验收（用户授权继续 Phase 8） |
| Phase 8 任务与队列 | 真实异步提交、任务状态 | 7 | 已验收（用户授权继续） |
| Phase 9 Codex 执行 | 独立会话、结果回传及调用记录 | 8 + CLI 环境 | 已验收（用户授权继续） |
| Phase 10 返工 | 同会话整套/单张修改、版本持久化 | 8；真实执行依赖 9 | 已验收（用户授权继续 Phase 11） |
| Phase 11 归档 | 真实下载、快照与生命周期 | 10 | 已按历史范围验收 |
| Phase 11A 开发机 CLI 真实联调 | 开发机真实生成、会话返工、归档及双任务并行验证 | 9–11 + 本机 CLI 认证/隔离环境 + 实际业务 Skill | 2026-09-14 用户确认并发 2 验收通过，保留尺寸例外 |
| Phase 12 钉钉与权限 | 12.1 身份会话与用户角色接口；12.2 双端认证、真实授权及业务回归 | 6–11、11A + 钉钉应用 | 12.1 已完成；12.2 已部署，待通讯录范围及双端验收 |
| Phase 13 管理接口 | 真实统计、监控、配置及页面联调 | 9、12 | 13.1–13.3 已部署待真实角色联调 |
| Phase 14 联调部署 | 三种真实 Skill 闭环及 Ubuntu 上线验收 | 11–13 + 真实 Skill | 14.1 VPS 已部署；真实 Skill 冒烟待治理后复验 |

主线 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 11A → 12 → 13 → 14。前端完成以页面、交互和状态验收为准；真实生成、存储、服务端权限和监控仍须后端阶段逐项验收。CLI 环境未就绪时，10/11 可使用测试执行器推进，但不能标为真实业务完成。

所有路径相对于仓库根目录；以下均为计划创建或承接的文件。

## Phase 1：前端工程承接与接口契约

执行拆分（2026-09-09）：
1. 工程承接：排除依赖 junction、构建产物和实际环境文件，复制源码及许可；固定本机 Node/pnpm，独立安装通过。
2. 服务边界：提取契约类型，集中模拟种子、状态与计时器，页面通过服务调用读写；原型存储不迁入正式工程。
3. 模式隔离：模拟预览明确标识，真实模式不导入演示身份或回退模拟数据，断连可重试。
4. 验收：独立审查、服务边界测试、严格类型检查、生产构建与浏览器主流程/故障回归；记录证据并交付预览。

**交付内容**：
- 将现有原型源码承接为正式前端，保留 art-design-pro 布局、组件库、主题及已认可导航，不删现有可复用组件。
- 定义用户、文件、模板、Skill、任务、轮次、图片版本、归档和管理数据类型，以及分页、错误、受理 ID 和状态契约。
- 把模拟接口集中隔离，页面通过同一服务接口访问；本地预览明确标识模拟数据，正式模式不自动退回模拟数据。

**关键文件**：
- `hengxin-smart-image/frontend/src/main.ts`、`hengxin-smart-image/frontend/src/router/modules/index.ts`：入口和导航承接。
- `hengxin-smart-image/frontend/src/types/hengxin.ts`、`hengxin-smart-image/frontend/src/api/hengxin/client.ts`：数据类型与服务边界。
- `hengxin-smart-image/frontend/src/api/hengxin/mock.ts`、`hengxin-smart-image/frontend/src/views/hengxin/model.ts`：集中模拟适配与旧模拟层迁移。
- `hengxin-smart-image/docs/API-CONTRACT.md`：接口字段、状态及错误约定，后端阶段按此实现并核对 OpenAPI。

**验收标准**：不启动后端即可运行前端；页面布局与认可视觉基准一致，组件保留；干净安装、类型检查、生产构建通过；模拟模式明确可识别，真实模式断连显示错误。交付首个前端预览地址，后续以正式前端回归。

Phase 1 验证记录：`hengxin-smart-image/docs/PHASE1-VALIDATION.md`；两阶段审查均 PASS，见 `PHASE1-REVIEW.md`。前端预览 `http://127.0.0.1:3008/`。继承依赖审计风险列为上线前整改，本阶段不作可发布声明。

## Phase 2：三类图片处理与模板库前端

执行拆分与完成标准（2026-09-09）：
1. 服务契约：独立模板分页、可用 Skill 目录、素材上传适配；版本绑定、文件引用和失败场景可测试，真实模式无模拟回退。
2. 三类创建页：统一素材预览/校验/移除/失败重试；名称、SKU、自然语言与模板/Skill 正确传递，提交期间不可重复操作，空态和加载错误可恢复。
3. 模板库：分页搜索与排序、创建编辑、图片排序、版本展示、仅绑定可用 Skill，无 Skill 可存草稿、保存失败保留输入，全员删除有确认，历史任务快照不变。
4. 交付：两阶段独立审查、服务与故障测试、严格类型及生产构建、浏览器主流程和视觉回归。


**交付内容**：
- 完成替换壁纸、替换商品、替换文字独立入口的表单、选模板、本地素材选择/预览/移除及提交交互。
- 完成模板创建、编辑、搜索、排序、版本展示、绑定可用 Skill 及无 Skill 草稿状态；保存后直接可用，无主管发布入口；全员可查看和删除模板。
- 覆盖空状态、校验失败、提交中、模拟上传失败及重试；遵循 PRD 建议状态，不把待确认细则升级为定案。

**关键文件**：
- `hengxin-smart-image/frontend/src/views/hengxin/components/CreateTask.vue`、`hengxin-smart-image/frontend/src/views/hengxin/components/Templates.vue`。
- `hengxin-smart-image/frontend/src/api/templates.ts`、`hengxin-smart-image/frontend/src/api/skills.ts`、`hengxin-smart-image/frontend/src/api/hengxin/http.ts`：对接统一模拟服务与契约。

**验收标准**：三个入口和模板操作可完整演示；文字不强制模板，类型绑定正确，重复提交有保护；素材可本地预览，模拟上传不声称已存入 MinIO。类型检查、构建及浏览器交互通过，交付可浏览页面。

## Phase 3：任务、返工与成品库前端

执行拆分（2026-09-09）：1. 任务分页/详情/删除与可靠状态；2. 有序结果槽、轮次和历史版本，串行返工失败保留旧图；3. 成品分页/预览/删除、快照归档及单图/整套下载；4. 独立审查、服务与浏览器故障测试、严格类型和构建、Art 视觉核对。完成标准以本节验收标准及 PHASE3-VALIDATION 为准。

**交付内容**：
- 完成全员可查看的任务列表、筛选、详情、删除及图片预览，覆盖排队/执行/成功/部分失败/失败各状态。
- 完成整套和单张意见、返工状态、历史版本切换；通过模拟场景演示失败保留旧结果。
- 完成单图与整套下载入口、归档及全员成品搜索/预览/删除；演示下载使用示例文件，不标为真实生成结果。

**关键文件**：
- `hengxin-smart-image/frontend/src/views/hengxin/components/Tasks.vue`、`hengxin-smart-image/frontend/src/views/hengxin/components/TaskDetail.vue`、`hengxin-smart-image/frontend/src/views/hengxin/components/Archive.vue`。
- `hengxin-smart-image/frontend/src/api/tasks.ts`、`hengxin-smart-image/frontend/src/api/revisions.ts`、`hengxin-smart-image/frontend/src/api/archives.ts`、`hengxin-smart-image/frontend/src/views/hengxin/download.ts`。

**验收标准**：模拟完成创建→结果→单张/整套返工→下载→归档全流程；单图返工显示仅目标图变化，失败保持旧图，部分失败不可整套归档；类型检查、构建、浏览器交互通过并交付预览。实际异步持久化与 CLI 会话留待后端验证。

## Phase 4：管理中心、角色视图与登录页面

执行拆分：1. 独立管理接口、类型守卫及模拟权限/故障，完成标准为四角色范围和参数校验可测试；2. 钉钉登录状态与角色菜单，完成标准为匿名/失效/待授权/禁用均不能进入业务，模拟角色切换不泄漏到真实模式；3. 五个管理页面，完成标准为查询、编辑、失败重试、安装状态及审计有可用交互；4. 独立两阶段审查、全量测试与构建、隔离浏览器角色/故障及旧流程回归、视觉对照。建议默认仅用于前端预览，真实授权/配置上限在后端阶段落实。

2026-09-09 权限确认：四角色均可编辑全员模板、返工及归档全员任务，保留实际操作者；Phase 4 前端及 Phase 12 后端跨创建人验收同步采用此规则，其他管理权限不变。

**交付内容**：
- 基于原 Art 组件完成调用统计、执行监控、用户与角色、Skill 管理、系统配置五个页面及异常/空状态。
- 通过仅模拟模式可用的角色预览验证四角色菜单和操作视图，设计与运营一致，Skill 维护仅超级管理员可见；不把前端隐藏入口当服务端授权。
- 完成钉钉登录入口、授权中/失败/过期/待授权状态，先模拟状态，不接真实 SDK 或授权码交换。
- 整体走查全部前端页面，修复交互及视觉问题；统一接口契约与模拟场景，记录前端验收结果后进入后端阶段。

**关键文件**：
- `hengxin-smart-image/frontend/src/views/hengxin/admin/usage.vue`、`hengxin-smart-image/frontend/src/views/hengxin/admin/monitor.vue`、`hengxin-smart-image/frontend/src/views/hengxin/admin/users.vue`。
- `hengxin-smart-image/frontend/src/views/hengxin/admin/skills.vue`、`hengxin-smart-image/frontend/src/views/hengxin/admin/settings.vue`。
- `hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue`、`hengxin-smart-image/frontend/src/api/hengxin/logout.ts`、`hengxin-smart-image/frontend/src/api/management.ts`。

**验收标准**：PRD 第 5 节全部页面及状态有前端演示；四角色视图符合已确认规则；统计/健康明确模拟，usage 缺失和空闲分别表达；无后台服务也能体验完整前端。类型检查、构建、浏览器流程和视觉对照通过，交付完整预览。钉钉双端实机认证与容器兼容性在 Phase 12/14 验收。

后端阶段涉及的前端文件均为接入真实接口和回归已有页面，不重新制作布局和交互。

## Phase 5：后端基础工程与契约落地

**交付内容**：
- 在全部前端完成后搭建后端；按 Phase 1–4 的接口契约实现响应结构，核对 OpenAPI 与前端类型，保留已有页面。
- 建立 FastAPI 应用、环境配置、OpenAPI 契约、数据库迁移入口和 MinIO 连通探针；规划接口 `/api/v1`。
- 建立独立 Compose 与锁文件，沿用现有镜像固定和健康检查方式；PG、Redis、MinIO 采用新命名卷。同步建立 Celery Worker 与通用 outbox 基础，以支持 Phase 7 的异步 Skill 安装。

**关键文件**：
- `hengxin-smart-image/frontend/src/main.ts`、`hengxin-smart-image/frontend/src/router/modules/index.ts`：核对已有入口和接口配置。
- `hengxin-smart-image/frontend/src/views/hengxin/model.ts`：准备切换已有模拟/真实服务适配。
- `hengxin-smart-image/backend/app/main.py`、`hengxin-smart-image/backend/app/core/config.py`、`hengxin-smart-image/backend/app/db/session.py`：应用、配置和数据库连接。
- `hengxin-smart-image/backend/app/worker/celery_app.py`、`hengxin-smart-image/backend/app/worker/outbox.py`：通用队列与可靠派发基础。
- `hengxin-smart-image/infra/compose.yaml`、`hengxin-smart-image/docs/API-CONTRACT.md`：服务组合与错误/分页/幂等契约。

**验收标准**：干净依赖安装、前端构建、后端启动及健康检查通过；已有前端页面无回归；框架 Demo 可独立运行，其他项目卷不被挂载。通用测试作业完成持久派发、Worker 执行及重复投递保护；本阶段不把演示生成算作正式能力。

## Phase 6：文件存储与用户归属基础

**交付内容**：
- 建立用户表、统一当前操作者接口和基础权限策略，资源与操作记录使用稳定用户 ID（用于归属和审计，不限制已确认的全员查看/删除）；本地开发通过服务端配置固定测试身份联调，自动化测试可注入四角色身份。
- 实现素材上传、服务端解码校验、文件元数据入库、MinIO 私有对象与受控预览下载；建立共用逻辑删除记录，供模板/任务/成品阶段使用；上传失败保留表单可重试。
- 开发身份仅限本地开发配置，前端不传可信角色或任意用户 ID；生产配置启用开发身份时启动失败。Phase 12 再接真实钉钉身份及已有角色管理页面的接口。

**关键文件**：
- `hengxin-smart-image/backend/app/modules/auth/dependencies.py`、`hengxin-smart-image/backend/app/modules/auth/permissions.py`：当前操作者接口及基础权限策略。
- `hengxin-smart-image/backend/app/modules/auth/dev_identity.py`：受环境限制的固定测试身份。
- `hengxin-smart-image/backend/app/modules/files/deletions.py`：共用逻辑删除记录及操作者留痕。
- `hengxin-smart-image/backend/app/modules/files/router.py`、`hengxin-smart-image/backend/app/storage/minio_store.py`：文件入口、所有者记录和对象存储。
- `hengxin-smart-image/frontend/src/api/hengxin/logout.ts`、`hengxin-smart-image/frontend/src/api/hengxin/http.ts`、`hengxin-smart-image/frontend/src/views/hengxin/components/CreateTask.vue`：开发身份接口及真实上传。

**验收标准**：损坏/超限图片拒绝，刷新和重启后素材仍在；文件及操作留存测试用户归属；不接受客户端伪造身份；生产启用开发身份时拒绝启动。通过身份注入测试基础角色规则和跨用户共享资源访问（有效用户可访问，匿名/禁用账号拒绝），前后端编译、迁移及上传下载通过。本阶段不要求钉钉配置，不将测试身份算作真实登录验收。

## Phase 7：模板与 Skill 版本管理

2026-09-09交付：模板与Skill真实接口、版本历史、模块默认、Linux安装和通用队列已接入；后端108项/前端41项测试、类型编译、构建、隔离API/Worker/浏览器和旧队列回归通过。真实业务Skill及图片生成仍属于后续。执行拆分及审查闭环见docs/PHASE7-PLAN.md、PHASE7-REVIEW.md、PHASE7-VALIDATION.md。

**交付内容**：
- 实现模板创建、搜索、排序、编辑、停用、全员逻辑删除及历史版本；保存后直接可用，无审批发布步骤；无 Skill 时可保存草稿。
- 仅超级管理员可上传、安装、更新、启停 Skill 和配置模块默认绑定；其他角色只选已发布版本。异步安装区分上传成功/安装中/可用/失败，安装失败保留旧版，历史任务冻结版本。
- 为安装与后续生成扩展通用作业类型、路由及成功/失败/取消终态；结束的作业停止 outbox 重派，健康运行中的作业不持续堆积重复消息，消息补发与再次执行业务分开记录。
- 保存模板时生成版本并冻结图片顺序，满足条件即成为可用版本；模板更新不改变旧任务引用，不增加审批发布步骤。

**关键文件**：
- `hengxin-smart-image/backend/app/modules/templates/router.py`、`hengxin-smart-image/backend/app/modules/templates/service.py`：模板与版本。
- `hengxin-smart-image/backend/app/modules/skills/router.py`、`hengxin-smart-image/backend/app/modules/skills/package_validator.py`：Skill 管理、ZIP 路径/大小/元数据校验。
- `hengxin-smart-image/backend/app/worker/skill_install.py`：超级管理员触发的异步版本安装和状态记录。
- `hengxin-smart-image/backend/app/models.py`、`hengxin-smart-image/backend/app/worker/outbox.py`、`hengxin-smart-image/backend/migrations/versions/`：将 Phase 5 测试作业关联扩为通用作业类型及终态，保持迁移可回归。
- `hengxin-smart-image/frontend/src/api/templates.ts`、`hengxin-smart-image/frontend/src/api/skills.ts`：业务接口。
- `hengxin-smart-image/frontend/src/views/hengxin/components/Templates.vue`、`hengxin-smart-image/frontend/src/views/hengxin/admin/skills.vue`：模板现有交互与管理表单。

**验收标准**：本阶段通过注入测试身份验证权限，Phase 12 再以真实登录回归：设计主管、设计和运营直接调用 Skill 包上传/安装/启停接口均被拒绝（模板图片上传允许）；管理员异步安装失败不影响旧版；不同类型只能绑定匹配 Skill；缺失可用 Skill 不可提交生成；四角色均能查看和逻辑删除他人模板，保存后无需审批即可选用；删除记录实际操作者；模板 t1 的新版本不更改旧引用；解压拒绝越界路径、符号链接及超限包。构建、迁移和模板浏览器主流程通过。不在此阶段制作业务 Skill。

队列增补验收：安装任务路由正确，成功、永久失败和已完成取消均停止重派；有效认领期间不会持续产生重复消息，Redis 故障后未完成的有效作业仍可恢复。

## Phase 8：任务提交、持久队列与状态

执行拆分及工程边界见 hengxin-smart-image/docs/PHASE8-PLAN.md。仅显式test环境启用fixture结果；本地development无真实执行器时清楚返回503，Phase9再接真实CLI。

**交付内容**：
- 建立供 fixture 和真实 CLI 共用的图片版本及结果持久化模型，再将三个独立入口接入真实任务 API，冻结模板/Skill/素材/要求快照；文字入口不强制套图模板。
- 复用 Phase 5 的 Celery、Redis 和 Phase 7 扩展的通用 PG 事务 outbox 接入生成任务；同事务保存幂等请求、任务/轮次、执行占用和待发消息，数据库保证同任务只有一个未结束轮次，重复消息只允许一个 Worker 原子认领。
- 接入全员任务分页、筛选、详情、逻辑删除与轮询状态；测试环境使用显式 fixture 执行器证明队列闭环。
- 接入持久取消意图、执行状态待核实及操作资格契约，失效认领不能提交版本。前端显示服务端返回的可返工/可重试能力与原因，不只根据“失败”状态开放重试；字段见 API-CONTRACT 并发安全补充。

**关键文件**：
- `hengxin-smart-image/backend/app/modules/tasks/router.py`、`hengxin-smart-image/backend/app/modules/tasks/service.py`：提交及快照。
- `hengxin-smart-image/backend/app/modules/tasks/idempotency.py`、`hengxin-smart-image/backend/app/modules/tasks/claims.py`、`hengxin-smart-image/backend/app/modules/tasks/cancellations.py`：幂等请求、任务级占用、轮次认领、取消及失效条件。
- `hengxin-smart-image/backend/app/worker/celery_app.py`、`hengxin-smart-image/backend/app/worker/jobs.py`、`hengxin-smart-image/backend/app/worker/outbox.py`：消息及认领。
- `hengxin-smart-image/backend/app/modules/tasks/results.py`：通用图片版本及持久化结果入口。
- `hengxin-smart-image/backend/app/execution/fixture_runner.py`：仅测试的确定性执行器。
- `hengxin-smart-image/frontend/src/api/tasks.ts`、`hengxin-smart-image/frontend/src/views/hengxin/components/CreateTask.vue`、`hengxin-smart-image/frontend/src/views/hengxin/components/Tasks.vue`：提交及真实状态。
- `hengxin-smart-image/frontend/src/types/hengxin.ts`、`hengxin-smart-image/frontend/src/api/hengxin/validate.ts`、`hengxin-smart-image/backend/app/contracts/business.py`、`hengxin-smart-image/frontend/src/views/hengxin/components/TaskDetail.vue`：幂等与操作资格契约、响应校验、忙碌/待核实提示，适配已完成前端。

**验收标准**：四角色均能查看和逻辑删除他人任务并留存操作者；重复提交同一请求只有一条任务；并发限额 1 时第二条排队；关闭页面不终止后台任务；Redis 短暂不可用不丢已入库任务；重复消息不能重复发布结果。使用尚未结束的受控作业验证提交已返回 202 和任务 ID，状态可独立查询；Web 请求不得等待作业结束。fixture 明确展示测试来源。前后端编译、迁移和队列故障验证通过。

并发增补验收：按 PRD AC-010、021–023、025，用并发 HTTP 请求和两个独立 Worker 验证同键重放、同键异内容、同任务不同新请求互斥、重复消息单次启动、取消和旧结果屏障；Phase 8 使用受控执行器及内部轮次服务，Phase 10 再验证用户返工入口。任务执行期间可查询状态和写取消意图；状态待核实时不允许新执行。不得以单 Worker 或内存锁替代多进程争用验证。

## Phase 9：Codex CLI 独立会话与输出接入

2026-09-23 生产维护追加：统一服务器入口和生产执行器至最新稳定版0.156.1。步骤与验收：官方发布包校验；精确路径沙箱许可及隔离调用；空闲时切换 Worker；核对实际进程版本、认证、模型响应及旧会话续接。详见 hengxin-smart-image/docs/CODEX-UPGRADE-20260923.md。历史验收证据保留原版本。

2026-09-10 用户授权实施；执行身份沿用专用 codex，生成并发1，单轮硬上限60分钟，失败不自动重跑。CLI实测版本0.153.4。详细方案及证据见 docs/PHASE9-PLAN.md（位于项目代码子目录）。

**交付内容**：
- 建立 runner 适配层，下载冻结输入及指定 Skill 版本到每任务/轮次独立目录，以参数数组和 stdin 调用 CLI；不拼接用户内容为 shell 命令。
- 解析 JSONL 事件并保存明确会话 ID 及任务唯一关联；新业务任务新会话，返工只按记录的 ID 续接，禁止使用共享的 `--last`。临时轮次目录与受保护的持久会话存储分开，每轮进程退出不删除会话材料，不使用 ephemeral 模式。会话不可恢复时明确失败并保留旧结果；第一期不实现自动重建会话、上下文摘要或历史要求整理。
- 校验输出清单、图片解码、模板 slot 对应关系和目录边界，上传 MinIO 后落库；实现超时终止、进程退出与不确定状态对账。
- 记录每次实际 CLI attempt、操作者、轮次、耗时及可用 usage（去重且缺失为 null），采集 Worker 心跳、依赖健康和检查时间，供 Phase 13 使用。

**关键文件**：
- `hengxin-smart-image/backend/app/execution/codex_runner.py`、`hengxin-smart-image/backend/app/execution/workspace.py`：进程和任务目录。
- `hengxin-smart-image/backend/app/execution/events.py`、`hengxin-smart-image/backend/app/execution/output_collector.py`：事件、结果清单和图片校验。
- `hengxin-smart-image/backend/app/worker/reconcile.py`：重启恢复、租约和过期轮次写入屏障。
- `hengxin-smart-image/backend/app/worker/health.py`：执行端状态采集。
- `hengxin-smart-image/backend/app/modules/tasks/attempts.py`：每次实际 CLI 执行事实及 usage 去重。
- `hengxin-smart-image/infra/hengxin-worker.service.example`、`hengxin-smart-image/docs/CODEX-EXECUTION.md`：Linux 原生Worker与外层Bubblewrap任务隔离、固定CLI版本及实机证据；API/PG/Redis/MinIO保持Compose部署。
- `hengxin-smart-image/infra/compose.yaml`：配置独立会话持久存储及临时轮次空间，记录固定 CLI 版本恢复所需的最小材料；禁止通过共享可写会话目录绕过任务隔离。

**验收标准**：在 Linux 上用已知测试图片执行无效果要求的传输冒烟；两任务会话 ID 不同，分别验证读取和修改另一任务材料均被拒绝；无文件的文本成功不能标图片成功；越界输出拒绝；超时停止整个进程组；重启后不盲目重跑可能已收费的轮次。保留 CLI 版本、认证状态结果及事件证据，不记录凭据。真实三类 Skill 效果不作为此阶段验收。

生命周期与恢复增补验收：PRD AC-015、021–025 要保留实际 CLI 证据；每轮结束后进程退出，空闲期间不挂起等待用户，Worker 容器重建后能在新轮次目录续接原会话。模拟 CLI 已启动/输出已落盘但 PG 未提交时失联，重复消息、租约过期和人工点击均不能绕过待核实门禁；确认旧进程停止后才能处理恢复或重试。验证排队删除、运行删除、上传后提交前删除及旧执行者迟到，图片当前版本和既有快照引用不被覆盖。此处通过内部轮次服务进行无效果要求的传输/续接冒烟，用户返工入口在 Phase 10、归档完整流程在 Phase 11 回归，真实 Skill 效果验收仍在 Phase 14。

长任务需配置 Redis visibility timeout 高于运行硬上限及收尾时间并留余量，仍以 PG 认领/租约防重复；队列重投不等于再次启动 CLI，不能直接沿用 Phase 5 的 60 秒测试值。执行进程只访问本轮目录及本任务必要会话材料，不授予其他任务文件的读写权限，不挂载其他项目卷、Docker socket 或全局宿主目录；认证和运行工具按最小需要配置。Skill 指定与包隔离可校验，但不能把模型文本中的“已调用”当作真实产出证据。

## Phase 10：整套与单张返工

**交付内容**：
- 接入整套预览、单图查看、修改意见、执行轮次及历史版本展示，沿用当前详情页。
- 返工复用 Phase 8 的幂等、任务执行占用和轮次认领，同任务跨用户的整套/单张/重试请求互斥；固定目标 slot 与输入快照，仅有效执行的新结果成功后切换对应图片当前版本。
- 返工同样通过持久队列异步执行，提交返回 202、任务 ID 与轮次 ID，Worker 按原会话 ID 续接。
- 保留失败前旧结果；部分失败可预览已成功图片，整套与单张修改冲突返回明确提示。

**关键文件**：
- `hengxin-smart-image/backend/app/modules/revisions/router.py`、`hengxin-smart-image/backend/app/modules/revisions/service.py`：意见、目标范围和版本事务。
- `hengxin-smart-image/backend/app/modules/tasks/results.py`：结果汇总与部分失败。
- `hengxin-smart-image/frontend/src/api/revisions.ts`、`hengxin-smart-image/frontend/src/views/hengxin/components/TaskDetail.vue`：版本和反馈界面。

**验收标准**：第 N 张返工成功只改变该图的当前版本，其他图对象键及校验和相同；失败保持原图；整套反馈可追溯；连续双击不重复建轮次。返工作业未结束时提交已返回受理标识；关闭页面后继续运行；首次生成和返工会话 ID 一致。fixture 可验证平台状态，实际 CLI 返工证据在 Phase 14 补齐；构建和迁移通过。

多人返工增补验收：按 PRD AC-021，两个不同用户同时提交整套与单张返工只有一个 202，其余新请求返回 409 并保留意见；同一已受理请求的幂等重放返回原标识。排队、运行、收集结果、取消处理及待核实期间均不能另开轮次；跨用户操作记录真实操作者，不能按用户分别加锁而放过同任务争用。

## Phase 11：下载、成品归档与生命周期

2026-09-10 开始实施（用户授权继续）。执行拆分：T11-1 授权单图与服务端流式 ZIP，验收文件内容、鉴权与资源释放；T11-2 归档快照、幂等事务与成品库接入，验收返工不覆盖、搜索筛选及跨用户操作审计；T11-3 引用保护与默认禁用的清理入口，验收运行/可返工会话保护及显式策略下的清理。沿用本节完整套图归档验收规则；保留期限仍未确认，不自动启用回收。最后完成独立审查、全套测试、编译迁移和浏览器闭环。

**交付内容**：
- 实现单张授权下载和服务端流式 ZIP，沿用前端入口；大文件打包避免一次全部读入内存。
- 建立归档快照，接入成品库搜索、筛选、预览和下载；后续返工不覆盖归档对象。
- 实现幂等归档、逻辑删除与引用保护清理；删除模板/任务/归档不连带破坏仍被使用的对象。
- 会话材料清理与任务生命周期关联：只回收按已确认策略可清理、无有效执行且不再支持返工的任务材料；归档操作不直接清理会话，回收与执行/续接竞争时保护有效任务。保留天数不沿用未确认建议自动生效。

**关键文件**：
- `hengxin-smart-image/backend/app/modules/archives/router.py`、`hengxin-smart-image/backend/app/modules/archives/service.py`：归档事务与筛选。
- `hengxin-smart-image/backend/app/modules/files/downloads.py`、`hengxin-smart-image/backend/app/worker/cleanup.py`：ZIP 和垃圾回收。
- `hengxin-smart-image/frontend/src/api/archives.ts`、`hengxin-smart-image/frontend/src/views/hengxin/components/Archive.vue`、`hengxin-smart-image/frontend/src/views/hengxin/download.ts`：成品及下载接入。

**验收标准**：归档后返工，旧归档对象校验和不变；重复点击不增记录；部分失败不能整套归档；移除归档不误删任务文件；四角色均可删除他人归档，删除记录实际操作者且保留引用保护；下载鉴权与 ZIP 内容数量/格式一致；清理与续接同时发生时不删除仍可返工或正在执行的会话材料，保留策略未确认前不启用会话自动清理；构建、迁移及浏览器闭环通过。

## Phase 11A：开发机 Codex CLI 真实联调

**当前日常开发环境（2026-09-11 用户实测后调整）**：`hx-local-test` 已显式启用并发2，实时 Worker 两个消费者及 API/Outbox 配置已核对。此前验收结束“恢复1”是历史状态；通用默认值1和独立验收环境清理规则不变。详见 [本机配置与运行证据](hengxin-smart-image/docs/LOCAL-CODEX-DEVELOPMENT.md)。

**用户确认的本阶段例外（2026-09-11）**：暂时跳过原生输出1254×1254与模板800×800不一致的问题。后续专用联调任务明确豁免像素尺寸一致性，使用真实原生输出继续验证其他链路；不修改既有失败任务、不将未验证项目标为通过、不改变上传Skill或生产规则。下列串行闭环及Skill执行验收按此尺寸例外执行，其余要求保持不变。

2026-09-11 新增，依据 PRD 第 8.3 节。技术验收和独立两阶段审查已通过：Ubuntu 24.04 WSL、CLI 0.153.4、实际壁纸 Skill 1.0.1 完成双图生成、同会话单张/整套返工、重启续接、历史归档和浏览器 ZIP；两个真实任务并行、跨目录隔离、Worker 中断待核实/恢复、重投不重跑、早期取消和超时均有证据。后端最终656项通过、前端79项与构建通过；独立环境已清理；该次记录的日常并发 1 后来已单独改为 2，VPS 仍为 1。结果见 [PHASE11A-CLOSEOUT-RESULTS.md](hengxin-smart-image/docs/PHASE11A-CLOSEOUT-RESULTS.md)，审查见 [PHASE11A-CLOSEOUT-FINAL-REVIEW.md](hengxin-smart-image/docs/PHASE11A-CLOSEOUT-FINAL-REVIEW.md)。历史网络失败记录保留于 [PHASE11A-VALIDATION.md](hengxin-smart-image/docs/PHASE11A-VALIDATION.md)。2026-09-14 用户已确认本阶段通过；商品/文字 Skill 验收仍留 Phase14。本阶段先于 Phase12，不替代生产部署验收。

**交付内容与执行顺序**：

1. **检查开发机执行条件**：核对 CLI 可执行路径、实际版本、认证状态及真实图像工具；检查已上传壁纸 Skill 的包格式、版本与工具依赖。核对当前 Windows 主机的 WSL/Linux、Bubblewrap、目录隔离及与本机 API/数据库/存储的网络连通性。优先复用现有 Linux 适配器；若只有 Windows 原生 CLI，列清隔离和进程管理适配范围并完成等价验证后才启用。输出检查结果，不复制开发者完整 CODEX_HOME，也不输出凭据。
2. **建立可重复启停的真实测试环境**：配置开发机专用 Worker、认证引用、唯一节点名及任务执行目录，明确与容器网络的连接地址。新真实测试环境关闭 fixture；暂停相同队列上的 fixture 消费者或使用独立队列/环境。保留现有测试数据与原执行来源，提供启动、健康检查、停止及回到 fixture 环境的方法；真实执行不可用时明确报错，不静默降级。
3. **用实际素材验证完整业务流程**：以已上传 ecommerce-wallpaper-swap 包和用户提供的模板/素材创建新的 cli 任务，验证真实输出；继续整套与单张返工、历史版本、单图/ZIP 下载及归档后再返工。商品和文字的真实 Skill 具备时按同样流程补测，未提供者在报告中明确列为未验证，留给 Phase 14 完成。不得将既有测试结果改标为 cli。
4. **验证实例管理与双任务并行**：串行闭环通过后，在专用测试配置将生成上限设为 2、提供至少两个执行槽；提交两个不同任务并记录真实 CLI 运行时间重叠、不同 PID/会话/目录和正确图片归属。覆盖同任务返工争用、消息重投、执行超时/取消及 Worker 中断后的待核实保护；恢复时不重复调用可能已计费的轮次。记录 CPU、内存、耗时、错误及可用 usage，测试结束恢复默认并发 1。
5. **整理可复验交付**：补充自动化验证入口与运行说明，完成相关回归、编译、独立两阶段审查和浏览器验收；报告分别列平台通过项、实际 Skill 测试范围、真实并行结果和剩余限制，交用户验收。

**关键文件（按检查结果创建或修改）**：

- `hengxin-smart-image/infra/start_local_codex.ps1`：开发机启动、就绪检查及显式停止入口；使用既定本机运行环境，不隐式安装系统组件。
- `hengxin-smart-image/infra/.env.local-codex.example`：无凭据的本机真实执行配置样例；实际配置保留 Git 忽略。
- `hengxin-smart-image/infra/hengxin-worker.service.example`、`hengxin-smart-image/infra/compose.yaml`：Worker 连接、节点身份与消费者隔离配置。
- `hengxin-smart-image/backend/app/execution/workspace.py`、`process.py`、`codex_runner.py`：仅对检查确认的开发机兼容问题作必要适配，保持目录、会话、进程及发布凭证约束。
- `hengxin-smart-image/backend/app/worker/reconcile.py`：如开发机运行方式影响恢复，补齐节点和精确进程身份核实。
- `hengxin-smart-image/infra/verify_local_codex.py`、`hengxin-smart-image/backend/tests/test_local_codex.py`：真实测试入口与必要的兼容性回归；真实测试显式执行，普通测试不自动消耗模型额度。
- `hengxin-smart-image/docs/LOCAL-CODEX-DEVELOPMENT.md`、`hengxin-smart-image/docs/PHASE11A-VALIDATION.md`：环境核查、启停/恢复方法、测试素材和 Skill 版本、真实执行与资源证据。

**验收标准**：

- 浏览器提交后快速返回受理结果，后台真实 CLI 完成生成，任务 executionSource=cli，sessionId 非空；有实际 attempt、命令版本与可读取的新生成图片，未使用 fixture 输出。
- 不同任务会话与持久目录独立；同任务整套/单张返工沿用原 session ID，目标图产生新版本，单张返工不改其他图，旧归档字节不变。每轮进程结束退出，再次启动可续接原会话。
- 两个不同任务的真实 CLI 执行区间重叠且各自只执行一次，图片归属正确；同任务竞争只有一个新轮次被受理，重复消息不重复启动。无跨任务读写、会话混用或旧凭证结果覆盖。
- 超时/取消停止对应执行进程组；Worker 中断后先核实原进程与产物，未知状态保持门禁。已有归档及可返工会话材料在服务重启后仍可读取/续接。
- 页面真实流程、图片预览和下载可操作；有脱敏日志、资源测量及失败证据。实际效果供用户审阅，不设置未确认的美观或生成时长承诺。
- 默认并发 1 和测试数据保留得到核对；不修改生产配置。缺少认证、隔离条件或真实壁纸 Skill 执行失败时不能标记本阶段通过；未提供的其他 Skill 不虚报已验收。

## Phase 12：钉钉双端登录与四角色

生图过程可观测已作为 Phase 11A 配套增量交付完成，见 [实现与验收任务](hengxin-smart-image/docs/EXECUTION-OBSERVABILITY.md)。本阶段开始实现钉钉双端登录、统一用户会话和四角色授权；尺寸问题仍按已确认例外处理，不改变原阶段编号。

### 已完成任务：12.1 身份与会话地基、用户角色真实接口

先交付不依赖企业密钥的后端地基：服务端随机会话令牌哈希、过期/退出、钉钉身份映射与部门字段、四角色当前授权及超级管理员用户管理接口。完成标准是匿名和伪造身份不能访问，服务端会话能失效，待授权/禁用账号被拒绝，角色更新在下一次请求生效，用户列表支持分页/搜索/状态/角色筛选，并保护最后一名启用超级管理员。该任务完成后再进入 12.2 钉钉电脑端免登与浏览器网页授权，真实验收需要 Q-008 企业配置。

**交付内容**：
- 实现钉钉电脑端内部应用免登与浏览器官方钉钉授权登录，后端验证后映射同一用户；新增四角色、退出/过期处理及成员资格校验。
- 设计人员和运营人员保留不同角色标识，但映射同一业务权限集合及数据范围规则；两者均可完整使用生产流程，不分别维护权限分支。
- 接入超级管理员分配角色及停用界面，沿用 Art 组件；未授权成员显示待授权，禁止首个登录者自动成为超级管理员。
- 接替 Phase 6 的开发身份来源，保留统一用户标识及资源归属接口；生产禁用开发身份，测试数据不自动绑定真实成员。回归前三类业务入口、返工、下载及归档的完整权限。

**关键文件**：
- `hengxin-smart-image/backend/app/modules/auth/router.py`、`hengxin-smart-image/backend/app/modules/auth/sessions.py`：会话、账号与权限。
- `hengxin-smart-image/backend/app/modules/auth/dingtalk.py`、`hengxin-smart-image/backend/app/modules/auth/permissions.py`：授权码交换、成员映射与数据范围。
- `hengxin-smart-image/frontend/src/api/hengxin/dingtalk.ts`、`hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue`：容器/浏览器双入口适配。
- `hengxin-smart-image/frontend/src/api/hengxin/logout.ts`、`hengxin-smart-image/frontend/src/api/hengxin/http.ts`：接入真实身份并回归文件授权。

- `hengxin-smart-image/frontend/src/views/hengxin/admin/users.vue`：账号授权管理。

**验收标准**：四角色跨创建人查看/删除模板、任务、成品均通过；匿名/禁用用户拒绝访问；主管全员统计及系统配置的权限策略测试通过，真实统计/配置接口在 Phase 13 验收；非管理员 Skill 维护接口越权检查通过；在相同归属/授权条件下，设计与运营的权限策略在相同资源条件下结果一致，业务页面与接口在其所属阶段实现后逐项回归；同一成员两入口映射同一用户，Web state 校验与码重放拒绝、待授权/禁用账号拒绝业务访问、角色变更后旧会话权限更新；匿名和越权请求不能签发下载地址；损坏/超限图片拒绝；刷新和服务重启后素材仍在；无凭据返回前端。数据库迁移、前后端编译和实际上传下载通过。需要钉钉企业应用和测试域名才能标记双端真实登录通过，mock 身份不替代验收。

### 当前执行任务：12.2 钉钉电脑端免登与浏览器网页授权

本任务在 12.1 的会话和身份映射地基上接入真实钉钉企业内部 H5 应用。开发先完成配置读取、授权状态检查、一次性 state、授权码交换、成员资格校验、待授权/禁用反馈和两类入口的前端适配；真实双端验收依赖 Q-008，不能用开发身份或 mock 登录替代。

**执行拆分**：
- 12.2-A：接入部署环境中的 CorpId、Client ID/AppKey、AgentId、AppSecret 和回调域名；增加启动时配置检查与脱敏管理状态，AppSecret 不落库、不回传。
- 12.2-B：实现浏览器 OAuth2 授权跳转和固定 HTTPS 回调；服务端校验短期一次性 state，交换授权码并获取企业成员身份，拒绝企业不匹配、未知成员、重复授权码和异常响应。
- 12.2-C：实现钉钉 PC 容器 `requestAuthCode` 入口，将临时授权码提交服务端，复用同一成员映射和系统会话签发逻辑。
- 12.2-D：接入前端登录状态、重试和错误态；回归待授权、禁用、角色变更、过期会话，以及登录后上传、任务、下载和归档。

**外部前置**：目标企业 CorpId、企业内部 H5 应用 Client ID/AppKey、AgentId、应用可见成员范围、通讯录个人/成员信息读取权限、HTTPS 首页域名与回调地址、超级管理员成员标识。配置字段和操作步骤见 [DingTalk 配置清单](hengxin-smart-image/docs/DINGTALK-SETUP.md)。

**完成标准**：代码测试覆盖 state 重放、授权失败、企业不匹配、待授权和禁用成员；真实浏览器网页授权和钉钉 PC 容器免登均能映射同一系统用户；服务端会话由系统签发，前端拿不到 AppSecret、访问令牌或原始授权码；两端均完成业务回归、前后端编译、迁移和两阶段审查。

## Phase 13：管理中心

### 13.1 调用统计真实接口 · 已审查并部署，待真实角色联调

- 后端新增 `backend/app/modules/management/usage.py` 和 `backend/app/modules/management/router.py`，真实读取 `execution_attempts`、`execution_usage`、`execution_rounds`、`image_versions`、`task_records`，不再返回 501。
- `backend/tests/test_management_usage.py` 覆盖个人/全员权限、日期和人员筛选、上海时区、成功/部分失败/进行中/超时/待核实、图片计数和缺失 usage。
- 修复执行器在 Windows 开发机读取 Skill manifest 时无法进入诊断分支的问题：仅对受控执行工作区显式启用兼容读取，通用安全读取仍保持 fail-closed；全量后端 540 项通过、133 项跳过。
- 前端 86 项测试、类型检查和生产构建通过；本切片相关回归与执行诊断组合测试 77 项通过、76 项跳过。

### 13.2 执行监控 · 本机实现，独立审查与本机验证通过

- 接入真实 Worker 心跳、CLI 版本、Worker 临时空间及 PG/Redis/MinIO 依赖；空闲、不可用与未知分别表达。
- 全部运行/待核实任务保留，最近 100 条其余排队/异常任务有总数及截断提示；复用固定诊断码，不回传原始日志。
- 主管可看全员业务状态，不暴露服务器详情/会话；普通成员拒绝访问。历史失败不使当前空闲 Worker 被误报离线。

### 13.3 系统配置 · 本机实现，独立审查与本机验证通过

- 迁移 `0011` 持久化配置版本与前后值审计；超级管理员可修改，旧版本保存409；默认 Skill 两个入口共享配置版本。
- 新轮次冻结配置与超时，上传接口执行大小限制；网页不能超过部署容量/超时上限，钉钉部署标识只读。
- 最终回归后端639通过/95跳过，前端100通过、类型检查及构建通过。随后于 2026-09-16 提交 `99ff375` 并部署 VPS，迁移 `0011`。
- 验证详情见 [本机验证记录](hengxin-smart-image/docs/PHASE13-MANAGEMENT-LOCAL-VALIDATION.md)。真实钉钉角色、真实生图及阶段验收仍待后续安排。

**交付内容**：
- 按 Product-Spec.md 第 13 节提供个人、全员的调用统计与明细（主管及超管查看全员），使用 Phase 9 采集的实际执行及 usage 数据。
- 提供 Worker、队列、CLI 和依赖状态面板，区分空闲、异常和未知，主管查看全员业务状态。
- 提供仅超级管理员可编辑的系统参数与审计；用户管理及 Skill 管理复用 Phase 4 已完成页面，不另做重复功能。

**关键文件（计划创建）**：
- `hengxin-smart-image/backend/app/modules/management/usage.py`：按日期、用户、类型统计及明细追溯。
- `hengxin-smart-image/backend/app/modules/management/health.py`：心跳、队列、CLI 与依赖状态。
- `hengxin-smart-image/backend/app/modules/management/settings.py`：受限配置读写、校验、版本和审计。
- `hengxin-smart-image/frontend/src/views/hengxin/admin/usage.vue`、`hengxin-smart-image/frontend/src/views/hengxin/admin/monitor.vue`、`hengxin-smart-image/frontend/src/views/hengxin/admin/settings.vue`：同源 Art 界面。
- `hengxin-smart-image/frontend/src/api/management.ts`：管理接口及错误状态。

**数据增补**：Phase 9 创建 execution_attempts、execution_usage、worker_heartbeats；本阶段创建 system_settings、settings_audit。业务事实与可展示检查字段持久化；统计首先按 PG 查询，不新增专门分析服务。心跳保留当前节点状态即可，不无限积累探测行。

**验收标准**：前后端构建和数据库迁移通过；用四角色账号、跨日任务、单张和整套返工、一次重复事件、一条无 usage 失败记录验证统计可复算；设计与运营的个人统计接口不能读取全员统计，设计主管可查询全员统计，只有超级管理员可改系统配置；无 CLI 活跃进程显示空闲、停止 Worker 后心跳过期显示失联；配置越界拒绝且变更有审计，运行中任务配置不被追溯修改。真实采集依赖 Phase 9，fixture 不替代 CLI 事件验收。


## Phase 14：真实业务联调与 Ubuntu 部署

### 当前执行任务：14.1 VPS 开发测试部署

用户已授权将系统部署到既有 VPS，用于后续开发和测试。本任务已交付可回滚的独立开发测试环境：复用 VPS 现有 1Panel，不接管其 80/443；应用使用独立 Compose 项目和数据卷，前端通过独立端口访问；关闭 fixture，使用 VPS 上专用 codex 用户和真实 CLI。HTTPS 已接入；钉钉双端、三个真实 Skill 全量验收和正式容量承诺仍待后续验收。

完成标准：VPS 主机、应用、数据库、队列、对象存储、原生 Codex Worker 和前端健康检查均有证据；公网 VPS 关闭开发身份，本机开发身份仅用于隔离联调；数据卷、CLI 认证、Skill 和会话目录不进入 Git；部署失败可以停止本项目并保留现有 1Panel 服务；前端能通过 VPS 地址打开并访问真实 API。2026-09-15 已满足部署与基础健康检查；真实壁纸 Skill 冒烟任务已进入模型处理并检测到输出，随后因 `SKILL_DIMENSION_MISMATCH` 失败，不能标记真实 Skill 业务验收通过。

**交付内容**：
- 安装外部提供的壁纸、商品、文字 Skill 及依赖，逐类验证指定规则、真实图片回传、返工和归档全过程。
- 建立 Ubuntu Compose 发布、HTTPS 入口、备份恢复、日志轮转与失败告警，生产关闭 fixture；限制内部数据库和存储管理入口。
- 将仍可返工任务的会话材料纳入受保护的备份与恢复边界，验证数据库会话关联、会话材料和图片版本在恢复后相互对应。
- 完成 20 人初期试运行及 100 登录用户的普通接口负载测试，独立测量 CLI 并发资源占用，形成实际运行参数和回滚记录。

**关键文件**：
- `hengxin-smart-image/infra/compose.prod.yaml`、`hengxin-smart-image/infra/nginx.conf`：发布配置。
- `hengxin-smart-image/infra/backup.sh`、`hengxin-smart-image/infra/restore.sh`：PG、MinIO 及必要 CLI 会话材料的配套备份恢复。
- `hengxin-smart-image/docs/DEPLOYMENT.md`、`hengxin-smart-image/docs/ACCEPTANCE.md`：机器规格、锁定版本、运行阈值、验收和回滚证据。

**验收标准**：PRD AC-001–025 中已确认的规则全部有真实证据；跨账号/重启/断线/失败重试验证通过；PG、MinIO 与必要会话材料在独立环境恢复后能打开归档图并按原会话返工。普通列表接口建议目标 P95 ≤ 1 秒（排除上传下载及生成，测试报告记录网络和数据量）；建议每日备份、RPO 24 小时、RTO 4 小时。这些数值仍按 PRD 第 11 节确认，再分别用负载测试和恢复演练验收。100 用户结果不等于 100 CLI 并发承诺。钉钉电脑端与 Chrome/Edge 实测登录、上传、预览、单张/ZIP 下载及异步闭环，权限、Cookie、窗口和回调兼容性均需证据。

没有真实 Skill、认证或服务器资源信息时，记录具体缺口，不能把 fixture 回归替代本阶段完成。图像美观程度仍由运营审阅，不制定本轮效果评分。

## 6. 数据模型分期

| 表 | 创建阶段 | 责任 |
|---|---|---|
| users | 6 | 稳定用户标识与测试用户归属，后续接真实身份 |
| sessions、user_identities、role_assignments | 12 | 四角色、钉钉身份绑定、资源操作策略和系统登录会话 |
| execution_attempts、execution_usage、worker_heartbeats | 9 | 实际 CLI 启动、操作者、可用 usage 与当前节点心跳 |
| system_settings、settings_audit | 13 | 可配置参数、版本及变更审计 |
| deletion_records | 6 | 模板、任务及成品共用的逻辑删除记录，保留实际操作者；Phase 11 接入回收清理 |
| files | 6 | 私有对象键、大小、类型、尺寸、校验和及所有者 |
| templates、template_versions、template_images | 7 | 模板元信息、不可变配置版本、有序 slot |
| skills、skill_versions、module_skill_bindings | 7 | 包状态、内容校验和、默认与专用绑定 |
| tasks、task_inputs、execution_rounds | 8 | 创建请求、输入快照、排队执行和失败原因 |
| operation_requests | 8 | 操作者/操作范围内的幂等键、载荷指纹及原受理标识，唯一约束防止并发重放 |
| 任务执行占用、轮次认领与取消字段 | 8 | 在 tasks/execution_rounds 持久化同任务唯一未结束轮次、当前认领凭证、取消意图及待核实状态；Phase 9 接实际进程和租约 |
| job_outbox（后续扩为通用作业） | 5 | 当前关联测试作业；Phase 7 增加作业类型与终态，Phase 8 用于生成 |
| task_events、image_versions | 8 | 业务事件、fixture 与真实执行共用的图片版本 |
| execution_sessions | 9 | taskId/sessionId 唯一关联、受保护会话材料位置及可恢复状态；为 execution_rounds 增加实际执行代次/租约迁移，复用 Phase 8 图片版本模型 |
| revision_requests | 10 | 修改意见与目标范围；任务表增加当前版本集合关联迁移 |
| archives、archive_images | 11 | 归档快照、选定版本和回收时间 |

MinIO 私有 bucket 建议 `hengxin-smart-image`，对象分 templates/、inputs/、outputs/、skills/ 前缀；每个版本新对象键，归档引用不可变版本并保护引用，不依赖覆盖同名对象。CLI 每轮输入/输出目录是临时执行空间，必要会话材料单独持久化并保护任务归属，MinIO 是持久图片与 Skill 文件来源。数据库事务与对象上传用暂存/确认/孤儿回收衔接，不能假定跨系统原子提交。

## 7. 覆盖与完成规则

| PRD 范围 | 前端阶段 | 后端/联调阶段 | 最终验收 |
|---|---|---|---|
| REQ-001 / SCOPE-001–003 三类功能 | 1、2 | 8、9、11A、14 | AC-001 |
| REQ-002 / SCOPE-004 模板与 Skill | 2、4 | 7 | AC-002、003、012 |
| REQ-003 素材和提交 | 2 | 6、8 | AC-003、010 |
| REQ-004 / SCOPE-005 会话和执行 | 3 | 8、9、11A、14 | AC-004、005、009、010、015、016、022–025 |
| REQ-005 / SCOPE-006 反馈返工 | 3 | 8–10、11A、14 | AC-006、007、011、021、025 |
| REQ-006 / SCOPE-007 下载归档 | 3 | 11 | AC-005、008、013 |
| SCOPE-008 四角色、登录和历史保护 | 3、4 | 7、11、12、14 | AC-012–014、017、019、020 |
| REQ-007 / SCOPE-009 管理中心 | 4 | 9、12、13 | AC-017、018 |
| REQ-008 钉钉双端登录 | 4 | 12、14 | AC-019、020 |
| 非功能与部署 | 1–4 | 5–14 | 持久化、重启、资源、备份及双端报告 |

每阶段完成后按 Code Review（独立 code-reviewer 两阶段）→ 测试完整性 → 编译验证 → 功能测试执行，证据写入开发记录。后端阶段的 Python 检查包括静态检查、导入/启动和迁移；前端执行类型检查及生产构建。针对幂等、权限、版本隔离和重启恢复编写有意义的测试，不用复述实现的测试凑数。只在用户授权提交时提交，Git 标题和正文使用中文。

本轮自检：15 个有序阶段（保留原 14 阶段编号，新增 Phase 11A 开发机真实联调）均列交付、关键文件及验收；8 项 REQ、9 项 SCOPE、25 项 AC 均有映射；前端复用与 Python/PG/MinIO 约束一致；不包含业务 Skill 编写或效果评测。已确认技术栈不等于批准所有建议业务默认，Phase 入口仍按第 4 节管理。

## 8. 官方资料与版本核查

### 已核查资料

- [FastAPI 版本锁定建议](https://fastapi.tiangolo.com/deployment/versions/)及[发布记录](https://fastapi.tiangolo.com/release-notes/)：独立锁定 FastAPI，执行升级回归；本计划以本机 0.139.2 为起点。
- [PostgreSQL 版本支持](https://www.postgresql.org/support/versioning/)：16.15 是受支持 16 系列的补丁版本，优先复用本机而非升级到其他主版本。
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/intro.html)：采用稳定 2.0 API；本机为 2.0.51，文档当前为 2.0.52。
- [Celery 介绍](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)及[Redis broker 注意事项](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)：后台 Worker 与消息队列；官方不支持 Windows，长任务须处理重投。
- [MinIO Python API](https://docs.min.io/aistor/developers/sdk/python/api/)：参考对象上传下载与预签名 API；文档为 AIStor 品牌，实际采用本机社区镜像，必须实测兼容，不假定商业功能可用。
- [Node.js 版本状态](https://nodejs.org/en/about/previous-releases)：选择 24 LTS；前端包版本以已有锁文件为准。
- [Codex 非交互执行](https://learn.chatgpt.com/docs/non-interactive-mode)：支持 exec、JSONL 事件及按会话 ID 续接。具体命令参数以 Phase 9 固定 CLI 版本实测为准。
- [Skill 结构](https://learn.chatgpt.com/docs/build-skills)：目录包含 SKILL.md 及可选脚本、参考资料；包存储与发布不代表已经具备图片处理能力。

钉钉官方资料与接入前置配置统一记录在 Product-Spec.md 第 13 节；双端登录在业务闭环后的 Phase 12 验收，Phase 14 上线前完成双端回归；企业配置不阻塞 Phase 1–11。


## 2026-09-21 · 独立 Demo 扩展计划（仅本地）

用户要求将图片优化原型拓展到 Demo + 假数据级别。范围、拆分、边界和验收以 [框架 Demo 计划](docs/FRAMEWORK-DEMO-PLAN.md) 为准。沿用当前品牌和正式前端，新增持久化假数据、模板维护、三类模拟任务、版本返工、归档与管理演示。正式工程和既有阶段验收不因本次 Demo 交付改变。


## 2026-09-21 · 用户确认基于现有框架迁移 Demo

用户确认采用现有 Vue 3、Element Plus、Art Design Pro 框架内的独立Demo模式，复用真实布局和业务组件，假数据隔离于生产API。此决定替代上一版独立HTML作为后续交互评审实现方式；旧原型已清理。范围及验收见 [框架Demo计划](docs/FRAMEWORK-DEMO-PLAN.md)。不改变生产业务接口和既有阶段验收结论。
## 2026-09-22 生图等待动效

1. 新增 Vue 生成占位组件，复用现有主题颜色，仅在无结果且任务活动时渲染；排队和执行反馈不同，不伪造进度。
2. 校验等待、生成、失败、已有结果、减少动态偏好与离屏暂停；类型检查、前端测试、构建与专项审查。
## 2026-09-22 紧凑上传区

调整 ImageUpload 非排序模式的空态/有图布局，复用上传校验与图片预览；检查追加、全删、失败、折叠及窄屏，回归模板排序和单张截图入口。类型、测试、构建、浏览器及限定范围独立审查后交付预览。

## 2026-09-22 · 正式前端 UI 发布

用户批准当前 Vue 前端 UI 迭代，授权文档同步、过程产物清理、提交、真实 VPS 部署与推送。共享组件改进同时用于真实 API 与本地 Demo；本节替代前述 Demo 阶段的“仅本地”发布范围，Demo 服务本身仍限本机 3010。

1. 核对正式源码、需求与设计，清理旧原型和无须交付的临时产物，保留必要验证证据；完成标准为无失效维护入口、无敏感发布文件。
2. 完成类型检查、单测、正式及 Demo 构建、浏览器回归和独立两阶段审查；完成标准为当前代码快照对应批准凭据与验证记录。
3. 用 `pnpm build` 的默认 production 模式构建正式前端并连接真实 API，按白名单发布与备份回退流程仅更新前端，保留已发布后端、Worker、0014 数据库及业务数据；核验哈希、健康与真实页面后记录实际发布编号，再推送提交。

本轮发布完成：源码提交 `c837abf`，前端 `ui-20260922-c837abf` 已上线；125单测、类型、生产构建、两阶段审查及隔离浏览器检查通过，线上399文件哈希/健康/匿名登录页通过。后端、迁移0014和Worker保持不变，真实登录后业务未在本次线上复测。见 [发布记录](hengxin-smart-image/docs/UI-RELEASE-20260922.md)。三类真实 Skill、付费生成效果、完整双端及容量/恢复验收仍需各自证据。
# 2026-09-22 · API 换套图交互预览追加

当前仅实施 [API 交互预览计划](docs/API-IMAGE-PREVIEW-PLAN.md)，在既有前端 demo 模式复用 Art / Element Plus 实现独立新建页、记录页和任务详情，模拟串行与重试。按该文档的五步验收；生产后端实施计划后续另定。本次不发布、不提交，不更改 CLI 业务链路。

## Phase 15 · 独立 API 换套图真实接入（2026-09-22 授权）

本轮替代上段仅预览范围，按 [独立 API 实施计划](docs/API-IMAGE-IMPLEMENTATION.md) 四个有序步骤实施：独立数据和接口、串行执行与故障恢复、真实前端接入、隔离集成和独立审查。关键文件/接口契约/错误规则/验收见该计划，既有Phase完成度不变。不得把单次API成功当平台或隔离已验收；不得改CLI业务链路或自动部署推送。

开发验收已完成，待用户确认：真实双图调用/持久化/下载通过，CLI业务数据未写入；串行、重试和不确定结果保护已测试。完整后端851项通过（112跳过）、前端137项通过，最后边界修复后API核心45项通过，类型检查/两模式构建通过；独立最终审查Stage1/Stage2 PASS。详见 [验证记录](docs/API-IMAGE-IMPLEMENTATION-VALIDATION.md) 和 [最终审查](docs/API-IMAGE-FINAL-REVIEW.md)。尚未部署、提交或推送，生产配置按运行说明另行处理。

后续用户已确认并授权提交部署：功能提交57ce288，生产发布api-image-20260922-57ce288完成，迁移0015、独立API服务及前端0.2.0通过线上健康/哈希/鉴权/登录入口核验；原CLI进程与配置保持。详见 [发布记录](hengxin-smart-image/docs/API-IMAGE-RELEASE-20260922.md)。登录后生产收费生图不在本次已验证范围。


## 2026-09-22 核心交互前五项执行计划
1. 列表图片预览及模板选择布局：验收等比图集、键盘打开、取消更换、1280同屏选择。
2. 查找范围贯通前后端与Demo：验收分页前按当前身份筛选、统计一致、创建人、URL恢复及长编号复制。
3. 单图对照与失败摘要：验收截图1张口径、意见保留、旧结果不误计本轮成功及重试恢复。
4. 类型/单测/构建、隔离浏览器核心流程与独立两阶段审查后交付本地效果。审查06–09不纳入。

## 2026-09-22 创建任务首屏布局修正
用户反馈整页高度过大。三类创建页采用左侧模板/素材、右侧任务信息/提交布局；压缩重复预览和标题留白，Demo 调试工具默认折叠且可展开。1366×768、1280×800下默认选定模板的空素材态及单图态，任务名称、修改要求和提交按钮无需滚动可见；多图和模板选择展开允许内容滚动，不能遮挡提交。窄屏按自然顺序堆叠，不缩放整页、不隐藏错误和必填项。上传空态改为紧凑拖拽区，替代此前“大拖拽框”要求。

## 2026-09-22 套图展示与模板选择布局细化
用户要求默认展示更多套图、组件高度协调、更换/取消不生硬、每行3套。默认选定模板展示前6张完整等比图片及总张数，点击任意图可看整套；大屏限制内容最大宽度，模板和任务信息区统一首行高度，使用16px区间节奏。更换模板在独立选择对话框进行，不推走上传/表单；关闭、取消保持原模板与输入，明确选择才应用。桌面选择器3列，每页6套；窄屏2/1列，搜索、分页、失败重试保留。真实可用模板不足3套时如实展示，不复制假模板填格。保持1366×768和1280×800核心输入/提交首屏可见。

## 2026-09-22 模板库四列完整卡片
用户要求模板库桌面一行4套，首行卡片及底部操作完整可见。仅调整模板库布局：桌面>=1200px为4列，900–1199px为3列，600–899px为2列，更窄为1列；预览完整等比、固定紧凑高度，保留整组放大与名称、状态、版本、使用/配置/历史/删除。1920×1080、1366×768、1280×800验收首行完整，长文字允许卡片自然增长且全文可查看，不固定高度裁切卡片；不改变成品库和模板选择面板。

## 2026-09-22 成品库四列完整卡片
用户确认成品库同样采用桌面4列与完整卡片方案。复用模板库的布局样式与响应式断点，预览等比，名称、归档时间、查看/下载/删除完整保留；首行在1920×1080、1366×768、1280×800可见，长文本自然增长。保持成品详情、归档快照、来源任务、下载和删除确认逻辑不变，同时回归模板库布局。

## 2026-09-22 任务中心首屏密度
用户要求第一眼展示更多任务。去除装饰眉题并压缩页头，将全员/我的范围与四项真实统计合成一条紧凑摘要；列表筛选保持清晰分组。任务行改为两行身份信息（名称；创建人/SKU与可复制完整编号），44px等比图，行高约60px，查看和删除同排且删除确认保留。状态、真实进度、时间、权限、分页和URL筛选语义不变。正常任务数据足够时1920×911首屏目标至少8条，1366×768至少6条，1280×800至少5条；保留缩略图大图、完整编号复制及窄屏可访问性，不缩放整页或隐藏关键操作。

## 2026-09-22 · 合并现网模块后的 UI 优化发布

用户授权先提交、再部署真实环境、最后推送。保留现网 API 换套图模块和0015数据库；发布当前共享前端及任务列表 scope/ownerName 后端兼容改动。正式前端版本0.2.1；API从合并后的完整代码构建，只更新API服务，CLI/API生图worker及outbox保持原实例与配置。上线前备份前端及API部署配置，保留旧镜像；不执行迁移，不创建收费生成任务。按发布记录验收文件哈希、服务健康、鉴权和匿名浏览器入口。

## 2026-09-22 · 已有结果收取阻塞修复

待核实状态只阻止新的生成调用，不能阻断已有结果的下载保存。复现、修复、测试与生产验证按 [修复计划](docs/API-IMAGE-COLLECTION-FIX.md) 执行。
