# 海外设计任务中心与反馈专项发布

本次发布包含海外设计任务中心、自定义生图、继续任务、SKU 归档、意见反馈及管理、关于我们和纯前端创作工具集。用户已授权短暂停用海外工作台、核验备份后迁移海外数据库，并更新共享登录页的海外跳转。生产目标为 `hengxin-ai-245`，业务入口为 `192.168.1.245:8080`。

## 基线与候选

2026-11-20 维护前只读核对了生产台账、运行工具及数据库。海外后端为 `aef44a628dae`，海外前端为 `3b38a2c44514`，共享前后端为 `2bc8acc7ecf4`，国内前后端为 `009a1808f5c4`。海外迁移版本为 `overseas_0026`，国内为 `0046`，台账无待处理发布。工具安装基线为 `acc16ece689edbb7`。

用 `scripts/release/intranet/package_release.py` 从同一个已审 Git 提交分别打包 `--scope overseas` 和 `--scope shared`。对两包检查文件清单及其 SHA256、来源提交、前端构建范围、敏感文件和两份海外迁移脚本。上传到 `/opt/hengxin-lan/` 下的版本专属文件名，在服务端核验 SHA256，再分别用当前安装工具的 `stage.py <包> --name <版本名>` 暂存两个候选。

安装维护工具时核对当前指针和旧版清单的全部文件摘要。将已审提交的工具改动装入版本独立的目录，在最终安装路径隔离运行工具测试，通过后在发布锁内切换 `current`。业务台账的内容须与安装前一致。

## 切换与恢复

在服务器上使用 `/opt/hengxin-intranet-tools/current/scripts/release/intranet/` 下的工具。以 `<海外目录>` 和 `<共享目录>` 表示两次暂存返回的绝对路径。

1. 运行 `release.py design-prepare --scope overseas --mode full --release <海外目录>`。核实目标组、固定基线和候选的变更范围，确认排空、备份、迁移和恢复所需服务可用。
2. 运行 `release.py design-deploy --scope overseas --mode full`。海外侧停止接纳并排空任务，核验备份后由专项工具运行两步迁移。`overseas_0027` 增加反馈、处理授权与索引，`overseas_0028` 为任务和归档增加设计类型并扩展名称长度。核对原有数据和业务账号权限、候选代码、目标版本与服务健康。
3. 排空失败时恢复接入。中断时通过 `release.py design-status --scope overseas --mode full` 确认阶段，用 `design-recover` 恢复。迁移提交前可以恢复原海外服务，提交后向前恢复同一候选。保留现有业务数据库、账号、图片和素材。国内服务在维护期间继续运行。
4. 海外版本验证完成后，运行 `release.py design-shared-prepare --scope shared --mode frontend --release <共享目录>` 核对共享前端与已发布海外后端的来源提交，再执行 `release.py deploy --scope shared`。共享后端继续使用原版本。
5. 执行 `release.py verify` 和 `release.py status`，核对两组 current/previous、数据库版本、国内与共享后端运行身份、待处理事务和清理结果。通过正式登录入口检查海外跳转、设计任务中心、继续任务、反馈和创作工具集。14 张工具卡用于展示封面、文案与悬停动效。

本页记录维护授权和操作路径。实际发布版本、包摘要、验收及恢复情况以生产回执为准。
