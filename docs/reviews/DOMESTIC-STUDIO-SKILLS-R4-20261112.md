# 国内 Skills 管理独立复审 R4 · 2026-11-12

- 送审 candidateId：5d8547496f3fd051c5d9ea5a44078b9dc0b0f10fe1dbc575bba84b9f41371d43。
- 审查范围：国内 Skills 管理及 R3 首次安装恢复修复，包括空目录和已安装目录异常退出恢复、未知文件与链接保护、数据保留、锁顺序、权限、CAS、ZIP、绑定列、引用及物理回收、共享海外行为。基准为 Product-Spec.md:3-11、Design-Brief.md:1-3、DEV-PLAN.md:1-10、docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:1-24、frontend/preview-domestic-studio/Skills.vue 及 R3 报告。
- **Stage 1：FAIL（两项 HIGH）；Stage 2：未执行。** 本轮发现阻断后按主 Agent 指示提前结束，不能据此登记两阶段 PASS。
- 快照：开始与发现问题后执行 review-status，currentId 均为送审 candidateId，approved 为 false。本 reviewer 仅新增本报告，未修改产品代码。报告撰写完成后如代码继续变化，必须重新固定快照并重新审查。

## Stage 1 阻断问题

### HIGH 1：恢复将未知普通文件当发布器暂存物删除

已安装目录：backend/app/overseas/management/skill_staging.py:8-24 仅凭 releases 或 packages 下匹配 .install- 加八个字符的名字收集目录；:27-42 只验证当前目录索引和树是否安全，然后删除整个目录。树中没有任何凭证证明内容属于该次发布器写入；目录里无法识别的普通文件也会随之被物理删除。实际服务在启动、定时恢复以及多种传输请求时执行恢复（backend/app/overseas/management/skill_publisher.py:24-45,75-107），共享恢复器发现目录后自动调用清理（backend/app/overseas/management/skill_publication.py:47-60）。这违反本轮未知数据不丢失的审查边界，也可能影响共享海外发布器；未证明普通用户上传能够自行创建这一受保护目录。

