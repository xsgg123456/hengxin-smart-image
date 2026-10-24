# 工作台开放输出：干净副本发布映射审查

日期：2026-10-24。审查方式：code-review，两阶段限定为已批准代码到发布副本的映射及打包前检查。仅新增本报告，未修改代码、提交、部署或重新运行全套测试。

## 结论与候选

- **Stage 1：PASS；Stage 2：PASS。可批准本候选进入打包，无本范围阻断。**
- 本候选：`f5c4964aff77d5ee39c16d7a17b02cf331e9521f738f9ba8e6101c4d80e138b7`。
- 原已批准候选：`16c34af9249fb8d4c8a6049d0009d62cad34427bf9ca1231d9adff97597540a1`。
- 主树和副本 HEAD 均为 `b6289ebfa9d69bd0b27c003bb0d978a48a135c5a`。
- 原报告：`docs/STUDIO-OUTPUT-FINAL-REVIEW-20261024.md:5-11`。文件 SHA-256 为 `e43895fb12da0f5dc5b3266d18836ecf5f9e1ad872187d4940a819e0dd97bc63`，与主树批准凭据一致；凭据的两阶段均为 PASS。
- 此结论不代表最终压缩包已验证或生产交付已完成。主 Agent 登记本候选批准后，仍须实际运行打包器，保存 package-audit、release.json 和压缩包哈希，再执行已计划的 Linux 安装包测试、隔离 PostgreSQL、生产发布门禁。

## Stage 1：代码与合同映射

| 核验项 | 结论与证据 |
| --- | --- |
| 受审实现、测试及发布脚本未漂移 | PASS。读取主树 `.codex/review-state.json` 的 approved.snapshot 与副本 candidate：各 1963 项，差异仅 `AGENTS.md`；其余 1962 项完全相同。主树 review-status 仍匹配原批准候选。快照按 `.codex/hooks/review_files.py:36-45` 仅规范换行，未忽略其他空白。 |
| 用户既有修改不进入发布 | PASS。主树 `git status --short` 仅 ` M AGENTS.md`，副本受跟踪文件 clean；两边 HEAD 一致。因此副本含提交版本 AGENTS，未带入用户未提交内容。`scripts/release/package-overseas.py:91-109` 对 AGENTS 不选择，本次实际 `selected('AGENTS.md')` 返回 None。符合实施合同 `docs/STUDIO-OUTPUT-IMPLEMENTATION-20261024.md:44`。 |
| 合同全部条目与 UI 结论映射 | PASS。实施合同 `:11-16` 的六项要求、`:22-28` 的七种用户场景和 `:40-45` 的六步验收，由原报告 `:16-44` 逐项核验。本次全部对应源代码、测试与发布模块哈希不变；原 Stage 2 与视觉结论见原报告 `:46-64`，因此沿用这些已有结论，不冒称本次重新做浏览器验证。无新增页面、功能或合同漂移。 |
| 生产版本及迁移 | PASS。`scripts/release/package-studio-output.py:11-29` 指定前端 0.2.52、海外 overseas_0022，并强制包含迁移、transport、保存与测试模块；本次实际校验 173 项 REQUIRED 无缺失，国内为 0032。 |
| 正式生产 dist 来源 | PASS。主树 frontend/dist 与副本 frontend/dist 全部 640 个文件逐字节 SHA-256 比对，差异 0；主树 dist-overseas 为 624 文件，与副本有 837 项键/哈希差异，确认副本未使用该目录。构建日志 `output/studio-output-production-build.log:3-8` 为正式 build；`scripts/release/package-overseas.py:155-165` 同时拒绝预览入口并核实 index 引用。 |

没有部分实现或未实现的本次映射项。完整产品功能审查依据原报告，不扩大本次审查范围。

## Stage 2：打包完整性、隐私与快照

