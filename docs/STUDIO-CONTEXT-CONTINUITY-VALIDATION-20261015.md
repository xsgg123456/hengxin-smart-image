# 工作台多轮文件连续性：实施验收

目标版本：0.2.36。当前状态：实现及已发现缺陷均已修复，最终快照独立两阶段审查通过；尚未生产切换或恢复业务文件。

## 实施范围

- 同一Studio会话持久使用自己的work；原件按内容版本只读挂载，研究文件可编辑并跨轮保留。
- 每轮input快照和Skill单独准备；未选Skill时隐藏旧版本。保持当前用户消息、CLI会话与业务记录。
- 按数据库已执行历史恢复旧目录；普通隐藏文件保留，冲突版本与来源索引可查；中断恢复和回退后的增量均需验证。
- 正式图片除最终引用与归属校验外，再比较本轮执行前字节基线；未变历史图不冒充新产物。
- 发布固定现有0.2.35/adf861b基线；备份排空后恢复明确清单中的旧会话，三次实际沙箱校验通过才切换并重新开放入口。

## 已取得的验证证据

| 验证 | 结果 | 原始证据 |
| --- | --- | --- |
| 前端测试与正式构建 | 364 passed；类型与构建通过 | output/context-frontend-tests.log、context-frontend-build.log |
| 修复初版后端Linux全量 | 2412 passed、189条件跳过；后续同名冲突修复需追加验证 | output/context-backend-linux-tests.log |
| 同名冲突修复后Linux全量 | 2432 passed、189条件跳过；编辑恢复版本的后续修复需追加验证 | output/context-backend-final-linux-tests.log |
| 编辑恢复版本修复后Linux全量 | 2446 passed、189条件跳过；最后提醒修复另有42项局部回归，最终安装包仍需全量验证 | output/context-release-candidate-linux-tests.log |
| 恢复/执行/交付/挂载完整相关Linux集 | 373 passed、1平台跳过 | output/context-final-targeted-linux-tests.log |
| 主流程、恢复CLI、挂载Windows集成 | 25 passed、1 symlink条件跳过 | 本轮工具输出 |
| 发布故障矩阵、打包与旧发布回归 | 最终157 passed、72 subtests passed | output/context-release-final-tests.log |
| Python编译 | app、tests、scripts/release compileall通过 | 本轮工具输出 |
| 生产依赖审计 | critical 0；既有high 36、moderate 34、low 1，本次未变依赖 | output/context-frontend-audit.json |
| 真实生产Linux环境隔离沙箱 | 3轮全部通过：7份原件→7份→追加同名后8份；派生笔记连续、原件不可写、其他会话不可见、本轮Skill独立；另旧目录同名原件及研究双版本恢复，4个源文件/2个冻结原件逐项覆盖、三次真实沙箱读取一致 | output/context-isolated-sandbox.json |
| 既有会话只读恢复预演 | 2份原件133,193,702字节，187普通文件121,807,029字节；无冲突，session保持 | output/context-precheck.json |

Linux全量中的条件跳过主要是需要专用数据库/身份/执行环境的测试；跳过不计通过。Windows不支持的链接/FIFO等边界由Linux测试补齐。沙箱测试使用独立临时目录、假原件字节及无网络Python进程，调用实际sandbox_command和Bubblewrap；没有调用真实模型或出图。

预演目标conversationId为`0b8feaa4-f302-4cc5-8cec-767004f0086d`，sessionId为`01a13d17-cb07-7db3-985e-8d196f45b6df`。预演只读，未创建persistent目录；冻结源摘要`34012644826e0bc318a6bf29ade7e85002a1c55e209befdd576e5d8b925c9adf`。实际应用时重新盘点，不直接复用旧摘要。

## 独立审查及发布

第一候选`c184666c74e1988a5639b54b1da203157bb9a247b58df30f9692f5ddd071b01e`发现回退增量与持久work未登记同名文件的冲突缺陷，未批准。修复后重新固定快照并从Stage 1审查，正式结果与生产证据将在完成后补入。

第二候选`6266e72745997d193b6b58c3ca840d437d81d99b1981658c501f0e9413f58781`的H1修复已通过源字节集合回归；复审另发现已公开恢复版本被正常修改后再增量迁移会被误当完整性错误，仍未批准。修复坚持保留用户编辑字节及可用旧源版本，并让索引只声明实际可读取内容。

第三候选`0dc3921eccfc4628d259d4b3d4895fbb8c1ee405aabc90972f42cfe349fe4d67`确认H1/H2闭环，但在线自动迁移后未实际dispatch的取消会丢失下一轮恢复提示（M1），未批准。现已统一维护和自动恢复提示，直到新dispatched历史出现才视为已送达；第四候选`2bf4ec347fb80829df115d2b1f6cac0739d0cf85ad86d61d356553f041dc9df2`送独立两阶段审查。

第四候选继续发现M1中断变体：增量迁移写索引或manifest失败后，重试的新增复制数为零，无法据此识别仍需提示。补两项失败复现后，改为以未提交迁移journal识别中断恢复；最终Windows相关57 passed，Linux相关83 passed、1平台跳过（output/context-notice-final-linux.log），compileall通过。第五候选`7b8d6f6ac459c8408f92e118e5f92cf0b2ae3083d625755c0c2ed7521a912df2`重新独立两阶段审查。

第五候选Stage 1/Stage 2均PASS，未发现HIGH/MEDIUM问题。独立验证相关109 passed、13平台条件跳过；发布99 passed、24 subtests；编译和diff检查通过。正式报告：docs/reviews/STUDIO-CONTEXT-CONTINUITY-SIGNOFF-20261015.md。批准只覆盖该源码快照，生产安装、切换及恢复验收需另记实际结果。

字体、Logo和本品清晰图的素材充足性不属于此次文件连续性修复。页面旧消息保留，不删除模型之前要求重新上传的历史回复。
