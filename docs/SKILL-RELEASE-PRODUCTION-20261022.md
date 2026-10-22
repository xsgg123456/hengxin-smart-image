# 海外工作台与 Skill 开关 0.2.47 发布记录

## 授权与范围

2026-10-22 用户授权提交 Git、打包并部署生产。包含附件草稿恢复、任务素材批量移除、当前账号专属 Skill 开关；初始只开启 `amazon-new-product-image-set`、`amazon-new-product-aplus`。产品验证见 `SKILL-AVAILABILITY-20261022.md` 与 `STUDIO-DRAFT-MATERIALS-VALIDATION-20261022.md`。

## 发布前实查

- 正式前端版本 0.2.46，发布标识 `domestic-retention-20261021-bec8dd7`；海外后端标识 `overseas-20261019-1c28ee2`。
- 国内数据库 `0032`，海外数据库 `overseas_0019`；本次仅海外迁移到 `overseas_0020`。
- 生产当前账号有效且单角色为 `super_admin`。部署绑定按固定成员 ID 私有传输，不纳入仓库、发布包或本报告。
- 海外 API 健康，3 GiB 内存限制、unless-stopped；实查任务状态仅 3 个 succeeded。切换时仍重新排空验证，不依赖此次静态结果。
- 国内三个原生服务来自最新三天清理版本；海外两个执行服务来自 0.2.43；共享凭据代理继续使用现有版本。发布脚本分别核验并保留这些基线。

## 发布前验证

- 前端标准生产构建成功。固定 Node 24.18.1、pnpm 10.33.4 再次构建的日志为 `output/skill-release-20261022/frontend-build-pinned.log`。
- pnpm 10.33.4 官方 registry 依赖审计：0 critical，7 low、51 moderate、72 high。本次没有升级依赖，现有非 critical 风险仍在；日志 `frontend-audit-pinned.json`。
- 新发布入口及继承链联合测试 206 passed、120 subtests。独立审查发现本地打包自检文件被误纳入发布清单，已缩小到部署必需文件并加入真实选中文件内容的隐私回归；修复后相关发布测试 148 passed、72 subtests。
- 私有绑定要求 root:root 0600 的单行 UUID；准备至切换保持摘要一致，只向海外 API 注入此项。实际镜像安装后只读探针验证唯一可切换成员及两项初始开启。
- 迁移要求完整备份隔离恢复、原业务行指纹与旧表列元数据保持，只增加 Skill 状态表及两个种子行；故障保持入口关闭。

## 生产部署结果

- 功能及发布提交 `5c3715ff71e3318435f3097f110b5d7e51ec600b`，部署 `overseas-20261022-5c3715f`，前端 0.2.47。独立两阶段 PASS，批准快照 `61902f176f05f3a6998fcf9ddb17c88f40804d0dc7101a6df778feea5aa78bc3`，详见 `reviews/SKILL-RELEASE-20261022.md`。
- 发布包 1267 个文件（含 manifest）、5,524,613 字节，SHA256 `edc71f7c6d98e0e8d2bbbc027ce3e9f4a446e7102c89b7c07bd04d0c92d48137`。本地隐私、文件集合、文件摘要及服务器解包后 1266 个业务文件摘要均通过；私有账号绑定另行传输、root:root 0600。
- 实际镜像 `sha256:ed7bafd1e6c0008fb89d7f19ef23e24546f5bcf2819b34de1b7aebb39924935c`，559 个后端文件与提交摘要一致。镜像内安装测试 2085 passed、178 skipped、1 deselected、6 warnings，482.74 秒；保留既有本地 CLI 忽略和源码接口对照排除，跳过不算通过。3 GiB 限制下上传容量测试 4 passed，7.28 秒。
- 排空前后各两次稳定 DB/broker 检查通过，正常停止海外执行服务。备份 `/opt/hengxin-backups/overseas-20261022-5c3715f` 已在隔离数据库恢复并验证原行指纹。迁移只新增 Skill 状态表及两条开启记录，旧业务行、旧列元数据一致，国内保持 0032。
- 发布目录有 `MIGRATION_VERIFIED`、`SKILL_AVAILABILITY_VERIFIED.json`、`INSTALLED_VERIFIED`、`verification.json`，`PHASE=complete`。海外 API 及两项原生服务已切换，公共入口恢复；国内 API/原生服务、身份服务及共享凭据代理配置和进程保持。国内、海外 ready 接口与正式首页均 HTTP 200。
- 只读安装探针在真实 API 环境下验证全部成员中仅绑定账号 `can_toggle=true`，此账号有效且有 `skills.manage` 权限；目录仅两个指定 Skill 开启，版本均为 1。实际状态表为两行，均 `enabled=true, version=1`。
- 完整状态证据 `output/skill-release-20261022/production-verification.log`、`final-status.log`，安装日志留在服务器发布目录；本地包与审计位于 `output/release/overseas-20261022-5c3715f/`。

## 正式页面验收

使用当前真实账号访问正式域名，管理页显示其余 12 项关闭、两个指定 Skill 开启，当前账号具有操作按钮。正式工作台下拉仅列两个指定 Skill。

在用户原“直杆实木布罩灯-乡村风 整套 测试”任务中，勾选 9.jpg、8.jpg，打开“移除所选素材（2）”确认窗并取消，素材总数仍为 17。引用两张既有附件并输入明确未发送的验收草稿，整页刷新后文字、两张缩略图均恢复；随后清除验收文字和输入区引用，恢复空草稿。未上传测试文件、未发送模型任务、未移除任务素材、未改变任务状态或 Skill 开关。

发布后首次浏览器加载曾呈空白，重新打开普通正式链接并等待资源加载后正常；随后任务页整页刷新也通过。未发现控制台异常，正式 HTML 在普通与附加参数请求中的摘要相同，资源请求 HTTP 200；未据此臆断根因或修改代码。

已目视核对截图：`production-skills.png`、`production-batch-confirm.png`、`production-studio-skills.png`、`production-draft-restored.png`，均在 `output/skill-release-20261022/`。生产批量移除只验确认/取消分支，实际移除、失败重试和权限否定分支沿用隔离测试证据。
