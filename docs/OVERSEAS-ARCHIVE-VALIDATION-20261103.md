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
