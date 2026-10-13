# 镜像源文件完整性增量审查

- 日期：2026-10-13。
- candidateId：`231d99b72040527332869fb64de3533d8fa39464eba1e4ae00589726873b6e25`。
- 基线：`823fc85`；业务全量范围沿用 `docs/reviews/requirements-20261013.md:1`。本报告仅覆盖当前五个代码文件差异及发布记录补充，不重复声称全量产品验收。
- 范围：`hengxin-smart-image/frontend/vite.pdf-assets.ts`、`scripts/release/overseas-deploy.py`、`scripts/release/package-overseas.py`、`scripts/release/test_overseas_deploy.py`、`scripts/release/test_package_overseas.py`。
- 已读取 code-review 技能、交接协议、相关 Spec 原文、构建/发布调用链、Dockerfile、差异和既有 PDF 增量报告。开始及结束 review-status 的 currentId 均为本候选；审查期间未发现代码变化。

## 结论

**Stage 1：PASS；Stage 2：PASS。** 无 HIGH/MEDIUM 阻断问题。主 Agent 可为本候选登记两阶段 PASS；本报告不代表实际服务器安装测试或生产发布通过。

## Stage 1：Spec Compliance

| 检查项 | 结论与证据 |
|---|---|
| 安装测试前验证镜像代码 | 完整实现。发布记录 `docs/OVERSEAS-REQUIREMENTS-RELEASE-20261013.md:22` 要求逐项核对。`scripts/release/overseas-deploy.py:26` 禁用构建缓存，`:27` 捕获实际镜像 ID，`:28` 至 `:40` 从发布清单提取所有 backend 文件并在该镜像内逐文件比较 SHA256。`hengxin-smart-image/infra/Dockerfile.backend:4`、`:8` 将 backend 内容映射到 /app，校验路径与 COPY 一致。 |
| 失败关闭 | 完整实现。`scripts/release/overseas-deploy.py:31` 拒绝空后端清单；`:36` 缺失/不可读文件抛错；`:38` 哈希不符返回非零；`:40` check=True 传播失败，后续安装测试与成功凭据在 `:44` 至 `:47` 才执行。独立执行校验器的匹配、错字节、缺文件三路径，退出码分别为 0、1、1。 |
| 实际更新入口使用门禁 | 完整实现。`scripts/release/overseas-update-deploy.py:127` 至 `:128` 调用本次修改的 build；`:37`、`:68` 将 prepare/deploy 绑定安装通过的镜像 ID。`:26` 在 build 前调用源包哈希验证。不是只修复未使用的旧发布入口。 |
| PDF worker 可部署 | 完整实现。`Product-Spec.md:990` 的真实 PDF 阅读由 `hengxin-smart-image/frontend/vite.pdf-assets.ts:23` 的 .js 输出保持生产 MIME 兼容；`scripts/release/package-overseas.py:90`、`:96` 至 `:100` 同步匹配新名称并以原依赖 .mjs 校验字节。对照 `docs/reviews/PDF-WORKER-MIME-20261013.md:1`，三文件差异一致，既有真实构建产物/引用/826 项资产审计证据适用。 |
| UI、引导与 Spec 漂移 | 无新增页面、文案、样式、API、数据库或业务范围。本次仅改变资产输出及发布门禁；`Product-Spec.md:985` 至 `:991` 业务条目维持基线。完整实现/部分实现/未实现分类仅针对派发增量：增量完整，无部分或未实现条目。 |

## Stage 2：Code Quality

| 检查项 | 结论与证据 |
|---|---|
| 结构和错误处理 | PASS。`scripts/release/overseas-deploy.py:25` 至 `:48` 保持 build 单一阶段，使用既有 subprocess 模式，失败不被吞掉。修改后的四个 Python 文件分别 170、182、214、178 行，前端插件亦小于 300 行；无新增 any。 |
| 测试真实性 | PASS。`scripts/release/test_overseas_deploy.py:200` 至 `:214` 验证失败阻止安装日志与成功凭据生成，断言 --no-cache 和清单映射。该测试 mock 进程，不能单独证明哈希脚本正确；reviewer 补充从真实源码 AST 提取 verify 字符串执行，仅把 /app 映射到临时目录，实际验证一致/不一致/缺失。既有发布及更新故障注入共 48 项通过。 |
| 敏感输出与执行安全 | PASS。`scripts/release/overseas-deploy.py:33` 至 `:40` 以 stdin 传哈希清单，静态代码通过参数数组执行，不拼接 shell；容器不挂载宿主目录，不注入生产环境，network=none。输出只有文件数、状态或相对文件名；读取错误显示路径而非文件内容。成功和失败独立实验均未输出文件字节。 |
| PDF 字节限制 | PASS。`scripts/release/package-overseas.py:87` 至 `:102` 保留固定依赖版本、symlink 检查及原始/gzip 字节核对；`scripts/release/test_package_overseas.py:84` 至 `:110` 覆盖匹配、篡改、错误版本及泛化二进制拒绝。 |
| 视觉比较 | 本增量无新视觉设计，沿用基线及 PDF 增量报告。reviewer 本次未重新启动浏览器；主 Agent 另提供正式构建 Chrome PDF 1/3 渲染及 error[] 结果，该消息属于主 Agent 验证，不冒充 reviewer 独立观察。 |

## 编译与测试原始输出

reviewer 独立运行：

```text
uv run --project hengxin-smart-image/backend python -m pytest -q scripts/release/test_overseas_deploy.py scripts/release/overseas-update-tests.py scripts/release/test_package_overseas.py
................................................                         [100%]
48 passed in 0.44s
```

reviewer 独立校验器实验与 Python compile 输出（缺失文件的随机临时目录省略）：

```text
match exit=0 IMAGE_SOURCE_HASHES 1 PASS
mismatch exit=1 IMAGE_SOURCE_HASHES 1 ['sample.py']
missing exit=1 FileNotFoundError: [Errno 2] No such file or directory
COMPILE_PASS scripts/release/overseas-deploy.py lines=170
COMPILE_PASS scripts/release/package-overseas.py lines=182
COMPILE_PASS scripts/release/test_overseas_deploy.py lines=214
COMPILE_PASS scripts/release/test_package_overseas.py lines=178
```

前端编译沿用并读取 `output/requirements-build.log` 的原始尾部：

```text
dist/assets/index.vue_vue_type_style_index_0_lang-CL-ZpOFL.js                               814.14 kB │ gzip: 275.63 kB
dist/assets/index-Bsnj2vw7.js                                                               963.71 kB │ gzip: 307.80 kB
✓ built in 36.25s
```

服务器 Docker 全量安装测试、上线及部署后功能验收由主 Agent 继续执行。本次本机实验验证算法和失败传播，未声称本机真实 Docker 镜像运行已验证。
