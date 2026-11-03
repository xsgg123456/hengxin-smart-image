"""Refresh only the pinned web container, then prove public overseas readiness."""
import json
import re
import subprocess
import time

WEB = 'hengxin-vps-staging-web-1'
READY = 'https://zhitu.qhhengxin.top/api/overseas/v1/health/ready'


def remaining(r,deadline):
    value = deadline-time.monotonic()
    r.require(value>0,'Public API readiness deadline exceeded')
    return value


def readiness(r,timeout=40,deadline=None):
    deadline = time.monotonic()+timeout if deadline is None else deadline
    last = None
    while time.monotonic()<deadline:
        try:
            budget = min(5,remaining(r,deadline))
            raw = r.run('curl','--max-time',str(budget),'-fsS','--proto','=https',
                '-H','Cache-Control: no-cache','--write-out','\n%{http_code}',READY,timeout=budget)
            payload,_,status = raw.rpartition('\n')
            r.require(status=='200','Public API readiness HTTP status invalid')
            body = json.loads(payload)
            checks = body.get('checks') if isinstance(body,dict) else None
            r.require(isinstance(checks,dict) and {'postgresql','redis','minio'}<=set(checks) and
                all(v=='up' for v in checks.values()) and body.get('status')=='ready',
                'Public API readiness payload invalid')
            remaining(r,deadline)
            return
        except (RuntimeError,ValueError,TimeoutError,subprocess.TimeoutExpired) as exc:
            last = exc
            time.sleep(min(0.5,max(0,deadline-time.monotonic())))
    raise RuntimeError('Public API readiness deadline exceeded') from last


def refresh(r,data,timeout=40):
    deadline = time.monotonic()+timeout
    saved = data['protected']['containers'].get(WEB,{})
    r.require(re.fullmatch('[a-f0-9]{64}',saved.get('id','')) and saved.get('running') is True,
        'Pinned web identity missing')
    live = json.loads(r.run('docker','inspect',WEB,timeout=remaining(r,deadline)))[0]
    labels = live['Config'].get('Labels') or {}
    r.require(live['Id']==saved['id'] and live['Image']==saved.get('image') and
        live['Name']=='/'+WEB and live['State']['Running'] and
        labels.get('com.docker.compose.project')=='hengxin-vps-staging' and
        labels.get('com.docker.compose.service')=='web','Web identity drift')
    # Pin exec to the verified ID so a name replacement cannot target another container.
    r.run('docker','exec',saved['id'],'nginx','-t',timeout=remaining(r,deadline))
    r.run('docker','exec',saved['id'],'nginx','-s','reload',timeout=remaining(r,deadline))
    readiness(r,deadline=deadline)
