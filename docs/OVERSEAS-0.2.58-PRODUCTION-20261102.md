# 海外业务 0.2.58 生产验收

2026-11-02 已完成开发、测试、独立双阶段审查、中文 Git 提交及生产部署。用户最后明确授权提交并部署，替代之前暂停提交和部署的指示。

## 发布与范围

- 地址：https://zhitu.qhhengxin.top/；版本 `0.2.58`；业务提交 `edfa075`，发布基线修正提交 `2fbbc5e`。
- 实际发布目录 `/opt/hengxin-releases/outon-20261102-2fbbc5e`。制品 SHA256 `acfbe6cfd3a9d3810b051aa749b1971266c4053372013ede6339d82025d2ab7a`，5,019,461 字节，隐私检查通过。
- 海外保留设计、设计主管、超级管理员三角色，删除运营角色分支，数据库迁移至 `overseas_0024`；国内业务保持。
- 基本信息顺序：SKU → 目标平台 → 品牌 → 任务名称 → 品名 → 负责设计。保留多 SKU；移除目标站点和补充说明及对应页面展示，重提省略字段时保留历史值。
- 陈妹、周仁平、胡礼辉、黄湘婷、姚锐娟按已核实的成员 UUID 授权：自己创建或负责的任务可操作全工作流，其他任务只读。管理、改派、删除等原有管理权限不扩大；其他设计成员不自动获得此特殊授权。
- 用户消息显示实际操作人及发送时间，Codex 回复显示对应时间，统一北京时间；缺失历史信息不冒用当前查看人或当前时间。

## 测试与审查证据

- 前端 444 passed，类型检查与正式构建通过；1366/390px、跨时区、多发送人及不同查看人浏览器验证通过。五人权限浏览器使用模拟 API，真实 HTTP/数据库授权另有测试覆盖。
- 最终候选镜像实际安装测试：37 模块，498 passed、0 skipped，281.12 秒；证据 `output/outon-install/test.stdout` 及服务器 `installed-tests.txt`、`INSTALL_TESTS_PASSED`。
- 真实 native 完整源码布局、UID 999、隔离 Linux/PostgreSQL：97 passed、0 skipped；发布工具 84 passed。
- 更广的 131 模块测试与旧测试前提修正记录见 `STUDIO-MESSAGE-METADATA-VALIDATION-20261102.md`。未将分批与定向复验称为最终全量一次通过。
- 独立审查：`reviews/MESSAGE-METADATA-COMBINED-20261102.md`、`reviews/NATIVE-BASELINE-20261102.md`，均 Stage 1 PASS / Stage 2 PASS。最后批准代码快照 `33e0ddfa935a236b08b4812ac07ac7603c4c1d4e6c95d20e307449df57df2090`。
- 依赖未改；审计 critical 0，既有 high 39、moderate 38、low 5 仍存在，本次不宣称消除既有依赖漏洞。

## 生产执行与实查

- 完整数据库备份及隔离同名恢复、指纹核对、迁移重复执行验证通过。空队列暂停后正常停止 API 与两个 native 服务，无强制杀进程；迁移、原生代码和权限配置、API、消费恢复、前端切换均通过。
- API 19 路径、各 native 18 路径分别按实际历史基线校验。原 native 307 文件中未纳入补丁的 290 文件逐字节保留，增加 helper 后共 308 文件；其他容器与原有服务配置保持。
- 五位真实成员在 API、worker、outbox 三个运行环境均确认为启用的设计成员且授权有效。各可读现有 8 个任务，对这 8 个他人任务均拒绝写操作，5 项管理权限拒绝。
- 当前这五人没有已创建或已负责的生产历史任务，因此不声称在生产执行过其正向写操作。自己创建/负责的正向操作由隔离真实 HTTP/数据库及浏览器用例验证；生产检查全程只读，无新增测试任务或生图请求。
- 三个运行环境以只读事务校验 24 会话、119 轮、2 位真实发送人；118 条有公开消息时间，1 条历史时间未记录。5 个不同查看人获得相同发送人/时间元信息。
- 生产页面已核验字段顺序、删除字段、三角色菜单；真实历史对话显示“张帅 2026-10-30 15:49:24”和“Codex 已回复 2026-10-30 16:26:21”，历史文本与附件仍在。
- 最终独立校验：内网及公网 readiness 均 HTTP 200，两个 native 服务 active，API 镜像/19 文件、native 文件、前端所有制品哈希与 schema 均匹配。证据 `output/message-release/final_health.stdout`；权限/元信息证据 `output/message-release/probe.stdout`。

## OUTON Skill

- 完整安装 51 文件，目录总计 16 个 Skill，原 15 项及原有开关、平台设置保持。新增项为“Amazon OUTON 图需转正式生图任务”，生产管理页目视核验为 **未分组、已关闭**，留给用户后续设置。
- API 与实际 native 身份读到同一目录；catalog release `61dde1b655f547ddc2b8f3745684387f489f2c9882376cb8b1793c938731a834`。
- 新包 checksum `75f7a2ccf0bf5a54d659266c941235ebbc3e62c273ad8675d2bed7f1d6234d68`。只对部署副本的两个来源元信息 JSON 做可移植路径适配，其余 49 文件与原包一致，原本地包未修改。
- 证据：`OUTON-SOURCE-MANIFEST-20261102.json`、`output/message-release/skill-{prepare,install,verify}.stdout`。

## 发布制品只读保护

原生验证子进程曾在发布源目录生成未列入清单的 `scripts/release/__pycache__/account-runtime.cpython-312.pyc`，精确清单检查因此阻止 API 阶段。只清除该已确认生成的缓存文件，重新验证全部制品哈希后，将 `/opt/hengxin-releases/outon-20261102-2fbbc5e/src` 自绑定挂载为只读，避免子进程再次写入缓存；没有忽略额外文件或放宽校验。

该只读挂载仅覆盖发布源制品，不覆盖运行代码或发布记录；未写入 fstab，重启后不保证保留。当前全部发布阶段已完成，最终检查确认只读挂载及精确清单正常。证据为发布目录 `IMMUTABLE_SOURCE.json` 和 `output/message-release/immutable-source.stdout`。Skill 安装后目录已按计划变化，不应再运行要求旧 Skill 目录不变的早期 outon-deploy verify/resume；应使用已安装 Skill 验证及独立最终健康检查。