| 核验项 | 结论与证据 |
| --- | --- |
| 允许清单和资产完整性 | PASS。本次在副本导入实际 package-studio-output.py，遍历 git ls-files，经 selected、no_symlink、privacy_check、collect_assets、validate：707 个源文件、636 个发布资产，173 项必需文件全部存在。640 个 dist 文件中的 4 个 demo-images 按 `package-overseas.py:124-125` 排除。 |
| PDF.js 参考资产 | PASS。`package-overseas.py:136-150` 对资源与 worker 使用固定 6.4.299 版本和逐字节参考校验；本次 collect_assets 完整通过。副本 node_modules/pdfjs-dist 是实际目录，参考文件仅用于校验，不作为源目录进入包。 |
| 私有事故原件排除 | PASS。tracked 中无 output/、rollout.jsonl 或 incident.json 原件；实际 `selected('output/private/studio-incident.json.gz')` 为 None。`.gitignore:19` 排除 output；`backend/tests/test_studio_open_outputs.py:87-91` 从 STUDIO_INCIDENT_FIXTURE 外部路径读取原始记录，不内嵌客户数据。打包器仅遍历 tracked 允许文件与正式 dist，见 `package-overseas.py:185-203`。 |
| 隐私扫描 | PASS。本次所有 707 个被选源文件及 636 个资产执行原始扫描器。仅 `backend/tests/test_public_messages.py` 两处既有合成负例被精确豁免，没有其他豁免。规则见 `package-delivery.py:24-34,54-67` 与 `package-management.py:65-83`。这是该扫描器的通过结果，不声称对所有可能隐私形式作形式化证明。 |
| 批准与归档防漂移 | PASS（实现与打包前检查）。`package-delivery.py:70-76` 要求当前批准；`package-overseas.py:180-212` 要求已提交、工作树一致、前后 HEAD/candidate 不变，写入每文件哈希；`:168-177,213-225` 校验内存及落盘归档成员、普通文件属性、字节哈希并写 package-audit。实际最终压缩包尚未生成，不能用此报告替代实际 audit。 |
| 本轮代码质量/安全变化 | 无新增实现。1962 项非 AGENTS 受控内容与已通过质量/安全审查的快照相同；原结论见原报告 `:48-64`。本 reviewer 未执行修复、未写 clean、未登记批准。 |

## 原始核验输出

```text
# 主树
b6289ebfa9d69bd0b27c003bb0d978a48a135c5a
 M AGENTS.md
{"currentId": "16c34af9249fb8d4c8a6049d0009d62cad34427bf9ca1231d9adff97597540a1", "reviewedId": "16c34af9249fb8d4c8a6049d0009d62cad34427bf9ca1231d9adff97597540a1", "changedFiles": [], "approved": true}
# 副本（写报告前 status 无输出）
b6289ebfa9d69bd0b27c003bb0d978a48a135c5a
{"currentId": "f5c4964aff77d5ee39c16d7a17b02cf331e9521f738f9ba8e6101c4d80e138b7", "reviewedId": null, "changedFiles": [], "approved": false}
snapshot file counts 1963 1963
differences ['AGENTS.md']
hengxin-smart-image/frontend/dist files 640 clone 640 differing 0
hengxin-smart-image/frontend/dist-overseas files 624 clone 640 differing 837
report sha matches True
{"sourceCount": 707, "assetCount": 636, "requiredCount": 173, "missingRequired": [], "privacy": "PASS", "syntheticExceptions": {"backend/tests/test_public_messages.py": ["existing synthetic negative fixture", "existing synthetic negative fixture"]}, "version": "0.2.52", "domesticMigration": "0032", "overseasMigration": "overseas_0022", "agentsSelected": null, "privateOutputSelected": null, "privateTrackedMatches": []}
frontend/dist/index.html d70ad9050d1481c85a6219ededd88ce71e14ba6950bed0d184c7a3a7649fd775
backend/tests/test_studio_open_outputs.py 3647fe4ec253124976a074cded16b0cffdeb4221c3646e684a5f51a494676bf9
scripts/release/studio-output-deploy.py 4b0391bfdfdb0e320eb75324592d16d7447e0e72effa97570f95b24010c3061d
validation PASS; archive build/hash still requires main approval and packaging
```

编译复用主树构建日志原始输出；本次未重跑构建：

```text
> hengxin-smart-image-frontend@0.2.52 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
dist/assets/index-7p9zuagU.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 30.53s
```

原代码测试证据继续引用原报告 `:69-118`（后端 885 passed / 43 skipped、真实事故及关键专项 50 passed、前端 396 passed、发布 31 passed、类型检查通过），不标记为本 reviewer 重跑。主 Agent 应对本报告 candidate 执行 review-status 和 review-approve，再打包；若代码或 dist 再变更，复核差异及相关资产哈希。
