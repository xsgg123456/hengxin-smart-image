# 内网副本执行记录 · 2026-11-10

状态：**内网副本已部署并投入测试；IP入口、已登录国内页面、CLI升级、授权代理修复及国内/海外Codex执行环境专项验收已完成。全业务、全角色、手机端和长时间稳定性验收仍未完成。** 旧公网未切换，正式DNS不变。

当前入口 `http://192.168.1.245:8080`，前端 `0.2.67-lan.2`；国内、海外及账号管理CLI均为 `0.167.1`。正式业务调用 `gpt-6-astra / high`，账号可用性探针使用 `low`。

最新证据索引：

- [IP访问与国内菜单修复](INTRANET-IP-ACCESS-20261111.md)：用户确认回调已配置且登录成功；主Agent使用现有已登录会话实测国内工作区及管理访问。独立发起新的完整OAuth往返、手机钉钉及全部角色组合尚未验证。
- [CLI升级](INTRANET-CODEX-UPGRADE-20261111.md)、[授权代理修复](INTRANET-CODEX-AUTH-FIX-20261111.md)：独立版本安装、排空切换、代理继承及取码验证；后续真实模型通过既有broker实际成功，早期“尚未授权”不再代表当前模型可用性。
- [执行环境与PPT验收](INTRANET-CODEX-RUNTIME-FIX-20261111.md)：两真实UID从最终安装路径通过文档、图片、脚本及隔离探针；海外真实PPT读取/看图/同会话续接、国内原生图片编辑和收集通过。不是完整业务API投递/UI流程验收。
- [国内删除核查](INTRANET-DOMESTIC-DELETE-CHECK-20261111.md)：用户已删除任务的数据库、对象和执行目录清理通过；没有删除前容量基线，不宣称净释放字节数。
- [国内完整流程验收范围](INTRANET-DOMESTIC-E2E-20261111.md)：计划与已有证据分开记录，未完成项保留待验收。

下文“已执行”为分阶段历史记录，其中旧CLI版本、空账号和未保存回调等描述只代表当时阶段；当前结论以以上索引及文末当前判定为准。

## 已执行

- 复核旧生产 hostname `racknerd-058889d`、运行服务镜像及前端正式包，仍为已盘点基线 `0.2.67 / overseas-light-20261107-d7c21a1`。
- 用现有 hengxin 账号验证 `.245` 为 `hengxin-ai-245`，确认 sudo 可用；为部署使用已有本地运维公钥加入新机 root authorized_keys，保留其余授权，不复制任何私钥。此变更只在新机。
- 新机确认约 1.9 TiB 可用、15 GiB 内存、4 GiB swap；原先无 Docker/应用，mihomo active。
- 按官方 Ubuntu 仓库安装 Docker 29.6.0、Compose 5.1.4、containerd 2.4.2、Python venv 与 socat；Docker daemon 配置 loopback 代理和日志轮转，docker/mihomo 均 active。
- 已创建新机 `/var/lib/hengxin-migration/lan-245`，root 所有、0700，用于私有复制候选。
- 新机 UID 999 为 mihomo、998 为 systemd-network；旧海外 UID 不能照搬覆盖，后续采用等效权限映射。
- 已复制并装载 9 个锁定镜像；7 个基础容器及前端、identity、国内 API、海外 API、Skills publisher 已启动。国内、海外 `/health/ready` 均返回 200，PostgreSQL/Redis/MinIO 均 up。
- 前端 688 个文件、海外 Skills 726 个文件逐项 SHA-256 校验；原生代码 1730 个文件完整校验。初次清单错误地排除源码 execution 子目录，已修复采集器、重新只读获取并独立审查后复核，最终无该遗漏。
- Codex 0.162.1 主程序、code-mode helper、包元数据与 bwrap 均复制并校验。codex（1001）与 hengxin-overseas（1002）真实身份运行版本命令成功，bwrap 基础隔离检查通过。只加载 bwrap 专用 AppArmor profile，没有全局关闭用户命名空间保护。
- 完整受控项目源码（commit `d7c21a1b3ac2296560663536bbda41712ef30273`）2005 个文件另存新端 `/opt/hengxin-lan/source-release-d7c21a1`；实际原生运行目录另保留生产补丁，未被仓库源码覆盖。
- 两个新库完成迁移链：国内 39 表、海外 44 表。国内白名单计数：users 30、identities 29、roles 23、申请 2、申请事件 4、成员审计 2、settings 1、settings audit 2。
- 海外白名单计数：members 8、roles 8、申请 6、申请事件 12、成员审计 11、Skills 管理审计 48、availability 24、settings 1。导入核对摘要和外键通过。海外初始 15 条 availability 只在字段及近期时间精确匹配时被事务内替换，失败回滚由真实 PostgreSQL 回归覆盖。
- 48 条海外技能审计中一条 reclaim 的嵌套旧业务历史字段经白名单裁剪，仅保留技能回收管理摘要；受保护导出记录了字段转换。旧库未改。
- 消费者启动前逐表确认白名单外业务表为空；控制门闩仅含迁移初始值。三个 Redis DBSIZE=0。两个对象桶已初始化，无匿名访问策略且无对象。
- 7 个原生 unit 候选已通过新机真实 systemd 255 verify；两项账号 broker 已启用并启动，active/running、NRestarts=0。其余消费者待代理/沙箱适配完成后启动。
- 钉钉应用 token 检测成功，但企业成员查询实际返回 `88 / 60020`，明确新出口 `202.96.165.231` 不在白名单。已请求用户在应用后台追加该 IP 并保留旧 IP；该项未通过，不以 token 成功代替登录通过。

