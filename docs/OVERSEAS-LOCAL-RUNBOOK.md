# 海外 Phase 16 本地独立运行

设计与验收顺序：先配置独立资源和最小权限账号，再运行海外迁移，最后启动 API 并检查真实依赖。复用现有 Dockerfile 与 MinioStore，不复制工程，不启动国内 Worker。海外 Worker/CLI 尚未实现，目录仅预留。

资源契约：Compose project 默认 `hengxin-overseas`，独立 bridge 网络，PostgreSQL、Redis、MinIO 和执行/Skill 卷均为项目私有；资源端口不发布，API 仅绑定 localhost。数据库 `hengxin_overseas`，`overseas_owner` 执行迁移，`overseas_app` 只有连接、schema 使用、业务表 DML 和序列使用权限，无建库/建角色/建 schema/建表/临时表权限。bootstrap 管理密码只进入初始化容器，API 不持有管理或 owner 密码。MinIO 应用账号只有指定私有桶读取/写入/删除/列举和 GetBucketPolicy 权限，不允许列所有桶或管理服务。

所有应用变量使用 `OVERSEAS_`，选择器为 `HX_BUSINESS_CONTEXT=overseas`。bootstrap 的 PostgreSQL/MinIO 原生变量仅用于资源容器。Redis 必须认证。密码必须分别生成，推荐 `python -c "import secrets; print(secrets.token_hex(32))"`；数据库/Redis URL 中密码须 URL 编码，Compose 拼接模式使用 hex 密码最简单。示例无真实密钥，不把实际 `.env.overseas` 提交到 Git。

从代码根目录执行：

```powershell
Copy-Item infra/.env.overseas.example infra/.env.overseas
# 填写全部空白密码和应用 access key，检查 18008 端口未占用。
docker compose --env-file infra/.env.overseas -f infra/compose.overseas.yaml up --build -d
curl.exe --fail http://127.0.0.1:18008/api/overseas/v1/health/live
curl.exe --fail http://127.0.0.1:18008/api/overseas/v1/health/ready
```

启动链：Postgres healthy → pg-bootstrap → migrate；MinIO healthy → minio-bootstrap；Redis healthy；三者成功才启动 API。迁移命令 `alembic -c alembic.overseas.ini upgrade head`，仅使用海外元数据和 `overseas_alembic_version`，初始 revision `overseas_0001`。初始化脚本可重复执行；修改密码后需重新运行 bootstrap 和重建 API。不要对已有数据卷使用 `down -v`，常规停止使用 `down`。

三个目录卷由无网络的 `roots-init` 将顶层归属设置为应用 UID 10001，仅挂载海外卷；API 不以 root 运行。版本表仅允许运行账号 SELECT，bootstrap 重跑不会恢复其写权限。

MinIO 固定版本在未授权 ListAllMyBuckets 时仍允许 ListBuckets 返回按桶权限过滤的结果；只允许看到应用自身桶，其他桶不可见，IAM 未授予全桶枚举或 admin 权限。验收创建额外隐藏桶验证此边界，不将官方过滤行为误记为全桶管理权限。

真实隔离验收脚本在 `infra/overseas/verify_resources.py`：创建唯一 `hx-overseas-p16-*` 项目和独立国内替身，仅使用 `*_test` 数据库、随机凭据与私有测试桶；验证海外迁移、DML/DDL权限、Redis认证、私有桶以及双向数据库/桶凭据互访拒绝，最终只清理脚本创建的资源。它不接触已有容器或生产服务，也不证明真实身份认证、任务工作流或收费 CLI 已完成。

先通过上述 Compose 构建镜像，再从代码根目录运行 `python infra/overseas/verify_resources.py`。可用 `OVERSEAS_VERIFY_IMAGE` 指定另一个已构建的同项目镜像；验证运行真实镜像，不把本地源文件覆盖进镜像。测试会停止自己创建的三个依赖，逐项断言 ready 503 / live 200 / 恢复 ready 200；国内替身用于验证独立凭据边界，不代表国内生产环境已核验。随机测试密钥仅存临时文件，完成自动删除；不会读取国内 `.env` 或接受继承的 `OVERSEAS_` 资源配置。

参考：[PostgreSQL 权限](https://www.postgresql.org/docs/16/ddl-priv.html)、[默认权限](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html)、[MinIO S3 API](https://minio.community/community/minio-object-store/reference/s3-api-compatibility.html)。
