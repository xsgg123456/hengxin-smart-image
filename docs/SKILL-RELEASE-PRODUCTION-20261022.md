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

生产部署尚在执行，以下结果仅在取得真实凭据后补记。
