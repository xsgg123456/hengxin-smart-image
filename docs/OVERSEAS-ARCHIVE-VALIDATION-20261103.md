# 成品库字段与图片加载验证 · 2026-11-03

目标前端版本0.2.62。用户已授权两项功能、测试审查、中文Git提交及生产部署；合同见 OVERSEAS-ARCHIVE-PENDING-20261103.md。

## 已获得证据

- 字段组件单测5项、工作台生命周期及SKU选择6项通过；包含真实SFC六字段同序同值、四语言与历史缺值、单SKU自动归属、多SKU必选及SKU改变清除旧选择。
- 正式dist + 独立浏览器/隔离API：`frontend/tests/archive-fields.browser.mjs`通过，1366/390宽度、长品名、历史多SKU/语言缺值、真实归档请求SKU和图片ID、按钮与字段祖先裁切验证。证据 `output/archive-fields-browser.log`、`output/playwright/archive-fields/`。主Agent目视1366-single和390-multi，与既有弹窗样式一致。
- 生产只读基线：0.2.61、overseas_0026，归档后端已具备缩略图及HEAD/ETag支持；API容器与镜像、两原生服务及6配置文件摘要记录在 `output/archive-release/baseline.json` 与 `protected-baseline.json`。不记录凭据。

## 验证边界

字段浏览器请求由隔离API提供，不能代替生产写入验证。生产验收仅查看既有记录，不创建/删除任务或归档，不触发生图。图片缓存另以真实HTTP隔离fixture验证条件缓存和字节数；本地耗时不等同生产带宽。最终测试、审查与发布结果在完成后追加，当前不得据此宣称已交付。

## 集成回归

- `pnpm test` 全前端486项通过（0失败/跳过），`output/archive-all-tests-final.log`；类型检查exit 0，`output/archive-typecheck-final.log`；正式Vite构建通过，`output/archive-build-final.log`。
- `scripts/archive-cache/browser.mjs` 使用真实localhost HTTP与正式归档组件，覆盖缩略图、最多2并发、原图缓存与HEAD/304、下载哈希、取消筛选、重试、权限、删除、换号及窄屏。证据 `output/archive-cache/result.json`。首次6张原件共4,574,682字节，热缓存打开新增原件GET和正文传输均为0；不比较不同操作的计时为加速倍数。
- 原工作台共享缓存回归 `scripts/image-cache/browser.mjs` 18项通过，`output/archive-workspace-cache-regression.log`，防止归档新预取owner影响既有工作台。
- 发布工具 `python -B -m unittest discover -s scripts/release -p 'test_archive_release*.py' -q` 26项通过，`output/archive-release/release-final.log`。
- `pnpm audit --prod --json` critical=0、high=39、moderate=38、low=5，与上一版本一致，本轮无依赖变更。审查将核对本次代码，不宣称无历史依赖告警。

最终补充后台预取撤权清整套缓存用例后，完整前端486通过，类型检查再次exit 0。图片专项36通过，真实HTTP浏览器13项（含封面加载失败重试），原工作台18项回归均通过。

独立初审发现发布入口临时文件在内部replace失败后未清理，会阻碍自动/手动回退重试（MEDIUM）。已用仅清理本次拥有的临时文件修复，并新增内部replace单次失败、源读取失败、外部已有临时文件保留3项；发布测试26通过。产品代码未改变，最终候选99cf8747a7f5599cda2c3e70c3eaeabffe57206fabfcd9e24d1597a185125a18待复审。

终审独立确认 Stage 1 PASS / Stage 2 PASS，无未关闭HIGH/MEDIUM；发布26项由终审再次独立执行通过。最终批准候选99cf8747a7f5599cda2c3e70c3eaeabffe57206fabfcd9e24d1597a185125a18，报告 docs/reviews/OVERSEAS-ARCHIVE-FINAL-20261103.md。正式提交部署仍待下节记录。

## 正式生产交付

- 代码提交 `0943f5f90b8a83d6867588b9b21fb0b42cd870c2`（fix(overseas): 统一归档字段并接入成品图片缓存），生产前端0.2.62；正式包 `archive-20261103-0943f5f`，4,933,517字节，SHA256 `3d47ba7e64721aa916f12541409c50fbf67c5d5d449d590ff839d67bf5a60052`。正式包从已审已提交代码重新构建，隐私检查通过；上传后再次核验哈希。
- 生产目录 `/opt/hengxin-releases/archive-20261103-0943f5f`，`src`为包内容，`frontend-backup`保留旧入口、安装/验证记录。deploy和verify均exit 0，正式HTTPS入口及入口JS字节与包一致，所有前端安装文件哈希通过。
- 生产后端镜像、容器和启动时间、两原生服务PID/启动状态、schema overseas_0026及6份配置摘要与部署前一致；国内/海外readiness均200。本次仅静态前端更新，无后台重启、数据库迁移或数据回卷。
- 新建独立Chrome标签打开正式域名，目视成品卡片、成品详情、原图查看器及原任务归档弹窗。封面naturalWidth/Height为384×384，详情已加载小图同为384×384；查看器原图为1600×1600。归档弹窗六字段的名称、顺序和值与该成品详情一致，历史语言显示“未设置”，单SKU不再重复要求选择。
- 正式UI只读使用既有“1030-拉通测试-张帅”任务及8张归档。仅勾选一张以打开确认弹窗，随后取消并恢复未选状态；没有点击确认归档、创建或删除生产数据、提交图需或触发生图。实际写入与多SKU/缺值/故障路径以隔离测试为证。
- 服务器日志 `output/archive-release/production-requests.json`记录上线验证窗口17次thumbnail请求、2次原图HEAD304、无500。窗口含其他页面/用户活动，15次原图GET200不作为单次页面流量指标；不据此给出生产加速倍数或声称所有首次下载免等待。隔离HTTP中热缓存0新增原件GET/0字节及刷新304的精确结果见前文。
- 正式页面检查的error/warn日志为空。截图与字段/图片尺寸读取保存在本会话工具记录；本地隔离截图及自动化结果在前述output路径。没有用本地截图冒充生产截图。
- 发布过程未回退。回退入口为包内 `scripts/release/archive-deploy.py rollback --source <release>/src --backup <release>/frontend-backup`，保留新旧哈希资源；执行前核验未出现后续发布，不恢复数据库。本次发布后旧标签需刷新加载新前端。
