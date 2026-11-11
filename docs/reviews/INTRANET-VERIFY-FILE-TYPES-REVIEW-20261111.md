# 国内验收脚本文件类型增量审查

- candidateId：`a72f30a4bfa5a105b154caa4db986d1b155ada17ac048efa149d0eec3061c50c`
- 范围：仅 `hengxin-smart-image/infra/verify_codex_model.py:140` 新增的 MIME 类型筛选。依照 code-review skill 两阶段执行，不修改实现、不提交、不登记批准。
- 需求来源：`Product-Spec.md:5` 的内网复制授权及 `docs/INTRANET-UNIFIED-RELEASE-20261111.md:19` 的验收脚本补充；不重新审查全产品功能和已部署版本。
- 快照：审查开始及测试后 `review-status` 均返回上述 currentId，changedFiles 仅含该脚本。未发现审查期间代码变化；普通发布记录 Markdown 存在主 Agent 修改，不属于代码快照。

## Stage 1 — PASS

### 完整实现

|范围内要求|结论和证据|
|---|---|
|图片与标记文本同时交付时，只计图片|匹配。脚本第 140 行按 `content_type.startswith('image/')` 筛选。`backend/app/overseas/studio/delivery.py:107`、`:119` 返回经 validated 验证的所有链接文件；`backend/app/overseas/studio/output_files.py:34`、`:35` 分别返回图片和普通文件。真实 `output/unified-release-20261111/domestic-proof/reply.txt:1` 与 `:7` 同时链接修改图和标记文本。抽取生产 AST 的一图加文本、文本在前用例均接受。|
|恰好一张图片；收取警告仍拒绝|匹配。脚本第 141 行未改；两图、零图、纯文本、有警告用例均拒绝，warnings 对象保持原样。|
|实际查看、原生编辑、原始参考输入和 marker 验证保持|匹配。脚本第 95、137、138 行未改；现有 tools.json 只读取调用记录并检查关键词，四项均存在，未打印大体积工具输出。|
|保存被筛选出的真实图片|匹配。脚本第 142–144 行沿用筛选后的图片对象，测试核对返回对象身份；不会把前置文本字节写入 domestic-result.png。|
|只修验收，不改线上业务|匹配。git diff 与两次 review-status 仅发现脚本第 140 行代码增量；海外分支无变更。|

部分实现、未实现、Spec 漂移：范围内均无。UI 一致性及引导真实性：不适用，本次没有页面或文案变更（脚本第 140 行）。

## Stage 2 — PASS

- 代码质量：脚本共 150 行；第 140 行沿用现有 tuple 和变量，不增加依赖、异常吞噬或分支副作用。`output_files.py:17` 与 `backend/app/modules/files/validation.py:21` 均定义 content_type 为 str，筛选与生产类型契约一致。
- 测试真实性：直接抽取生产脚本第 140–141 行 AST 执行，输入模拟收集器返回的 tuple/带 content_type 对象，覆盖正常与拒绝路径并核对对象身份。不是完整 collector 集成或新收费模型调用；收集器实现另经代码核对。`backend/app/overseas/studio/files.py:35`、`:50` 将非图片及验证失败文件标为普通 MIME，符合负例前提。
- 安全扫描：逐字检查唯一新增代码（第 140 行），无密钥、命令执行、SQL、动态求值、新路径或日志输出；原收取警告拒绝条件保持（第 141 行）。未发现新增安全问题。
- 视觉对比：不适用，唯一代码增量是验收脚本过滤，未增加或修改 UI；不以此报告声称模型图片视觉效果合格。
- HIGH / MEDIUM / LOW 新增问题：均无。

### 编译及聚焦验证原始输出

通过 Python `compile(source, path, 'exec')` 检查整个脚本语法；通过 AST 运行新增过滤与紧随其后的断言。进程退出码 0，原始输出：

```text
COMPILE PASS: verify_codex_model.py
PASS: one image (accept)
PASS: image and txt (accept)
PASS: txt before image (accept)
PASS: two images and txt (reject)
PASS: only txt (reject)
PASS: empty (reject)
PASS: image with warning (reject)
PASS: invalid image demoted (reject)
RESULT: 8/8 focused cases passed; production AST lines 140-141 executed
Existing tool evidence: {'view_image': True, 'imagegen': True, 'referenced_image_paths': True, '/work/input.png': True}
```

### 验收边界

结论仅授权该 candidate 的脚本修正进入主 Agent 的 review-approve 流程。读取时 `output/unified-release-20261111/model-recheck.log` 尚无输出，因此不将正在运行的真实复验计为成功，也不以主 Agent 提供的源码、前端、账号及容器保持声明代替独立发布验收。真实复验结果由主 Agent 在发布记录中追加。
