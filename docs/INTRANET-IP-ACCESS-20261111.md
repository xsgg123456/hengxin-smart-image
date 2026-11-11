# 内网 IP 直接访问适配 · 2026-11-11

用户明确要求像恒鑫智邮一样直接用内网 IP 加端口访问。本轮入口为 `http://192.168.1.245:8080`，覆盖此前公司 DNS/原域名内网解析方案；不操作公司路由器、公网 DNS 或旧生产。保留钉钉企业身份、原用户权限、现有功能与数据隔离。

1. 入口：仅在 `.245` 内网地址开放 8080，保留公司网段限制、上传与 SSE 代理配置；其他内部服务继续只监听 loopback。完成标准：公司电脑正常 HTTP 浏览器加载完整前端和接口。
2. 登录：identity 与两业务使用相同内网 origin；明确启用的内网 HTTP 配置只接受 RFC1918 IPv4，不通过切换 development 模式绕过生产校验。不降低默认 HTTPS 要求，Cookie 保留 HttpOnly/SameSite 与原路径、过期策略，保持 CSRF/Origin 校验。钉钉追加内网回调，保留旧生产回调；真实授权完成前不得宣称登录验收通过。
3. 前端：HTTP 浏览器缺少 randomUUID/subtle 时，采用密码学安全随机 UUID 和等价 SHA-256 实现；不使用 Math.random，不绕过文件摘要校验。验证任务请求键、上传/技能摘要、编辑标注等调用点。

   HTTP 环境不支持目录写入选择器时，Skills 下载使用经文件摘要核验的 ZIP，保留完整根目录、空目录和二进制文件；提示“已发起下载”，不冒称完成磁盘写入/读回，不因无法验证本地落盘而触发服务器包回收。HTTPS 的原目录保存流程保留。复制操作提供 HTTP 兼容或可手动复制的反馈，剪贴板图片保留粘贴/文件选择入口。
4. 部署：限定新服务器，备份相关配置/文件，锁定现有运行基线后最小覆盖，配置/代码独立审查后应用。验证健康、Origin 拒绝、Cookie、登录跳转与页面。原生 worker/任务数据不因访问入口修改而重建。

实际业务生成仍取决于已有待办 Codex 独立授权，本轮不以页面或 OAuth 成功替代完整生成验收。

## 验证与候选准备

- 前端全量测试 541/541、类型检查、生产构建通过；版本 `0.2.67-lan.1`。日志 `output/intranet-ip-frontend-{typecheck,all-tests,build}.log`。HTTP ZIP 是目录写入受浏览器限制时的替代交付方式，未调用远端回收接口。
- 后端内网 HTTP 边界 59 项通过；两现有 API 容器实际依赖与环境中加载候选配置成功，开发身份未启用。部署准备隔离/篡改拒绝/源码漂移拒绝 3 项通过。
- `.245` 私有候选目录 `/opt/hengxin-lan/ip-access-20261111`，前端 695 文件，上传包 12,195,840 字节；上传摘要及逐文件清单通过，两个 API 源文件与固定运行基线一致。Compose 和 Nginx 配置预检通过。首次 Nginx 预检的独立网络没有宿主 LAN 地址，修正为 host 网络执行 `nginx -t` 后通过，未启动临时服务。
- 钉钉页面填入原回调及新增内网回调后，保存明确被当前账号权限拒绝（要求应用管理或应用开发权限）。刷新确认新增回调尚未持久化；已请求用户用添加白名单时的有权限账号保存。未宣称钉钉登录通过。

用户随后明确“先部署，回调先不管、搁置”。本轮继续部署与未登录访问验收，不再修改钉钉配置；登录及登录后的业务验收留待补回调后执行。已刷新后台清除未保存的编辑。

首次应用时，普通 Chrome 已加载 `.245:8080` 的前端，但部署脚本对 `/health/ready` 的错误检查得到 404，触发回退。检查确认当前 Compose 已恢复到备份，两 API healthy；实际 Docker Healthcheck 与真实请求确认正确路径分别是 `/api/v1/health/ready`、`/api/overseas/v1/health/ready`，均 200。仅修正部署健康检查路径后重新审查；此处不以首次页面打开代替最终部署成功。

## 最终部署结果

2026-11-11 已部署到 `http://192.168.1.245:8080`，最终脚本返回 `APPLIED`、退出 0。后续排障发现 Compose 报 started 后 nginx entrypoint 尚未写入 `/run/nginx.pid`，即时 reload 失败；回退中的同一失败会跳过外层入口 reload。新增等待重试与 finally 重载外层入口，真实延迟 3 秒启动的隔离 nginx 容器复现验证通过；测试容器已删除。最终 5 项部署故障测试通过，代码快照 `1727aa01ca08192c1d0da00cee2abb1bfa7cf16104447c0c21efca05f4fd08da` 经 [独立增量审查](reviews/INTRANET-IP-RELOAD-REVIEW-20261111.md) 两阶段通过并登记。30 秒是重试窗口，不承诺严格的墙钟上限。

