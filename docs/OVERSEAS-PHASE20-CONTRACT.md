# Phase 20：海外资料合同与执行计划

本阶段接通真实资料，不启动 CLI、不伪造分析状态。复用一期有界 multipart、文件名清理、MinioStore、OwnedStreamResponse，以及已有海外身份、任务范围、幂等和事务锁；前端复用 OverseasCreate、ElUpload、MaterialPreview。

## 顺序与验收

1. 文件与解析：海外原件及解析版本独立落库、落桶；类型/20 MiB/空内容/损坏/资源上限失败明确。验收真实 PDF、DOCX、XLS、XLSX、CSV 及不支持内容，失败保留原件并可重试。
2. 任务绑定：所有权、有效解析、每类最多一份、至少一份、并发绑定/删除及权限撤销在后端控制。验收改派后旧设计拒绝、他人未绑定资料不可读取或关联、国内文件 ID 无法使用。
3. 前端：真实上传进度、失败/重试/移除、解析内容和原件操作；创建携带资料一次事务提交，既有 created 任务可补充资料。验收真实浏览器及错误态/窄屏。
4. 全套回归、迁移、独立两阶段审查；通过后中文本地提交，不部署或推送。

## 资料与状态

- requirement：PDF、DOCX；旧 DOC 明确拒绝并提示另存 DOCX/PDF（当前无可靠已有 DOC 解析器，不冒充解析成功）。competitor：XLS、XLSX、CSV。前端保留可理解的支持范围提示。
- 单文件上限 20 MiB；校验扩展名、签名/结构和非空。PDF 必须可抽取文字；加密、纯扫描、损坏、超资源限制明确失败；不提供 OCR。表格只读取值，不计算公式、执行宏或访问外链；无可读值不算成功。解析文本仅作不可信数据，通过文本插值展示。
- 有界解析在隔离子进程执行，超时/内存/输出量失败可重试。解析版本保留 parserVersion、状态、错误、文本及时间，原件不可覆盖。未绑定文件仅本人且仍有 task.create 权限可访问/重试/删除；绑定后按任务实时可读范围。绑定后不可重试/删除/替换，保留提交时的解析版本。
- 未引用资料删除采用数据库墓碑，读取立即拒绝；对象删除失败保留墓碑供再次删除重试，不能误删已引用对象。对象存储错误不返回密钥/内部路径。
- 不提供公开桶、直连签名 URL 或缩略图通道。原件经身份和任务授权流式读取，no-store/nosniff；PDF 可原件预览，其他格式下载使用本地应用打开。

## API（/api/overseas/v1）

- POST /materials?kind=requirement|competitor，multipart 单 file，浏览器写保护，返回 Material；上传完成后同步有界解析，解析失败也返回可重试的记录。
- GET /materials/{id} 返回 Material；POST /materials/{id}/retry 仅未绑定所有者，新增解析版本；DELETE /materials/{id} 仅未绑定所有者，成功204。
- GET /materials/{id}/content?download=true|false：原件流；无 download 时仅 PDF inline，其余 attachment。
- GET /tasks/{id}/materials：任务权限后返回 Material[]。
- POST /tasks 创建结构在 Phase19 基础上增加可选 materialIds（1–2个不重复UUID）。提供时须所有文件归当前运营所有、未绑定且解析成功、种类不同，和 task/event/outbox 一起原子落库，状态 submitted（图需已提交）。省略仍为 Phase19 created 元数据兼容，不得进入分析。
- POST /tasks/{id}/materials，Idempotency-Key，严格 {materialIds:[UUID],version:int}：仅创建者且仍有 task.create 或运营主管可为 created 任务补充；只可绑定当前操作者自己的文件；原子校验并变为 submitted，增加 task.materials_submitted 事件/事务 outbox。submitted 是资料已提交，尚不宣称排队/执行；Phase22 再接分析作业。
- 任务 DTO 对可补充的记录返回 task.materials.submit 能力；该值为记录级能力，不作为新的全局角色权限。
- Material：{id,kind,name,sizeBytes,contentType,status:'ready'|'failed',taskId:string|null,version:int,parserVersion:string,text:string,error:string|null,createdAt:string,versions:[{version,status,parserVersion,text,error,createdAt}]}。无 objectKey/bucket/其他成员信息。绑定后版本冻结。
- 变更锁顺序沿用成员权限锁→幂等→任务→按ID排序资料锁，避免角色变更/改派/绑定/删除竞态。读取沿用当前任务授权，不能信任上传者旧权限或客户端 taskId。

解析库官方用法已核查：pypdf PdfReader/extract_text、openpyxl load_workbook(read_only)、xlrd open_workbook。缺少现成文档解析能力时新增最小依赖，不复制文件存储、身份和任务基础设施。

参考：[pypdf文字提取](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)、[openpyxl只读模式](https://openpyxl.readthedocs.io/en/stable/optimized.html)、[xlrd读取接口](https://xlrd.readthedocs.io/en/stable/api.html)。DOCX仅通过defusedxml读取OOXML段落、表格及页眉脚注，不启动Office程序。

解析执行限制：15秒墙钟/12秒CPU、Linux512MiB地址空间、2MiB输出文本；ZIP解压50MiB/2048条目、PDF300页、表格50万个单元格，超过即失败，不截断后标成功。上传请求默认一期10MiB不变，海外调用显式20MiB。
