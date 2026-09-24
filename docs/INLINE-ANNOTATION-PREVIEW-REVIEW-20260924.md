# 单张直接标注预览审查

审查日期：2026-09-24；使用 code-review skill，独立两阶段审查。

最终 candidateId：`f4fff578d5c2895aa8e03e98f35d3a0bee8d6709d67bd9382b17f505402a0232`。

范围：`hengxin-smart-image/previews/inline-annotation/{index.html,style.css,app.js,assets/*}`；依据 Product-Spec.md:3、DEV-PLAN.md:3、Design-Brief.md:3、docs/INLINE-ANNOTATION-PREVIEW-20260924.md:3。只审本地预览，不代表正式业务、真实生成或部署验收。

## 最终结论

Stage 1：PASS。Stage 2：PASS（本地交互预览范围）。无未关闭 HIGH/MEDIUM；有 1 项 LOW 可维护性建议。不得把本报告用于批准生产实现。

## 快照变化与缺陷闭环

初始 candidate `010ae693d54ca57ec92ae49d8e180a571acfe573c51ee47efbf2959b49c44fa9` 发现两项 MEDIUM，不予通过：

1. 原 app.js:10/46/92：画框→输入旧意见→移动框→输入新意见→撤销，意见被还原为旧意见。独立浏览器原始输出 `撤销移动后意见=旧意见`。新 app.js:11–14 按框 id 保留当前意见，:89/:96 使用该恢复函数。复核移动撤销保留新意见，删除/清空撤销恢复意见，通过。
2. 原 app.js:32：上传模式仍提示拖动画框，而实际禁止框选。新 app.js:36 对非直接模式隐藏提示，浏览器断言通过。

审查中主 Agent 同步更正范围文档预览目录。上述代码修复后重新固定最终 candidate，重跑核心检查和针对回归；最终结论只适用新 candidate。

## Stage 1 · 逐条核对

| 需求条目 | 结论及证据 |
| --- | --- |
| 蓝色主按钮、白色圆角、版本提示、大图/右侧意见、窄屏上下 | 完整实现。index.html:7、style.css:1；实际 desktop.png 为1440×900，mobile.png 为390×844，左右/上下布局及无横向溢出通过。 |
| API/CLI切换、会话草稿隔离、关闭重开 | 完整实现。app.js:3、102、120；CLI两框切API空草稿后返回保留，关闭重开保留。 |
| 多矩形、编号、移动、右下调整大小 | 完整实现。app.js:19、66、78；真实pointer拖动、数量及尺寸断言通过。 |
| 图片坐标保存、缩放、平移、适应 | 完整实现。app.js:16、63、80、95；缩放/平移后框坐标深比较相等，viewBox实际改变。 |
| 撤销、删除、清空、每框意见及整体补充 | 完整实现。app.js:11、49、96–99；原缺陷已修复，几何撤销保留当前意见，删除/清空恢复对应意见。 |
| 直接标注与上传互斥 | 完整实现。app.js:36、57、71、130、133；切模式不将直接框混入上传参考，上传模式空草稿提示已隐藏。 |
| JPG/PNG/WebP、10MiB、单张、拖拽/聚焦粘贴 | 完整实现。app.js:107–118；选择文件、坏图、超限、错误MIME及DOM drop/paste处理测试通过。原生OS剪贴板未实测。 |
| 合成一张编号图、意见汇总、模拟提交 | 完整实现。app.js:123、132–139、144；实际生成图片decode、确认弹框、模拟成功通过。 |
| 基础图片不覆盖、本地隔离、不承诺框外像素锁定 | 完整实现。app.js:132创建独立canvas，index.html:5、28明示演示及限制；app.js:144仅写模拟状态。网络监测仅本地资源/blob。 |
| 浏览器验证与预览边界 | 完整实现。output/annotation-preview-20260924/check.mjs:5–31覆盖实际交互；未修改正式业务、未部署，静态页面仅供评审。 |

无未实现项。首版不保留跨浏览器会话草稿，属于范围文档:8明确限制；不将真实原图/素材附带、模型生成或历史版本业务列为本轮已验证能力。

## Stage 2 · 质量、安全、视觉

- 安全 PASS：app.js:15、26、49、139使用textContent/value，无eval、innerHTML、硬编码密钥、生产URL或fetch/XHR；:111、113、119、129管理blob URL。上传及模拟提交实际网络监测无外部业务请求。
- 错误处理 PASS：app.js:108–114校验单张、MIME/尺寸并decode，失败释放URL，finally恢复提交；:140处理合成错误。坏图、超10MiB、错误类型实测通过。
- 结构 PASS：app.js共145行，状态、绘制、上传、合成以函数分开；无TypeScript any。LOW：style.css:1整份单行，可读性差，正式承接时宜格式化，当前预览不阻断。
- 测试真实性 PASS：check.mjs:6–18用实际pointer拖动覆盖画框/移动/resize/pan/delete/clear，检查坐标而非仅内部函数结果；补测移动后再次编辑意见弥补原盲区。drop/paste是DOM事件注入，不冒充原生系统端到端验证；新增真实后端不在范围。
- 视觉 PASS（截图比对）：实际打开本轮desktop.png、mobile.png和邻居output/ui-preview-20260923/api-annotation.png，蓝色操作、白色弹框、图文对照、取消/提交位置保持既有方向；新页面当前浏览器渲染经过重跑验证。邻居使用既有真实渲染截图，未重新启动业务页面，不宣称同会话在线邻居交互回归。
- Spec漂移：未见新增业务API/表/生产功能；index.html:5及app.js:144明确模拟，新增范围限于授权预览。

## 原始验证输出

`node --check hengxin-smart-image/previews/inline-annotation/app.js`：退出码0，无输出。静态预览无业务编译阶段，本次未运行全项目构建。

`node output/annotation-preview-20260924/check.mjs`：退出码0（新快照已重跑）：

```text
PASS: drawing, notes, coordinate stability, move, undo, composite, mock submit, draft, channel isolation, upload, validation, mobile overflow; page errors=0
```

独立边界测试退出码0（上传逻辑在两快照间未变化）：

```text
PASS: corrupt image, >10MiB, invalid MIME, DOM drop/paste handlers, mock submit; network local-only
```

新快照针对回归退出码0：

```text
PASS: M1 geometry undo retains latest note, delete/clear undo restores note; M2 upload hint hidden
```

最终review-status确认currentId为`f4fff578d5c2895aa8e03e98f35d3a0bee8d6709d67bd9382b17f505402a0232`；approved:false表示尚待主Agent按协议登记。主Agent可对同一快照review-approve，不写clean；任何后续代码变更需重新复核。
