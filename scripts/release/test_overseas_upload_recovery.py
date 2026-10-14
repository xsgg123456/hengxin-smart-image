import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('overseas-upload-recover.py'))
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)


def setup(tmp_path, monkeypatch):
    work = tmp_path / 'work'; work.mkdir()
    backup = tmp_path / 'backups/release'; backup.mkdir(parents=True)
    (backup / 'COMPLETE').write_text('ok')
    target = tmp_path / 'target/backend'
    pointer = tmp_path / '90.conf'; pointer.write_text('new')
    saved = backup / '90.conf'; saved.write_text('old')
    edge = tmp_path / 'edge'; edge.write_text('closed')
    inner = tmp_path / 'inner'; inner.write_text('old-inner')
    data = {'overseas': {'ids': {'api': 'old'}, 'mounts': {'api': []}, 'files': {}}}
    values = {'PHASE': 'verify-installed', 'FAILURE.json': json.dumps({'phase':'verify-installed','errorType':'AssertionError'}),
              'PREPARED':'tested','UPLOAD_CAPACITY_IMAGE_ID':'tested','topology.json':json.dumps(data),
              'domestic-native.json':'{}','native-target':str(target),'edge-before.conf':'old-edge',
              'upload-inner-before.conf':'old-inner','upload-edge-after.conf':'new-edge'}
    for name, value in values.items(): (work/name).write_text(value)
    events = []
    def event(name):
        return lambda *a, **k: events.append(name)
    m = NS(GROUPS=('overseas',), EDGE=edge, APP=tmp_path, image_id=Mock(return_value='tested'),
           live=Mock(return_value={'State':{'Running':False},'Image':'tested','HostConfig':{'Memory':3*1024**3},'Mounts':[]}),
           private=lambda p,v:p.write_text(v if isinstance(v,str) else json.dumps(v)),
           compose=Mock(side_effect=event('compose')),run=Mock(side_effect=event('run')),assets_safe=Mock())
    u = NS(API='api',UNITS=('worker','outbox'),DROP='90.conf',reload_edge=Mock(side_effect=event('open')))
    u.switch_native=Mock(side_effect=lambda *a: events.append('switch:'+u.DROP))
    r = NS(PREFIX='web-',hashes=Mock(),publish=Mock(side_effect=event('publish')))
    verify = NS(proxy=Mock(side_effect=event('proxy')),frontend=Mock(),public=Mock(side_effect=event('public')))
    proxy = NS(inner=lambda m:inner,install_inner=Mock(side_effect=event('install-inner')),
               verify=Mock(side_effect=event('boundary')),restore_inner=Mock())
    d = NS(m=m,u=u,r=r,verify=verify,proxy=proxy,BACKUPS=tmp_path/'backups',resources=NS(API_MEMORY=3*1024**3),
           schemas=Mock(),prepared_settings=Mock(),domestic_native=Mock(return_value={}),closed_config=lambda x:'closed',
           closed=Mock(),close_edge=Mock(),drain_and_stop=Mock(side_effect=event('drain')),
           installed=Mock(side_effect=event('installed')),resources_unchanged=Mock())
    monkeypatch.setattr(rec,'pointers',Mock(return_value={str(pointer):saved}))
    return d, work, {'release':'release','files':{}}, events, pointer


def test_forward_recovery_order_and_no_database_restore(tmp_path,monkeypatch):
    d,w,manifest,events,pointer=setup(tmp_path,monkeypatch)
    rec.recover(d,w,tmp_path,manifest,'image')
    assert pointer.read_text()=='old'
    assert events.index('drain') < events.index('switch:99-overseas-upload.conf') < events.index('installed') < events.index('install-inner') < events.index('publish') < events.index('open') < events.index('boundary')
    assert (w/'PHASE').read_text()=='complete'
    assert d.u.DROP=='90.conf'
    assert d.m.compose.call_count==1
    assert '--no-build' in d.m.compose.call_args.args
    assert 'migrate' not in str(d.m.compose.call_args)


@pytest.mark.parametrize('failure',['installed','public','boundary'])
def test_failure_closes_without_stopping_unknown_executors(tmp_path,monkeypatch,failure):
    d,w,manifest,events,_=setup(tmp_path,monkeypatch)
    target = {'installed':d.installed,'public':d.verify.public,'boundary':d.proxy.verify}[failure]
    target.side_effect=RuntimeError('failure')
    with pytest.raises(RuntimeError): rec.recover(d,w,tmp_path,manifest,'image')
    d.close_edge.assert_called_once()
    d.proxy.restore_inner.assert_called_once()
    assert d.m.compose.call_args.args[1:]==('stop','-t','30','api')
    assert d.drain_and_stop.call_count==1
    assert not (w/'verification.json').exists()


@pytest.mark.parametrize('guard',['replay','capacity','memory'])
def test_failed_preconditions_do_not_mutate(tmp_path,monkeypatch,guard):
    d,w,manifest,events,_=setup(tmp_path,monkeypatch)
    if guard=='replay': (w/'RECOVERY_STARTED').write_text('old')
    if guard=='capacity': (w/'UPLOAD_CAPACITY_IMAGE_ID').write_text('wrong')
    if guard=='memory': d.m.live.return_value['HostConfig']['Memory']=384*1024**2
    with pytest.raises(AssertionError): rec.recover(d,w,tmp_path,manifest,'image')
    assert not events


def test_pointers_preserve_higher_override_and_reject_drift(tmp_path,monkeypatch):
    import hashlib
    monkeypatch.setattr(rec,'Path',lambda path:tmp_path / str(path).lstrip('/'))
    folder=tmp_path/'etc/systemd/system/worker.service.d';folder.mkdir(parents=True)
    backup=tmp_path/'backup';(backup/folder.name).mkdir(parents=True)
    saved=backup/folder.name/'90.conf';saved.write_text('baseline')
    path=folder/'90.conf';target=tmp_path/'target'
    command=str(target/'.venv/bin/celery')+' -A app.overseas.execution.worker:celery_app worker --pool=prefork --concurrency=5 --queues=overseas.cli --loglevel=INFO --hostname=overseas@%H'
    path.write_text('[Service]\nWorkingDirectory='+str(target)+'\nExecStart=\nExecStart='+command+'\n')
    higher=folder/'95-codex-astra.conf';higher.write_text('preserve')
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    data={'nativeFiles':{str(path):digest(saved),str(higher):digest(higher)}}
    d=NS(u=NS(DROP='90.conf',UNITS=('worker',)),m=NS(digest=digest))
    assert rec.pointers(d,tmp_path,data,target,backup)=={str(path):saved}
    higher.write_text('concurrent edit')
    with pytest.raises(AssertionError):rec.pointers(d,tmp_path,data,target,backup)
