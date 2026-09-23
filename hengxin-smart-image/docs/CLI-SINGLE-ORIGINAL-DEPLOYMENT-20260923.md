# 壁纸单张修改原图对照发布

## 范围

壁纸单张修改自动读取任务冻结模板对应槽位的原图到 `/work/original/`，选定成品仍为唯一修改基础；素材和可选标注保留。新增明确图片职责、局部对照和仅交付1张的提示词，原图目录不能直接收作成品。商品/文字、首轮和整套逻辑保留。沿用原会话，不挂载首轮Skill。用户自行验证真实出图效果。

## 验证

- Windows完整后端：`python -m pytest -q`，932 passed、168 skipped（平台/外部集成条件），59.89秒。
- 独立两阶段审查PASS，候选 `46a02346bc9ffc8bb7427a495ffa13f4bb734325c4f0169fb20ddae74e2afa45`；独立专项102 passed、1 skipped，六文件compileall通过。
- 服务器实际发布包在已有生产镜像中无网络隔离测试：168 passed，28.03秒，覆盖材料、提示词、收图、runner、返工、沙箱、恢复、续跑及输入冻结。临时容器已自动移除。第一次调用系统Python缺pytest，后改用镜像内既有 `/app/.venv/bin/python`，没有安装或改动生产依赖。
- 发布包242个代码/测试白名单文件，247885字节，SHA256 `1004b99a737b6becf6ee1cda253aa98d0481524031ceca49337113eaf0ca5708`。无运行数据、数据库、凭据；实际仅部署3个应用文件。

## 生产切换

2026-09-23 18:19北京时间，停止接纳并确认Worker及数据库无在途任务后，备份并原子替换 `app/execution/materials.py`、`prompts.py`、`final_delivery.py`，重启专用Worker。新PID1294761，心跳ready，CLI0.156.1，并发5，超时7200，队列celery恢复，ping成功，三文件哈希与发布包一致。API容器、前端、Skill发布树和业务数据未修改。

使用既有“111111”任务的第2张历史单张修改轮次，在临时目录调用已安装材料/提示词代码：得到 `current/00.png`（冻结V1）、`original/00.jpg`（对应原底图）、`inputs/00.png`（屏幕素材）、`annotation/reference.png`，未加载Skill，提示词611字符。生产事务只读，临时文件自动清理，没有创建轮次或调用生图模型。

发布目录 `/opt/hengxin-releases/cli-single-original-20260923`，含artifact-tests.log、deployed.json、verified.json及哈希清单。备份 `/opt/hengxin-backups/cli-single-original-20260923`。回退须同样取消消费并证明空闲后恢复三个备份文件、重启和核验消费/心跳；不得强停在途任务。

新提交的壁纸单张修改即可测试。代码验证不代表生成质量已验证，真实细节改善由用户用相同基础版本及意见对照测试。
