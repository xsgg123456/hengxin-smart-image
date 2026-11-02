# 海外设计人员流程与 OUTON Skill 合并发布记录

最新结果：用户已明确恢复授权，本轮开发、测试、审查、提交及生产部署均已完成，包含五人权限与消息姓名/时间。当前版本 0.2.58，发布目录 outon-20261102-2fbbc5e，OUTON 已安装且未分组、默认关闭。完整证据见 [0.2.58 生产验收](OVERSEAS-0.2.58-PRODUCTION-20261102.md)。以下暂停和未执行叙述均为此前阶段历史，不代表当前状态。

已确认范围：docs/DESIGNER-ONLY-IMPLEMENTATION-20261102.md，包括三角色及海外0024迁移、设计提交和任务范围、字段重排、目标站点/补充说明删除及完整Skill安装。下文“本地验证”为新增三角色需求之前的阶段证据，不能替代本次合并版本验收。提交部署现已授权。

用户确认安装指定 Skill 到海外生产、保持未分组，并删除提交/修改图需的目标站点输入和必填要求。目标平台保留，历史 market 数据保持。新增 Skill 沿用默认关闭，由用户后续配置。

## 范围与实施顺序

1. 源包完整性与生产基线核对：原始51文件、24,889,876字节；原始checksum `7d05f9c586503996c0a5346f84ce549ee5a3442f243d6c873b01546c8ebb9b81`。生产0.2.57、海外schema `overseas_0023`。
2. 删除共用表单项及正式/预览校验，后端接受缺省/空串；重提省略market保留历史值，幂等摘要区分省略和显式空串。
3. 当前完成独立审查；审查通过后中文提交、构建正式制品。追加指定五人权限后的合并版更新16个海外运行文件及0024角色迁移，前端0.2.58；停止API接纳、暂停空闲队列及正常停止原生服务、备份并隔离恢复迁移验证，同步API与原生代码及指定账户配置，再恢复消费。
4. 安装Skill：复制当前完整集合并追加一项，验证所有旧项及原开关/分组保持。实际API及原生身份读取同一目录，正式管理页显示未分组。
5. 正式表单和管理页视觉核验、服务健康与部署哈希确认。

## 源包路径适配

原目录不变。部署副本仅将 `assets/brand/manifest.json` 与 `font-reference.json` 中本机来源路径改为实际包内路径；字体/Logo摘要必须与原记录相符。其他49文件逐字节保持，完整原始及部署摘要见 `OUTON-SOURCE-MANIFEST-20261102.json`。

部署副本checksum `75f7a2ccf0bf5a54d659266c941235ebbc3e62c273ad8675d2bed7f1d6234d68`；51文件、24,887,153字节。源包tar SHA256 `2beeba69b0da84c48f7a235a4d88133818c993d2afba9bde312d8dbc5c399154`。文本隐私扫描通过。

## 本地验证

- `pnpm test`：438 passed；`pnpm typecheck`通过；0.2.58生产构建成功，日志 `output/remove-market-frontend-test.log`、`output/outon-install/frontend-build.log`。
- 后端tasks/requirements/market_optional：48 passed，验证真实HTTP/SQLite契约、持久化、历史值、幂等与其他字段错误分支。
- OUTON发布/源包及既有平台发布工具：40 passed。
- 独立审查发现隔离数据库名不同导致information_schema指纹误报，已改为隔离容器内同名数据库。实际PostgreSQL验证复现旧问题并确认同名dump/restore列指纹一致，证据 `output/outon-install/catalog_test.stdout`；测试容器和卷已清理。
- 依赖审计critical 0，现有high73/moderate55/low11。本轮未修改依赖，不宣称清除既有漏洞。

## 历史发布暂停状态（已由本次上线替代）

合并实现的最终测试证据见 `DESIGNER-ONLY-VALIDATION-20261102.md`：前端441项、隔离Linux/PG海外729项、发布工具55项均通过，类型检查/生产构建/3套浏览器通过。生产发布验收仍未执行。

用户最新已暂停Git提交和部署。当前合并实现和验证进行中，尚未Git提交。服务器仅有待安装源包 `/opt/hengxin-releases/outon-skill-20261102/skill-source.tar.gz`，未解包安装、未修改Skill目录、未切换前端或API。

生产备份恢复、实际Skill安装与部署后的正式页面验证尚未执行，留待恢复发布授权后完成。当前隔离测试只启动临时测试容器，不修改生产数据或业务服务。

## 指定五人权限追加

依据 `WORKFLOW-COLLABORATORS-20261102.md`，本地私人绑定为 `output/workflow-access/binding.private.json`；未来发布工作目录复制为 `workflow-collaborators.private.json`。新增配置键 `OVERSEAS_WORKFLOW_COLLABORATOR_MEMBER_IDS` 必须仅包含核实的五个成员UUID。prepare只读核验有效designer、绑定哈希与实际基线；API覆盖文件只增加该键和镜像，旧full-access及Skill开关授权保持。

原生服务正常停止且0024迁移验证后，安装固定源代码及专属 `/etc/hengxin-overseas/workflow-collaborators.env`、两个专属systemd drop-in，再启动核对进程实际授权和其他业务环境哈希；API和native恢复文件读取入口均核查同一权限。已有单元/环境文件保持，未知配置变化拒绝，中途失败人工检查后按固定快照修复。当前未执行任何生产配置写入。
