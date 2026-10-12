# Phase 17 本地接入与部署交接

本阶段只做本地隔离验证，未修改生产配置。钉钉真实回调、管理员授权及生产上线另行验收。正式海外入口仅接通身份，任务与管理功能按后续 Phase 接入。

## 服务与配置

- 国内：既有 `infra/compose.yaml`、独立国内数据库；API默认本机8008。
- 海外：`infra/compose.overseas.yaml`、海外数据库/Redis/MinIO保持独立；API默认本机18008。
- 统一身份：`infra/compose.identity.yaml`，独立Redis与卷；API默认本机8012。复制 `.env.identity.example` 至忽略的本地配置，分别生成两个服务密钥与Redis密码。Redis密码使用URL安全字符，避免连接串转义歧义。
- 国内配置 `IDENTITY_SERVICE_URL`、`IDENTITY_SERVICE_KEY`、`IDENTITY_PUBLIC_ORIGIN`；海外配置对应 `OVERSEAS_IDENTITY_*`。两个服务密钥分别等于身份服务中的 `IDENTITY_DOMESTIC_SERVICE_KEY` / `IDENTITY_OVERSEAS_SERVICE_KEY`，不能互换。身份服务不注入任何业务数据库或对象存储凭据。
- 统一 `PUBLIC_ORIGIN` 是浏览器实际访问的完整源，例如本地 `http://localhost:3013`，生产为HTTPS源，不含路径。三个服务配置一致。
- 国内已有钉钉配置保留用于旧登录兼容；新双入口仅使用统一身份服务的一次钉钉授权。钉钉网页回调改为同源 `/api/identity/v1/dingtalk/callback`，不能拿本地provider替身代替真实验收。

## 同机容器互联

三个Compose默认网络相互独立，容器内 `localhost` 不能指向另一个服务。上线时增加两个专用内部网络，仅连接API，不能把数据库/Redis/MinIO接到共享网络：

1. 创建 `hx-identity-domestic`、`hx-identity-overseas` 两个 `docker network create --internal` 网络。
2. 国内Compose本地覆盖文件为 `api` 追加外部网络 `hx-identity-domestic`，保留原 `default` 网络。
3. 海外Compose本地覆盖文件为 `api` 追加外部网络 `hx-identity-overseas`，保留原 `overseas` 网络。
4. 身份Compose本地覆盖文件为 `identity-api` 同时追加这两个网络，保留原 `identity` 网络，两个网络都使用别名 `identity-api`。
5. 两业务服务的 `*_IDENTITY_SERVICE_URL` 设为 `http://identity-api:8000`。业务容器只拿本业务服务密钥。身份API只挂身份Redis网络及这两个API连接网络。

覆盖文件中网络必须声明 `external: true`、`name: hx-identity-domestic` 或 `hx-identity-overseas`。使用 `docker compose -f <原文件> -f <覆盖文件> --env-file <本地配置> config --quiet` 校验合并结果，切勿输出真实配置到共享日志。之后按现有迁移服务先执行国内0027与海外0002，再启动API；不要向国内库执行海外迁移。

## 同源代理

公网代理只转发以下路径，并保留原路径、Host、X-Forwarded-Proto：

| 路径 | 本机上游 |
|---|---|
| `/api/identity/v1/` | `127.0.0.1:8012` |
| `/api/overseas/v1/` | `127.0.0.1:18008` |
| `/api/v1/` | 既有国内API `127.0.0.1:8008` |

`/internal/` 必须拒绝，不配置指向身份服务的兜底代理。身份回调带短期code/state，反向代理该身份路径关闭访问日志或清除query；服务自身已关闭access log。生产保持HTTPS，不设置跨域凭据CORS。

前端开发复用Vite代理：`VITE_IDENTITY_PROXY_URL=http://127.0.0.1:8012`、`VITE_OVERSEAS_PROXY_URL=http://127.0.0.1:18008`、`VITE_API_PROXY_URL=http://127.0.0.1:8008`。以development模式启动，浏览器进入 `/#/auth/business`。mock/demo模式仍是独立预览，不代表真实授权。

## 验证与故障

自动隔离测试：仓库根目录运行 `python hengxin-smart-image/infra/identity-test/run.py`；使用临时两库、Redis和三个API，只替换外部钉钉provider，结束清理。完整证据见 `OVERSEAS-PHASE17-INTEGRATION.md`。

未分配本业务角色显示暂无权限，成员只登记pending，不自动提权。角色管理接口在Phase18实现。身份Redis/服务故障时，绑定身份的两业务访问返回503，不自动退回旧身份；未绑定统一身份的旧国内会话保持原有兼容行为。全局退出撤销统一身份；本业务退出只影响本业务。业务停用独立生效。
