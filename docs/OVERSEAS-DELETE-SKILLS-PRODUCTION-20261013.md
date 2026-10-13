# 海外任务删除与14个Skill生产交付

2026-10-13发布完成，生产站点 https://zhitu.qhhengxin.top/ 。本轮不包含另一工作流的国内/海外成员目录隔离整改。

## 已发布版本

| 项目 | 实际结果 |
|---|---|
| 应用提交 | `3a060c8cebcebe876931b3b1c636ecb6bc2fb9b5` |
| 前端版本 | `0.2.28` |
| 发布标识 | `overseas-20261013-3a060c8` |
| 海外数据库 | `overseas_0013`；国内仍为0027 |
| 应用镜像 | `sha256:ec4817ea4118d4d275732cca5ad9c881b466ed6e98c7802e0342ab9351856e8e` |
| 发布包SHA256 | `db71e3a08a448b5212d0ca5d5528ccdc4013d5ae7bc1269885efea512aed5f04` |
| 服务器发布目录 | `/opt/hengxin-releases/overseas-20261013-3a060c8` |
| 数据备份 | `/opt/hengxin-backups/overseas-20261013-3a060c8`；完成标记及pg_restore清单检查通过 |

打包仅消费受审提交，1408文件、8,574,604字节，逐文件校验通过。生产构建镜像内1845项测试通过，167项显式依赖跳过、1项排除；完整本地Linux、真实PG及HTTP流程的补充证据见 `OVERSEAS-DELETE-SKILLS-VALIDATION-20261013.md`。国内和身份服务容器身份前后相同，没有重建这些服务。

## Skill安装实测

- 7个源文件夹对应3+2+1+2+2+2+2，共14个完整包、181文件、111,321,938字节。完整资源都安装，未合并同名变体；必要唯一名称适配比源件增加118字节。
- Skill发布SHA：`7f409fdc92401c25f559899e3529720480b482cee0bfbbbca8daaecb0c0c2bbc`。
- API与原生worker统一使用 `/var/lib/hengxin-overseas/local-skills`；API为只读bind。原先空named volume保留。
- API、native及真实uid999 sandbox报告同一device=64770、inode=1708242；逐包全部181文件哈希与只读检查通过，只发现所选Skill，模型调用为0。
- 网页实际显示14项，仅名称、描述列及搜索/刷新；没有添加入口。沃尔玛分别显示“沃尔玛新品主图 · 原版”和“沃尔玛新品主图 · 新版（9.27）”。工作台沿用同一已安装目录接口，其选择与轮次冻结已在隔离HTTP/UI流程验证。

## 任务删除与归档

线上超级管理员任务列表显示删除入口；打开“测试”任务确认框，完整名称为空时确认按钮禁用，取消后原有两条任务均保留。没有执行任何生产任务删除。线上成品库为0套，空状态正常，因此不将本次线上验收冒充生产归档删除下载实测。

隔离环境已实际完成：管理员删除、其他四角色拒绝、清理CLI任务私有目录/业务记录/未归档对象、保留另外任务及共享资源；两张已归档图片在删除后独立查看、原图下载、ZIP下载，其字节哈希与删除前一致。改派权限、删除竞争、事务回滚、历史归档迁移均通过真实HTTP/PG验收。

## 发布期间发现的问题及处理

第一次切换时，发布进程umask077令公共 `local-skills/releases` 父目录成为700。真实worker校验失败后门禁维持海外入口关闭，并停止新API；未丢弃备份、未回退迁移后的数据库。

通过namei确认路径为海外专用、root所有、无链接，只将这一个公共父目录改为755；保持凭据、备份及任务私有目录权限。使用原受审发布代码与原版本/备份/空队列/镜像校验重新启动、复验并恢复海外入口，结果为 `OVERSEAS_UPDATE_COMPLETE overseas-20261013-3a060c8`。

运维脚本另补显式父目录校验及chmod755，新增真实Linux root用例覆盖首次创建、已有700及拒绝链接；私有目录仍700。相关发布回归57项通过，独立审查新增3项全部通过，候选 `deac809ca46f4033c0ad7acd4ae1acfd3c525e9618ffbeacbd86974e4831f0c5` 已批准。该修正属于发布工具，不改变本次业务镜像；原release源码与manifest保持不可变。

## 原始证据与边界

本地证据目录：`output/release/overseas-20261013-3a060c8/`。

- `verification.json`：部署结果、镜像、迁移、备份及其他业务未变。
- `SKILLS_VERIFIED.json`：实际14包、uid999、共享inode及只读逐包结果。
- `server-deploy.log` / `server-recovery.log`：首次门禁失败与恢复成功，保留完整历史。
- `installation-tests.log` / `permission-regression.log`：镜像测试及权限回归。
- `screenshots/skills-walmart-production.jpg`、`task-delete-entry-production.jpg`、`delete-confirm-production.jpg`、`archives-production.jpg`：真实线上页面。

未触发付费模型调用，未删除用户真实任务。本轮不验证成图质量或生产字体完整性；原14包没有附带字体。现有依赖审计告警及跳过原因见总验收文档。