- 公司 Windows 普通 Chrome 直接加载 IP 入口，完整呈现恒鑫智图登录页，未使用 hosts、特殊浏览器启动器或 DNS 修改。
- 首页、身份 config、国内/海外 ready 均 200，响应 `X-Hengxin-Environment: lan-245`；未登录 me=401，内部接口外部路径=404。HTML 与入口 JS 逐字节匹配本轮构建。
- 钉钉 authorize=303，redirect_uri 正确指向内网 IP 的 `/api/identity/v1/dingtalk/callback`；仅检查本服务生成的跳转，不等于平台已接受或登录成功。
- 身份 state Cookie 为 HttpOnly、SameSite=Lax，HTTP 下不带 Secure；两业务实际容器使用运行设置生成 Cookie，同样通过上述属性验证。错误 Origin 注销请求=403，同源=204，没有绕过身份和权限。
- 17 个容器运行，两个 API healthy；仅国内/海外 API、identity、web 四容器发生预期重建，其余 13 容器 ID 与部署前相同。核对的五项原生 worker/outbox/broker 服务 PID 和 active 状态均未改变。
- 入口和 Compose 设置已持久化，保留原 restart 策略；本轮未再次整机重启，不把此前重启结果冒称为本轮 HTTP 改动的整机重启实测。
- 配置备份在 `.245:/opt/hengxin-lan/ip-access-20261111/{compose.before.json,edge.before.conf}`；原前端目录仍保留，新包独立挂载。旧公网生产、公司网关和 DNS 均未改。

尚未完成：钉钉内网回调保存/发布及真实登录，登录后的功能验收、Codex 独立授权与实际生成。用户随后再次询问如何追加回调，已提供保留原地址、英文逗号追加新地址的完整内容；截至本记录尚未取得平台成功保存/发布证据。

## 国内入口菜单模式修正

2026-11-11 用户反馈已配置回调且可以登录，进入国内业务却跳到 `?workspace=domestic#/500`。实查国内 API 日志记录 `GET /api/v1/api/v3/system/menus` 返回 404：首轮内网构建误设 `VITE_ACCESS_MODE=backend`，触发模板后端菜单接口；项目既有 `.env.example` 和 Vite 默认均为 `frontend`，国内既有路由由前端按已认证角色过滤。修正构建模式不会绕过后端身份与权限校验。

本次按序执行：固定内网构建入口（显式 frontend 菜单模式）→ 类型检查和构建 `0.2.67-lan.2` → 增量独立审查 → 仅 `.245` 更新前端挂载、保留上版回退 → 普通已登录浏览器进入国内工作区并确认不再请求不存在的菜单接口。海外与全部后端服务保持。

Codex 版本只读实查：从两项实际 worker 进程的环境找到可执行文件，分别以 `codex`、`hengxin-overseas` 真实服务用户执行 `/opt/hengxin-runtime/codex-0.162.1/codex --version`，均返回 `codex-cli 0.162.1`、退出 0。

修正已完成部署：`0.2.67-lan.2`，候选 `56a094272e2962b4fd4fb0392dcef56b2de1b5abd583065559c3405194d9b461` 经 [两阶段独立审查](reviews/INTRANET-DOMESTIC-MENU-REVIEW-20261111.md) 并登记批准。新目录 `.245:/opt/hengxin-lan/frontend-menu-fix-20261111/frontend` 保留上版静态哈希资源，并覆盖本轮经 695 项 SHA 校验的文件；备份 Compose 在同级 `compose.before.json`。只重建 domestic-web，其余 16 个容器 ID 不变，17 容器均运行；HTTP 首页与本轮 HTML 摘要相符。

真实普通 Chrome 以用户已登录会话，从旧 `#/500` 页面点击“返回首页”成功进入国内 `#/api-image-edits/create`，上传区、表单、菜单完整呈现。随后用户在同一标签页自行浏览管理页面，观察到 Codex 账号管理页面正常加载；未争用用户控制继续强制导航。部署后日志中错误菜单接口请求为 0，`/auth/me` 1 次=200、换图任务接口 2 次=200、管理接口 13 次=200。截图 `output/intranet-menu-fix-20261111/domestic-home.png`。未发起实际收费生图；Codex 授权仍独立于本次入口修复。

后续版本更新：同日按用户授权，国内/海外 Codex 执行器及账号管理已从 0.162.1 切换到官方稳定版 **0.167.1**；详情与回退位置见 [内网 Codex 升级记录](INTRANET-CODEX-UPGRADE-20261111.md)。本节前面的 0.162.1 为升级前实查记录。

## 后续验收状态

后续状态以本文“国内入口菜单模式修正”和[运行时验收](INTRANET-CODEX-RUNTIME-FIX-20261111.md)为准：用户已确认回调配置及登录成功，现有已登录会话国内页面通过，两侧既有broker真实模型请求通过。前文“尚未完成”是该部署阶段的历史记录，不是最新状态。