首次空目录：backend/app/overseas/management/skill_initialization.py:23-28,62-64,70-87 对名为 .write- 加八个字符的文件，只要开头匹配 {"beforeBytes": 就接纳并删除；其余内容是否为发布器实际创建的临时文件、属于哪次准备，未验证。

隔离复现，在 backend 目录执行；只操作 TemporaryDirectory：

    from pathlib import Path
    from tempfile import TemporaryDirectory
    from app.overseas.management import skill_objects, skill_staging, skill_initialization

    with TemporaryDirectory(prefix='review-r4-data-') as tmp:
        root = Path(tmp) / 'skills'
        root.mkdir()
        skill_objects.prepare_release(root, [])
        stage = root / 'releases' / '.install-abcde123'
        stage.mkdir()
        important = stage / 'important.txt'
        important.write_bytes(b'irreplaceable user data')
        print('before_exists:', important.exists())
        print('before_bytes:', important.read_bytes())
        print('reclaimed_bytes:', skill_staging.reclaim(root))
        print('after_exists:', important.exists())

    with TemporaryDirectory(prefix='review-r4-init-') as tmp:
        root = Path(tmp) / 'skills'
        root.mkdir()
        evidence = root / '.write-abcde123'
        evidence.write_bytes(b'{"beforeBytes": keep this unknown user file')
        print('before:', evidence.read_bytes())
        print('recover_return:', skill_initialization.recover(root))
        print('after_exists:', evidence.exists())

原始输出，Windows 文件长度计量：

    before_exists: True
    before_bytes: b'irreplaceable user data'
    reclaimed_bytes: 23
    after_exists: False
    before: b'{"beforeBytes": keep this unknown user file'
    recover_return: True
    after_exists: False

普通文件与硬链接不同；backend/tests/test_skill_initialization_recovery.py:139-150 只证明硬链接拒绝删除，:153-170 的未知文件用例没有覆盖上述已索引目录和匹配临时文件前缀。修复应令清理范围的所属和内容可验证，未知内容保留并报错；也应覆盖恢复过程中再次中断。

### HIGH 2：恢复后安装/删除与管理员配置锁顺序相反，可触发数据库死锁

实际发布服务的安装及删除入口先调用 recover，再调用国内 install/delete（backend/app/overseas/management/skill_publisher.py:124-132,144-151）。无 pending 但有初始化残留或 staging 时，恢复先取 admission gate，且不提交事务即返回（backend/app/overseas/management/skill_publication.py:47-60）；其后国内 install/delete 调用 authorize，先请求权限 advisory lock（backend/app/modules/domestic_studio/skill_publication.py:19-29,44-45,84-86）。与此同时，绑定或启停接口先取得权限锁，再请求 gate（backend/app/modules/domestic_studio/management_router.py:138-143,152-157；bindings.py:36-44；skill_state.py:28-34）。两个事务交错即形成 gate → 权限锁和权限锁 → gate 的环；PostgreSQL 检测死锁后中止其中一个事务。

使用主 Agent 指定的 127.0.0.1:35439/hx_studio_test，在随机 schema 内创建真实 ExecutionGate；以下两个线程分别调用真实国内恢复、权限锁和 admission 锁，复现上面两个调用顺序。它直接编排函数顺序，没有模拟 HTTP；权限 advisory lock 在测试数据库范围内，其 key 由现有代码指定。测试后删除仅由本次创建的随机 schema，未连接生产：

    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from threading import Event
    from types import SimpleNamespace
    from uuid import uuid4
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import Session
    from app.execution.models import ExecutionGate
    from app.modules.auth.member_policy import lock_permissions
    from app.modules.domestic_studio import skill_publication
    from app.modules.domestic_studio.bindings import lock_admission
    from app.overseas.management import skill_objects

    base = create_engine('postgresql+psycopg://postgres@127.0.0.1:35439/hx_studio_test',
                         isolation_level='READ COMMITTED')
    schema = 'hx_studio_' + uuid4().hex
    with base.begin() as connection:
        assert schema not in inspect(connection).get_schema_names()
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = base.execution_options(schema_translate_map={None: schema})
    try:
        ExecutionGate.__table__.create(engine)
        with Session(engine) as session:
            session.add(ExecutionGate(id=1))
            session.commit()
        with TemporaryDirectory(prefix='review-r4-lock-') as tmp:
            root = Path(tmp) / 'skills'
            root.mkdir()
            skill_objects.prepare_release(root, [])
            stage = root / 'releases' / '.install-abcde123'
            stage.mkdir()
            (stage / 'manifest.json').write_bytes(b'partial')
            store = SimpleNamespace(installed_root=root, protected=False)
            gate_ready, permission_ready = Event(), Event()

            def publisher():
                try:
                    with Session(engine) as session:
                        session.execute(text("SET LOCAL statement_timeout = '8s'"))
                        skill_publication.recover(store, session)
                        gate_ready.set()
                        assert permission_ready.wait(4)
                        lock_permissions(session)
                        session.commit()
                    return 'publisher success'
                except Exception as error:
                    return ('publisher ' + type(error).__name__ + ' SQLSTATE=' +
                            str(getattr(getattr(error, 'orig', None), 'sqlstate', None)))

            def admin():
                try:
                    assert gate_ready.wait(4)
                    with Session(engine) as session:
                        session.execute(text("SET LOCAL statement_timeout = '8s'"))
                        lock_permissions(session)
                        permission_ready.set()
                        lock_admission(session)
                        session.commit()
                    return 'admin success'
                except Exception as error:
                    return ('admin ' + type(error).__name__ + ' SQLSTATE=' +
                            str(getattr(getattr(error, 'orig', None), 'sqlstate', None)))

            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(publisher)
                second = pool.submit(admin)
                print(first.result(timeout=12))
                print(second.result(timeout=12))
    finally:
        with base.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base.dispose()

原始输出：

    publisher OperationalError SQLSTATE=40P01
    admin success

修复时需统一跨路径锁顺序，并确保未提交状态恢复后的后续鉴权、撤权与绑定/启停写入仍有事务一致性；应以真实 PostgreSQL 对恢复与管理写入两种并发顺序验收。

## R3 修复复核及其边界

- R3 首次写空目录清单前/后、建立指针前崩溃：新测试以子进程 os._exit 直接退出并调用共享恢复器，见 backend/tests/test_skill_initialization_recovery.py:19-32,60-77；恢复过程中第二次退出见 :90-108。受测场景能恢复空索引并重试准备，不能扩展为所有路径安全，HIGH 1 是反例。
- 已安装目录准备 release/package 时的进程退出：测试检查原有索引保持并回收暂存目录，见同文件 :34-56,111-136；该测试未检查属于未知人员的普通文件是否会被误删。
- 无索引未知文件和硬链接：同文件 :139-170 验证部分拒绝路径；不覆盖以上两个误删反例。
- 本次独立运行 backend 目录下 .venv/Scripts/python.exe -m pytest -q tests/test_skill_initialization_recovery.py，原始输出：

      ............                                                             [100%]
      12 passed in 10.34s

## 其他核查与未验证边界

- 权限锁及绑定入口的代码顺序如 HIGH 2 所列；本轮未重新完整执行权限、CAS、ZIP、绑定列、引用回收、前端和海外全部回归，不能视为本轮通过。R3 报告中的 112 项后端、37 项前端及类型检查对应旧候选快照；主 Agent 提供的本轮 65 项通过为交接信息，非本 reviewer 独立复验。
- 未重新执行构建或类型检查，故本轮无编译原始输出。Stage 2 的质量、安全扫描和新旧页面实际视觉对照均未执行；本轮也未完成设计预览的实际页面比较或全范围 Spec 漂移检查。
- 五工作台、真实会话/执行、归档及部署仍在后续范围；用户确认的会话仅创建人可见、归档图片和对话资料对所有国内成员可见尚未实现，不将其算作本管理阶段已完成。
- 两项复现均在隔离临时文件及临时数据库 schema 中完成；未访问生产，未验证生产文件属主、部署、浏览器交互或真实上传下载。
