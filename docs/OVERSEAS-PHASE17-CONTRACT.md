# Phase 17 统一身份与双业务会话合同

实施顺序：统一身份服务和公共会话原语 → 双业务独立兑换及海外迁移 → 正式前端登录/双入口 → 本地真实API联调、一期回归与独立审查。各步未验证前均不得标完成。

## 身份与业务边界

1. 钉钉只授权一次。复用现有企业验证、换码、SDK及登录布局，保留原国内登录兼容路径；不复制钉钉接入。将可复用身份逻辑与国内ORM/角色检查解耦。
2. 中立身份服务使用独立Redis保存短期OAuth state、统一身份会话和一次性业务ticket，不连接任何业务数据库、图片存储或执行队列。入口 `/api/identity/v1`，独立进程 `app.identity.main:app`。仅此服务需要钉钉应用密钥。
3. 浏览器统一身份cookie为 `hx_identity`，HttpOnly、SameSite=Lax、HTTPS时Secure，Path=/api/identity/v1；只表示企业身份，不包含业务角色。OAuth state cookie绑定浏览器且一次性消费；登录失败不能重用state。
4. 身份服务根据当前有效身份签发60秒一次性ticket，显式绑定 domestic/overseas，ticket不放URL/日志/localStorage。业务服务通过各自独立服务密钥向身份服务兑换；不同业务不能兑换对方ticket，任何篡改/过期/重放都拒绝。身份服务不持有业务资源凭据。
5. 业务服务只存储本业务成员/角色/会话，独立随机token及哈希；海外cookie `hx_overseas_session`，Path=/api/overseas/v1。国内继续 `hx_session`。不得根据浏览器角色、国内cookie或国内管理员配置授予海外权限。
6. 新业务会话绑定统一身份会话标识，受统一身份剩余寿命与本地会话TTL共同限制。每次受保护请求校验本地会话、成员启停/授权和统一身份仍有效；身份服务不可用时失败关闭。国内旧会话保持既有行为，不要求迁入统一身份库。
7. 全局退出撤销统一身份，绑定该身份的两业务会话均不可继续访问；本业务退出只撤销本业务token。关闭海外成员不修改国内成员或统一身份。过期/撤销结果不可由客户端伪造。服务端只存token哈希。
   有效ticket兑换时撤销浏览器携带的旧本业务会话，即使新身份在本业务未授权也不能继续沿用另一个成员的旧cookie。
8. 修改身份/兑换操作要求同源自定义请求头 `X-HX-Request: 1`，不开放跨域凭据CORS。内部兑换/会话核验接口要求业务服务密钥，公网反向代理不暴露 `/internal/`。

## API与页面合同

- 身份：GET `/api/identity/v1/config` → `{configured,corpId,clientId}`；GET `/me` → `{name}` 或401；GET `/dingtalk/authorize`；GET `/dingtalk/callback`；POST `/dingtalk/container` `{code}`；POST `/tickets` `{business}` → `{ticket}`；POST `/logout` →204。
- 业务：POST `/api/v1/auth/identity/session` 与 `/api/overseas/v1/auth/identity/session`，body `{ticket}`；成功写本业务cookie并返回用户，待授权/禁用403。GET各业务 `/auth/me`；POST各业务 `/auth/logout`。
- 内部：POST `/internal/redeem` body `{ticket}`，`X-HX-Service-Key`验证服务与ticket业务，返回 `{member:{corp_id,provider_user_id,union_id,name,department},identity_session_id,expires_at}`；POST `/internal/check` body `{identity_session_id}` 返回 `{active:boolean}`。服务身份由独立密钥决定，不信任传入business。
- 前端加载统一身份，再用独立ticket分别建立业务会话，显示两个入口；403显示暂无权限，网络故障显示重试，不能误记为无权限。海外单授权不触发国内bootstrap。进入国内后沿用原启动链；进入海外使用独立身份守卫。
- 复用 `BusinessEntry.vue` 及已有登录组件；正式页面不提供模拟身份切换。海外业务/管理API尚未实现，正式海外入口此Phase仅呈现真实登录身份与业务切换/退出，不把模拟任务操作接入正式入口；原预览仍独立保留供后续接入。
- 海外成员身份及角色关系在海外库落地，为Phase18维护接口提供基础；本Phase无成员管理接口、自动管理员或默认运营授权。未授权身份可登记pending，以后授予角色；此举不授予业务访问。

## 复用与验收

公共代码保持单份：钉钉provider、随机session/token哈希与过期判定、错误中间件、数据库池、前端请求及登录视觉；业务ORM与身份服务存储分离。实际外部钉钉认证需要用户真实配置，本地使用可控provider替身验证协议，不宣称生产验收。

验收四种授权组合、OAuth绑定/重放、ticket篡改/跨业务/重放/过期、会话过期/单边禁用/全局退出/服务失联、国内登录回归、海外独立迁移、真实本地API+浏览器联调。部署配置明确身份独立Redis、服务密钥和同源路由，不访问生产或调用收费模型。