## 验证命令摘要

`docker version --format '{{.Server.Version}}'` → `29.6.0`；`docker compose version` → `v5.1.4`；`systemctl is-active docker mihomo` → 两项 `active`。这些结果仅证明基础环境安装，不代表应用、登录或模型调用已经可用。

## 尚未完成

真实浏览器登录、Codex 新授权、登录后的角色/Skills 管理与完整业务生成、重启后真实任务、工作日持续观察。正式 DNS、旧生产服务保持；钉钉应用版本及出口白名单按后续授权处理，详见 2026-11-11 记录。当前健康检查不等于所有业务功能验收通过。

## 后续实测

- 16 个原业务/基础容器及新增 HTTPS 网关运行，7 个原生服务 active。新增容器代理 active，mihomo 保持 active；消费者启动前无旧业务任务。
- 同域名指定新 IP 的 HTTPS 返回 200，证书链校验通过，`X-Hengxin-Environment: lan-245`。网关仅监听 `192.168.1.245:443`，允许 `192.168.1.0/24` 和 `192.168.2.0/23`。
- Playwright 独立 Chrome 以 browser host-resolver-rules 映射原域名至 `.245`，未修改系统 hosts/DNS；已目视检查 1440×1000 登录页，资源和布局正常。未登录 `/api/identity/v1/me` 返回预期 401；真实登录尚未通过。截图：`output/playwright/lan245/page-2026-11-10T08-05-28-119Z.png`。
- 容器访问百度和代理 HTTPS 均 200，代理观测出口 `107.172.161.139`。独立非项目 Docker 默认 bridge 访问转发端口超时，项目容器访问成功，验证 IPAddressAllow/Deny 实际限制。
- Windows 测试端有 FlClash TUN，仅 TCP connect 成功会产生假阳性；补充发送 HTTP/PostgreSQL 协议数据后仅 443 获得响应，7890/7891/DB/Redis/MinIO/18080 均超时。结合新机真实监听确认内部端口未绑定 LAN 地址。
- 两个真实执行用户使用实际安装的 `sandbox_command` 运行 Codex 0.162.1 成功；沙箱 HTTPS 代理请求 200，宿主两套授权目录不可见，测试临时目录自动清理。
- 以 codex 身份从实际国内原生安装路径运行 workspace、managed credentials、海外 Skills owner configuration 回归：53 passed，2 项依赖弃用警告。未以这些测试替代真实登录/生成测试。
- 海外 worker 用户和 API 实际身份分别读取全部 726 个 Skills 文件成功。国内模型网关带现有凭据查询 models 返回 200、3 项；未进行收费生图，不能据此声称实际生成成功。
- 新端私有备份 `/var/backups/hengxin-lan/20261110-before-reboot`：国内/海外 custom-format dump 分别恢复到隔离库，39/44 表逐表计数相符，演练库删除；配置/Skills 备份中 726 个文件重新逐项校验。另备份 systemd、tmpfiles、AppArmor、Docker 配置与三份部署适配源码。
- 增加已独立审查的 `/etc/tmpfiles.d/hengxin-lan.conf`，开机先重建五个 `/run` 通信目录。运行 tmpfiles create 成功；仅新增目录定义，不删除既有内容。
- 复制末期只读核对旧生产：原 16 个容器 ID/镜像保持一致且均 Running。没有对旧生产执行部署、重启、停服或写库。
- 新机实际整机重启：boot ID 从 `0eb3d5bf-c9e0-4134-b4a0-31afab9cd15b` 变为 `0b2d4ea6-ef9a-449f-9f85-fd4e5ae83a0e`。17 个容器自动恢复，Docker/mihomo/转发/7 个原生服务均 active，系统 failed units=0。开机依赖启动期间短暂 502，后续国内/海外 ready 与 identity config 全部 200，无人工重启服务。
- 重启后两原生 Celery inspect ping 均收到 `.245` 节点 pong；两 API 以容器实际身份连接账号 broker socket 成功；容器代理 HTTPS 200。相关原生服务 NRestarts=0。
- 重启后重新核对 1730 个原生文件 hash，除三份已记录且审查的部署适配外与源一致。国内 users/identities/roles=30/29/23，海外 members/roles/availability/enabled=8/8/24/11，国内图片任务与海外任务均为 0。
- 管理操作过程中 Windows SSH 偶发连接超时，重试及 Paramiko 连接成功；未据此判定服务器所有网络路径长期稳定。一个工作日持续观察仍未执行。

