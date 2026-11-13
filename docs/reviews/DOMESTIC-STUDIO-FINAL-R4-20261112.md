# 国内 AI 工作台及联合发布独立审查 R4 · 2026-11-12

## 结论、快照和范围

- **candidateId：`75467c5539fd380bf6539b9aea6c8be872f2772379a9acf84b8f173399053a37`；Stage 1：FAIL；Stage 2：未执行。** Stage 1 有一个经真实隔离 MinIO 实测的 HIGH，不能登记此候选的两阶段 PASS。其余条目中的静态代码存在不代表已完成验收。
- 范围：`Product-Spec.md:1-13` 的五个国内工作台、私人会话与附件、恢复、Skill 管理、归档及国内外隔离；`DEV-PLAN.md:1-26` 的发布、0032→0043 迁移和故障恢复；`Design-Brief.md:1-3` 与 `hengxin-smart-image/frontend/preview-domestic-studio/` 确认预览。此前三轮报告 `docs/reviews/DOMESTIC-STUDIO-FINAL-20261112.md`、`DOMESTIC-STUDIO-FINAL-R2-20261112.md`、`DOMESTIC-STUDIO-FINAL-R3-20261112.md` 均已阅读，不能把旧候选结论移作本候选的通过凭据。
- 开始时 `review-status` 显示 `currentId` 为上述 candidateId，`approved` 为 `false`。本轮只读业务代码，独立探针和 Markdown 报告不属于受控代码快照；未写 clean、未调用 review-approve、未提交、未访问生产或实际模型。
- 高优先级问题发现后停止完整审查；下面准确区分已验证、静态部分核查与未验证。主 Agent 的其他测试结果不视为本 reviewer 独立验证。

## Stage 1 · HIGH

### H1：图片附件与成品原图预览或下载仍整文件读取，合法大图需要两份文件规模的 Python 堆

**需求**：`Product-Spec.md:6,8` 要求保留工作台附件能力，以及“大附件以有界方式处理，避免按附件上限重复占用内存”。`DEV-PLAN.md:22,26` 又要求大文件路径避免按 500 MB 附件规模重复占用内存，并检查取回和下载调用链。

**真实可达调用链**：

1. 允许的国内附件上限为 500,000,000 字节（`hengxin-smart-image/backend/app/overseas/upload_limits.py:2`；上传入口 `backend/app/modules/domestic_studio/router.py:144-155`，流式校验 `backend/app/modules/domestic_studio/file_service.py:29-40`）。有效 PNG 可被 `backend/app/overseas/studio/files.py:42-71` 判定为 `image/png`。
2. 用户在国内工作台的待发送附件或素材列表中点击图片查看原图：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:20,26` 使用 `StudioAttachments`/`StudioMaterials`；前者在 `frontend/src/views/shared/studio/StudioAttachments.vue:3-4` 渲染 `StudioAssetImage`，后者在 `frontend/src/views/shared/studio/StudioMaterials.vue:8-9` 也使用该组件。`StudioAssetImage.vue:2,24` 打开 `use-image-viewer.ts:17-23,30-37`，后者通过 `studio-images.ts:7` 和 `image-cache.ts:61-73` 请求原图 URL。图片的“下载原图”按钮在 `StudioAssetImage.vue:4,8,39-43`，通过 `frontend/src/api/shared/attachment-download.ts:4-24` 先发 HEAD，再用原 URL 发下载 GET。
3. 国内源附件、输出图的内容端点在 `backend/app/modules/domestic_studio/router.py:160-175`，归档副本端点在 `backend/app/modules/domestic_studio/archive_router.py:59-67`。二者将记录交给 `backend/app/overseas/attachment_delivery.py:8-11`；图片 MIME 无论是预览还是下载都进入 `backend/app/overseas/image_delivery.py:38-66`。该路径的 `original_bytes` 在 `image_delivery.py:10-19` 对对象流执行 `stream.read(500000001)`、计算完整文件摘要并返回整个 `bytes`，随后 `image_delivery.py:64-66` 将整份结果构造为响应。它不是按固定小块消费并输出的路径。由 `app/overseas/image_delivery.py:7` 可知 JPEG、PNG、WebP 都进入此分支；本轮仅对 PNG 做内存实测。
4. **缩略图边界**：`image_delivery.py:49-52` 对 `thumbnail=true` 调用 `backend/app/overseas/thumbnails.py:43-45`，后者对超过 32 MiB 的图直接返回 413；这是缩略图限制，不覆盖点击“查看原图”或“下载原文件”的后续原图 GET。页面的失败提示和原图入口见 `StudioAssetImage.vue:2-4`。HEAD 原图请求可在 `image_delivery.py:61-63` 返回而不读取原图，但随后的 GET 会走上述整读。

**独立实测**：脚本在隔离 MinIO `127.0.0.1:35441` 新建随机 bucket，创建 4096×4096 随机像素的普通 RGB PNG，使用真实 `validate_stream` 验证、真实 MinIO SDK 和真实 `MinioStore.open`，直接调用生产的 `image_delivery.deliver`。记录是隔离测试用 `SimpleNamespace`；未执行 HTTP 身份认证或浏览器页面，UI 可达性由上述源码链路核对。`tracemalloc` 在图片生成、上传和校验之后启动，因此下列峰值仅覆盖原图分发调用。脚本最后删除自身对象及 bucket。原始输出（省略 WSL 启动提示）：

```text
validator= ('img.png', 'image/png')
actual_minio image_bytes=50351853 response_bytes=50351853 peak_bytes=100971777 status=200
```

Python 堆峰值约为文件长度的 2.01 倍。另一个有效 PNG（1×1 PNG 尾随零字节至 64 MiB）同样经 `validate_stream` 接受，真实 MinIO 实测 `actual_minio image_mib=64.00 response_mib=64.00 peak_mib=128.26 status=200`。第二个样本说明应用目前接受该字节形式；第一个样本不依靠尾随数据。两次均不是浏览器端到端、完整进程 RSS、并发或实际 500 MB 测量，也未观察到 OOM；不能把约两倍堆峰值直接当作线上必然 OOM。

**复现材料**：本机临时脚本 `C:/Users/82358/AppData/Local/Temp/review_domestic_r4_image_memory_natural.py`；在 `hengxin-smart-image/backend` 目录用 WSL 隔离虚拟环境、`PYTHONPATH=.` 运行。为避免依赖临时文件，等价脚本如下；只允许指向主 Agent 指定的隔离测试 MinIO，账号通过环境变量提供：

```python
import os, tempfile, tracemalloc
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4
from PIL import Image
from minio import Minio
from app.storage.minio_store import MinioStore
from app.overseas import image_delivery
from app.overseas.studio.files import validate_stream

