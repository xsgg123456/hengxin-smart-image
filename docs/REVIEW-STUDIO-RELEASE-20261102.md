# 0.2.56 静态发布独立审查

日期：2026-11-02。使用 code-review skill；只审查、不修复、不部署。

candidateId：`166c691f766a8111e5aecbbcfc3972aaba3eeb7dd38796bdb52717cd8332c842`。

范围：Product-Spec.md:3–6 四项业务变更、前端 package.json 版本、scripts/release/frontend-studio.py、test_frontend_studio.py 和发布记录。排除用户既有 AGENTS.md 与 release-builder/SKILL.md 修改。独立运行 review-status 确认 currentId 与派发一致；相对先前已审快照仅 package.json 和两个发布脚本发生代码变化。业务 diff 已重新阅读，不将此前禁止发布的授权边界沿用到本轮。

## Stage 1：PASS

| 条目 | 结论与证据 |
| --- | --- |
| 当前会话部分/全部原图 ZIP，空选禁用、加载、防重复、失败重试、切换取消 | 完整。frontend/src/api/overseas/studio-download.ts:5 按原 blob 字节生成 ZIP，:10 限定原图端点，:17 释放租约；frontend/src/views/overseas/studio/StudioDownload.vue:2、:13、:15、:19 分别对应控件状态、卸载取消、防重复、保存前检查。独立重跑四项专项测试通过。 |
| 勾选及归档行为保留 | 完整。frontend/src/views/overseas/studio/OverseasStudio.vue:24 保留原归档事件与禁用条件，:81 仅选当前会话图片；与 HEAD diff 已复核。 |
| 去任务名示例 | 完整。frontend/src/views/overseas/OverseasCreate.vue:24 删除 placeholder；共用修改表单不另设示例。专项组件测试通过。 |
| Wayfair 第二、既有标签/默认值/历史兼容 | 完整。frontend/src/views/overseas/platforms.ts:3；OverseasCreate.vue:102 追加历史选项；frontend/src/api/overseas/tasks.ts:84 默认 Amazon。专项组件测试逐项断言通过。 |
| 三品牌下拉、初始空、必填及旧品牌保留 | 完整。OverseasCreate.vue:40、:100、:101；tasks.ts:84、:89。专项组件测试验证固定选项及历史模型保留。 |
| 版本与生产基线 | 完整。frontend/package.json:3 为 0.2.56；frontend-studio.py:43、:77、:79 强制包目标 0.2.56 和部署基线 0.2.55。生产只读基线记录于 docs/STUDIO-DOWNLOAD-RELEASE-20261102.md:9；本 reviewer 未另连生产。 |
| 备份、原子切换、回退 | 完整。frontend-studio.py:65 使用同目录临时文件及 os.replace；:88–98 先备份四类入口/元数据，记录 COMPLETE；:100–123 先增资源后替换入口并验证；:124–130 异常恢复；:134–150 显式回退校验当前发布清单并恢复。独立运行五项部署保护测试通过。原子性是单文件级，两个入口不构成跨文件事务；旧资源保留使短暂双版本入口均可加载。 |
| 不重启后端、不迁移数据库 | 完整。frontend-studio.py:74–150 只写前端静态文件、版本清单和备份，无进程管理、服务重启、数据库操作；test_frontend_studio.py:35 检查 API_RELEASE.json 与旧资源不变。 |
| 允许清单、隐私及快照绑定 | 完整。frontend-studio.py:16–20、:29、:37–45、:53–54 检查已提交源、审查状态、扫描静态制品及加入 commit/candidateId；package-overseas.py:130、:147 检查路径、后缀、压缩内容和固定 PDF.js 资源；package-management.py:62 执行隐私检查。本 reviewer 独立重跑 650 个文件扫描通过。 |

前端路径均相对 hengxin-smart-image/frontend；发布脚本相对 scripts/release。部分实现：无。未实现：无。Spec 漂移：无；发布已在 Product-Spec.md:6 明确授权。无 HIGH 功能问题，进入 Stage 2。

UI 一致性：重新查看真实浏览器产物 output/playwright/studio-download/desktop.png 与邻居 form.png。下载与归档控件同高，品牌和平台复用同类下拉，任务名为空输入，无新增布局体系；对应 OverseasStudio.vue:24、StudioDownload.vue:2、OverseasCreate.vue:40。复用上一轮浏览器证据而非声称本轮重开生产页面；此前完整视觉及窄屏证据见 docs/REVIEW-STUDIO-SMALL-20261102.md。

## Stage 2：PASS

- 质量：frontend-studio.py 共 161 行，发布、备份、验证、回退职责拆函数，无新增外部依赖；所有部署写入前先做基线、制品摘要和资源冲突检查（:74–87）。业务下载使用类型参数，finally 释放资源，组件卸载取消（studio-download.ts:5、:17；StudioDownload.vue:13）。
- 安全：制品只收集 dist、前端 package.json 和当前发布脚本，未收集后端配置、用户文件、报告或工作区指令（frontend-studio.py:37–42）。源路径验证及资源目标 symlink 检查见 :58–62、:85。无新增 shell 拼接、eval 或 HTML 注入入口。独立静态资源扫描结果如下；完整打包仍须在主 Agent 同快照批准并提交后执行，不能将预扫描称为已生成发布包。
- 测试真实性：test_frontend_studio.py:35、:43、:50、:56、:62 使用临时目录实际执行 deploy/rollback，覆盖后端和旧资源保留、损坏制品拒绝、资源同名冲突、切换后故障恢复与显式回退。故障注入发生在安装后 verify，不是仅测空壳函数。测试未覆盖进程强杀、磁盘永久故障或并发管理员发布，不声称这类故障可自动恢复。
- 历史依赖风险：docs/STUDIO-DOWNLOAD-RELEASE-20261102.md:16 记录 audit high 73、moderate 55、low 11、critical 0；依赖及锁文件未变。本次 PASS 为指定增量范围，不代表全仓漏洞清零。

## 原始验证输出

独立执行 `python scripts/release/test_frontend_studio.py`，退出 0：

```text
.....
----------------------------------------------------------------------
Ran 5 tests in 0.152s

OK
```

独立执行 `pnpm exec tsx --test tests/studio-download.test.ts`，退出 0：

```text
✔ 所选图片按鉴权原图获取，部分/全部ZIP保留原始字节且同名不覆盖 (23.1216ms)
✔ 空选/外部地址/读取失败/取消不产出残缺ZIP (1.3256ms)
✔ 下载按钮空选禁用，忙碌防重复，失败可重试，卸载不触发保存 (128.0197ms)
✔ 图需表单保持默认及历史值，平台顺序与品牌下拉按要求 (56.8018ms)
ℹ tests 4
ℹ suites 0
ℹ pass 4
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1081.4709
```

存在既有 pnpm 字段迁移 WARN，不影响上述退出码。

读取主 Agent 正式构建原始日志 output/studio-release-build.log（未重复构建），原始节选：

```text
> hengxin-smart-image-frontend@0.2.56 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build

🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4703 modules transformed.
✓ built in 31.20s
```

独立调用 package-overseas.collect_assets 对当前 dist 执行同一允许清单和隐私检查，退出 0：

```text
{'privacy': 'PASS', 'files': 650, 'bytes': 10183888}
```

最终批准须由主 Agent 使用 review-approve 登记本 candidateId；本报告不写 clean，不替代实际打包后验证或上线后的真实页面验收。