## 访问方式

当前公司内网入口为 `http://192.168.1.245:8080`，无需测试启动器或修改 hosts/DNS。允许已确认的公司网段 `192.168.1.0/24`、`192.168.2.0/23`。普通浏览器中的 `https://zhitu.qhhengxin.top/` 仍访问旧生产；原独立浏览器指定新 IP 的 HTTPS 测试入口会跳转至新内网 IP 入口。钉钉白名单接口已通过，但新增 IP 回调尚待保存发布，不能据此称已完成真实登录。

## 当前验收判定

### 2026-11-11 钉钉配置与发布复核（历史阶段）

用户授权通过现有浏览器追加出口 IP 并发布应用版本。创建 `1.0.6` 草稿后，平台要求开发管理员审批；用户随后完成审批。版本列表实际显示 `1.0.6` 于北京时间 `2026-11-11 09:17:54` 已上线。这是钉钉应用配置版本，不是网站代码版本或公网入口切换。

首次操作时白名单**未保存成功**：最初点击保存后未等待异步错误提示，误把表单填写当成持久化成功。刷新实查仍只有 `107.172.161.139`；再次保存两 IP 时平台明确提示当前账号必须具备“应用管理权限”或“应用开发权限”。未继续尝试绕过权限。当时新端接口仍返回 `88 / 60020`，已要求用户切换有权限的账号，或由管理员保存两 IP 并保留原 IP。

用户随后通知白名单已添加。2026-11-11 再次从 `.245` 的实际 `hengxin-lan-identity-api` 容器调用钉钉应用 token 与企业成员详情接口，使用新端已迁移的身份绑定进行只读核验，结果 `enterprise_member_read=true`、`errcode=0`、无 `sub_code`。未输出成员资料或 token。此前 `60020` 白名单阻断已解除；本检查不等于完成浏览器 OAuth 回调或真实生成验收。

证据：`output/dingtalk-publish-20261111/version-1.0.6-published.png`、`whitelist-permission-block.png`。浏览器保留待管理员操作页；原回调地址及公网 DNS 未修改。

| 范围 | 判定 |
|---|---|
| 镜像/运行代码/前端/Skills 复制，白名单导入及旧业务排除 | 已完成上述实查；UI 管理行为另列待验收 |
| 新端基础依赖、IP入口、API readiness、worker通信、代理出网 | PASS；当前入口与专项结果见上方索引 |
| 数据库隔离恢复及 Skills 备份内容校验 | PASS；尚无新业务产物可做引用恢复验证 |
| 整机重启后服务自动恢复 | 早期部署重启PASS；后续HTTP/CLI/运行时修复后未再次整机重启，R04联合验收待完成 |
| 钉钉与登录页面 | 白名单接口PASS；用户确认登录成功、现有登录会话国内页面实测PASS；完整OAuth重走/手机/全部角色仍待验收 |
| Codex授权与真实执行 | 两侧既有broker真实模型请求PASS，国内一张原生图片编辑、海外PPT读取/续聊PASS；账号全生命周期、跨有效期刷新和完整海外工作流待验收 |
| PC/手机钉钉、故障恢复/并发完整业务演练、持续观察 | 未完成，不能声明整体功能验收通过 |

下一步：按尚未覆盖范围补全业务UI/API闭环、手机与权限组合、故障/并发、刷新及长期观察证据。正式DNS切换仍属另行授权阶段。

## 审查及部署边界

选择性导入与原生服务生成器复审 candidate `14b030e332df71a01b5717e34c97c2179a2ddd504026aaea95821727953c238c` 两阶段通过，独立复跑 native 12 项及数据 17 项，批准后执行。HTTPS/沙箱适配另行审查，首轮发现只读 nginx 的三类临时目录缺失，未部署失败候选，修复后重新审查。

曾尝试调整新机 mihomo 用户编号的操作被自动审批拒绝，未执行；采用应用侧明确配置 UID 1002 的等效隔离方案，mihomo UID 999 保持。证书沿用原域名证书，2026-12-14 到期；当前独立副本尚未建立自动续期。