client = Minio('127.0.0.1:35441', access_key=os.environ['TEST_MINIO_ACCESS'],
               secret_key=os.environ['TEST_MINIO_SECRET'], secure=False, region='us-east-1')
bucket = 'review-r4-' + uuid4().hex[:20]
client.make_bucket(bucket)
try:
    store = object.__new__(MinioStore)
    store.client = client
    with tempfile.TemporaryFile() as stream:
        image = Image.frombytes('RGB', (4096, 4096), os.urandom(4096 * 4096 * 3))
        image.save(stream, format='PNG', compress_level=0)
        image.close()
        size = stream.tell()
        stream.seek(0)
        print('validator=', validate_stream(stream, size, 'img.png'))
        stream.seek(0)
        digest = sha256()
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
        stream.seek(0)
        client.put_object(bucket, 'img.png', stream, size, content_type='image/png')
    row = SimpleNamespace(bucket=bucket, object_key='img.png', size_bytes=size,
                          checksum=digest.hexdigest(), content_type='image/png', name='img.png')
    tracemalloc.start()
    try:
        response = image_delivery.deliver(store, row, preview=True)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    print(f'actual_minio image_bytes={size} response_bytes={len(response.body)} '
          f'peak_bytes={peak} status={response.status_code}')
finally:
    client.remove_object(bucket, 'img.png')
    client.remove_bucket(bucket)
```

该探针没有修改正式文件、数据库或运行服务。非图片原件路径使用 `attachment_delivery.py:12-28` 的 `OwnedStreamResponse`，本次发现不能不加验证地外推到非图片。归档 ZIP 下载已换为 `archive_router.py:70-98` 分块拷贝，不能以 ZIP 的测试结果代替归档图片单张原图分支；反之本次原图探针也不声称 ZIP 存在同一问题。修复时需保留原图完整性检查、身份授权、图片类型及原有海外行为，再对可达 GET/下载路径做真实服务回归。

## Stage 1 · 逐条状态与未验证边界

以下路径中 `backend/` 和 `frontend/` 均相对于 `hengxin-smart-image/`。除 H1 的调用链和探针外，下列“部分”表示代码位置已核对，**不是完整通过**。

| 要求 | 本轮状态及证据 |
| --- | --- |
| 五入口、分组、成品库一级与 Skills 管理角色 | 部分：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/router/modules/index.ts:12-29`。五入口登录、实际跳转及全部角色未逐项实测。 |
| 默认留白、无预填和自动发送、教程 | 部分：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-22,29`；未逐入口渲染或全面检查死引导。 |
| 会话独立、新建切换重命名删除与创建人权限 | 部分：`backend/app/modules/domestic_studio/conversation_service.py:29-47,70-106`、`conversation_deletion.py:14-54`；未独立完成跨用户及并发 HTTP 矩阵。 |
| 真实姓名、北京时间和消息左右排列 | 部分：`backend/app/modules/domestic_studio/queries.py:68-105`、`frontend/src/views/hengxin/domestic-studio/library.vue:11`；未以实际登录用户逐入口验证。 |
| 输入、附件、连续对话、结果、修改、停止和异常 | **不通过：H1**；`DomesticWorkspace.vue:15-23` 与 `backend/app/modules/domestic_studio/turn_service.py:40-116` 提供入口，完整交互、模型和故障流程未独立验收。 |
| 成功执行后的部分收取和手动取回；不确定进程不重生 | 部分：`backend/app/modules/domestic_studio/recovery.py:38-76`、`recovery_stream.py:9-28`、`recovery_files.py:113-187`；未独立重放全部进程、磁盘损坏、源文件并发变化及网络故障。 |
| 上传、输出、归档写入迟到时的凭据、删除保护及重试 | 部分：`file_service.py:43-72`、`output_intents.py:13-32,35-62`、`archive_service.py:203-225`、`conversation_cleanup.py:81-99`。本轮未独立复跑前两轮的真实 MinIO 迟到写和分片中断测试，不能声称前两轮缺陷在此候选全覆盖通过。 |
| 大附件工作区及手动恢复 | 部分：`backend/app/execution/bounded_read.py:20-35`、`backend/app/overseas/studio/context_assets.py:91-113`、`recovery_stream.py:9-28`；本轮没有重复 500 MB 和跨进程并发探针。图片原件读取不通过 H1。 |
| 仅新品可归档、替换端服务端拒绝 | 部分：`backend/app/modules/domestic_studio/policy.py:27-30`、`archive_service.py:101-103`、`DomesticWorkspace.vue:14,64`；本轮未独立发绕过请求。 |
| 按产品名归档，国内成员共享副本和对话、源会话私有 | 部分：`archive_service.py:101-176`、`archive_router.py:36-44`、`conversation_cleanup.py:44-57`、`file_service.py:75-81`；未完成所有角色、源删除后跨用户读取/下载实测。 |
| 成品库搜索、来源、详情、删除、ZIP、图片保护 | 部分：`backend/app/modules/domestic_studio/archive_queries.py:26-93`、`archive_router.py:47-98`、`frontend/src/views/hengxin/domestic-studio/library.vue:4-11`；单张原图分发存在 H1；未独立验收 ZIP 内容与全部角色。 |
| 超管 Skill 文件夹、校验、更新、启停、删除、ZIP、无版本管理 | 部分：`backend/app/modules/domestic_studio/management_router.py:82-147`；未逐项操作及盘点是否存在额外 UI。 |
| 五入口初始空绑定、未配置/停用禁发、冻结和绑定保护 | 部分：`backend/migrations/versions/0033_domestic_studio_bindings.py:5-26`、`backend/app/modules/domestic_studio/bindings.py:37-82`、`policy.py:33-51`；未独立执行整个并发/防绕过矩阵。 |
| 国内外身份、数据库、对象、队列隔离与历史海外能力 | 部分：`backend/app/modules/domestic_studio/recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`；未独立完成跨业务端到端、对象隔离和全部海外回归。共享原图函数受到 H1 影响，不能断言海外大图分发已验证。 |
| 安装权限、UID/GID、socket、联合迁移和恢复 | 部分：`scripts/release/intranet/joint_studio_verify.py:68-85`、`joint_studio_fence.py:25-60`、`joint_studio_release.py:160-198`、`backend/migrations/env.py:39-47`；未独立重跑迁移父子进程/DB 锁、旧台账重入、真实 Docker 身份、正常前向恢复及工具安装。旧版 R1 发现未自动覆盖新候选。 |
| 预览同视口视觉、未授权功能漂移 | 未完成：设计基准 `Design-Brief.md:1-3` 与 `frontend/preview-domestic-studio/`；本轮未进行实际同视口对照或完整页面/API/表盘点。 |
| 构建、完整测试、中文提交、正式部署和入口验收 | **不通过**：本候选 Stage 1 有 HIGH；本 reviewer 仅执行下列有限检查，未完整构建、提交、部署或验收生产。 |

## 本 reviewer 独立测试及编译原始输出

使用 WSL 中 `/tmp/hengxin-domestic-studio-python/bin/python`，在 backend 设置 `PYTHONPATH=.:tests` 执行 `pytest -q tests/test_domestic_delivery_capture.py tests/test_bounded_output_read.py --disable-warnings`，退出码 0；原始汇总（省略 WSL 启动提示）：

```text
........                                                                 [100%]
8 passed, 1 warning in 8.28s
```

这些测试针对快照捕获和有界读取，未覆盖本报告 H1 的真实 MinIO 图片原图分发，不能证明 H1 通过。

对国内工作台模块、发布工具和共享图片分发文件执行 Python 内存 `compile`，未写入字节码，退出码 0；原始输出：

```text
COMPILE_OK files= 105
```

这是 105 个 Python 文件的语法检查，不是前后端完整构建。没有独立复跑完整后端、前端或发布工具套件，也未在真实 Docker 身份或生产环境运行部署。

## Stage 2

**未执行。** Stage 1 存在 HIGH，未系统完成代码质量、安全扫描、测试真实性全面审查、正式页与预览及邻居基准页面的同视口视觉对比，也未独立验证安装与联合发布链。修复并重新固定 candidateId 后从 Stage 1 重审；旧报告不得覆盖新快照。

报告写成后再次执行 `review-status`，原始输出：

```json
{"currentId":"75467c5539fd380bf6539b9aea6c8be872f2772379a9acf84b8f173399053a37","reviewedId":"d3a967332ae14940e06e774849782af11917f8c7bc2e0902deee6d698edc3ce1","approved":false}
```

审查期间受控代码快照未变；该状态不是通过凭据。
