"""Explicit, isolated real-Skill acceptance. Each requested round can spend model usage."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time
import threading
from uuid import uuid4

import httpx

from phase11a_checks import Evidence, image_evidence, require, save_report
from phase11a_environment import Phase11AEnvironment

NOTE = ('开发机验收：将参考素材的壁纸和前置镜头替换到目标屏幕，保留原模板文字、边框和装饰。'
        '本轮用户已豁免尺寸一致性，可交付原生生成尺寸，不因尺寸不同而重试；仍须使用真实图像工具并正确写交付清单。')


class Acceptance:
    def __init__(self, environment, inputs, output):
        self.env, self.inputs, self.output = environment, inputs, output
        self.client = httpx.Client(base_url=environment.base_url, trust_env=False, timeout=60)
        self.evidence = Evidence(environment)
        self.report = {'status': 'running', 'stages': {}, 'dimensionException': True}
        self.report_lock = threading.Lock()

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        require(response.is_success, f'{method} {path}: HTTP {response.status_code}')
        return response.json()

    def record(self, label, value):
        with self.report_lock:
            self.report['stages'][label] = value
            save_report(self.output / 'report.json', self.report)
        print(json.dumps({'stage': label, 'recorded': True}, ensure_ascii=False), flush=True)

    def wait(self, tasks, label, timeout=1200):
        deadline, last = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            details = [self.request('GET', '/api/v1/tasks/' + task) for task in tasks]
            stages = [self.request('GET', '/api/v1/tasks/' + task + '/execution') for task in tasks]
            self.evidence.sample(tasks)
            current = [(item['task']['state'], stage['stage'], len(stage['events']))
                       for item, stage in zip(details, stages)]
            if current != last:
                print(json.dumps({'phase': label, 'progress': current}, ensure_ascii=False), flush=True)
                last = current
            for item, stage in zip(details, stages):
                if item['task']['state'] in ('失败', '部分失败'):
                    self.record(label + '-failure', stage)
                    raise RuntimeError(label + ' did not succeed; no automatic model retry')
            if all(item['task']['state'] == '待查看' for item in details):
                self.record(label + '-observations', stages)
                return details
            time.sleep(2)
        raise TimeoutError(label + ' acceptance deadline')

    def setup(self):
        manifest = json.loads((self.inputs / 'inputs.json').read_text())
        self.record('input-provenance', manifest)
        uploads = []
        for file in manifest['files']:
            data = (self.inputs / file['name']).read_bytes()
            require(hashlib.sha256(data).hexdigest() == file['sha256'], 'Input changed after export')
            uploads.append(self.request('POST', '/api/v1/files',
                files={'file': (file['name'], data, file['mime'])}))
        package = (self.inputs / 'skill.zip').read_bytes()
        require(hashlib.sha256(package).hexdigest() == manifest['skillChecksum'], 'Skill package changed')
        skill = self.request('POST', '/api/v1/management/skills',
            data={'mode': 'wallpaper', 'version': manifest['skillVersion']},
            files={'file': ('skill.zip', package, 'application/zip')})
        self.skill = skill['id']
        self.request('POST', f'/api/v1/management/skills/{self.skill}/install')
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            versions = self.request('GET', '/api/v1/management/skills')
            installed = next(item for item in versions if item['id'] == self.skill)
            require(installed['status'] != 'failed', 'Skill installation failed')
            if installed['status'] == 'available':
                break
            time.sleep(1)
        require(installed['status'] == 'available', 'Skill installation timeout')
        self.sources = uploads[2:]
        self.template = self.request('POST', '/api/v1/templates', json={
            'name': 'Phase11A隔离双图', 'mode': 'wallpaper', 'images': uploads[:2],
            'skillVersionId': self.skill, 'active': True, 'notes': '独立联调，尺寸按已授权例外'})
        self.single = self.request('POST', '/api/v1/templates', json={
            'name': 'Phase11A隔离单图', 'mode': 'wallpaper', 'images': uploads[:1],
            'skillVersionId': self.skill, 'active': True, 'notes': '双任务并行用'})

    def submit(self, label, template=None):
        template = template or self.template
        body = dict(mode='wallpaper', name='Phase11A-' + label, sku=label, sources=self.sources,
                    note=NOTE, skillVersionId=self.skill, templateId=template['id'], templateVersion=template['version'])
        key = uuid4().hex
        start = time.monotonic()
        receipt = self.request('POST', '/api/v1/tasks', json=body, headers={'Idempotency-Key': key})
        elapsed = time.monotonic() - start
        require(receipt['state'] == '排队中', 'Submission did not acknowledge queue')
        require(self.request('POST', '/api/v1/tasks', json=body, headers={'Idempotency-Key': key}) == receipt,
                'Idempotent submission changed receipt')
        self.record(label + '-receipt', dict(receipt, responseSeconds=elapsed))
        return receipt['taskId']

    def revise(self, task, target, note, key=None):
        return self.client.post('/api/v1/tasks/' + task + '/rounds',
            json={'taskId': task, 'target': target, 'note': note + NOTE},
            headers={'Idempotency-Key': key or uuid4().hex})

    def serial(self):
        task = self.submit('serial')
        initial = self.wait([task], 'initial')[0]
        identity = initial['task']['sessionId']
        require(identity and initial['task']['executionSource'] == 'cli', 'Not a real CLI session')
        first = image_evidence(self.client, initial['task']['images'], self.output, 'initial')
        require(len(first) == 2, 'Expected two initial outputs')
        old = [slot['currentVersionId'] for slot in initial['slots']]
        key = uuid4().hex
        response = self.revise(task, 0, '仅修改第一张，使屏幕细节更清晰，保持其他部分。', key)
        require(response.status_code == 202, 'Single revision not accepted')
        require(self.revise(task, 0, '仅修改第一张，使屏幕细节更清晰，保持其他部分。', key).json()
                == response.json(), 'Revision replay changed receipt')
        require(self.revise(task, None, '竞争请求不应执行。').status_code == 409, 'Same-task exclusivity failed')
        revised = self.wait([task], 'single-revision')[0]
        current = [slot['currentVersionId'] for slot in revised['slots']]
        require(current[0] != old[0] and current[1] == old[1], 'Single revision changed unrelated slot')
        require(revised['task']['sessionId'] == identity, 'Single revision replaced session')
        archive = self.request('POST', '/api/v1/tasks/' + task + '/archives',
            json={'imageVersionIds': current}, headers={'Idempotency-Key': uuid4().hex})
        archived = image_evidence(self.client, archive['images'], self.output, 'archive-before')
        self.env.restart_services()
        self.client.close()
        self.client = httpx.Client(base_url=self.env.base_url, trust_env=False, timeout=60)
        from phase11a_faults import whole_revision_recovery
        interrupted_attempt = whole_revision_recovery(self, task)
        whole = self.wait([task], 'whole-revision-recovery')[0]
        require(whole['task']['sessionId'] == identity, 'Restart/whole revision replaced session')
        self.evidence.ownership(self.client, whole)
        require(all(slot['currentVersionId'] != previous for slot, previous in zip(whole['slots'], current)),
                'Whole revision did not create every slot')
        preserved = self.request('GET', '/api/v1/archives/' + archive['id'])
        require(preserved['imageVersionIds'] == current, 'Archive version references changed')
        require(image_evidence(self.client, preserved['images'], self.output, 'archive-after') == archived,
                'Archived bytes changed after restart/revision')
        for before, slot in zip(first, whole['slots']):
            data = self.client.get(slot['versions'][0]['url']).content
            require(hashlib.sha256(data).hexdigest() == before['sha256'], 'Old result bytes changed')
        rounds = [initial['task']['currentRoundId'], revised['task']['currentRoundId'], whole['task']['currentRoundId']]
        attempts = self.evidence.round_evidence(task, rounds)
        require(next(row['id'] for row in attempts if row['round_id'] == rounds[-1]) == interrupted_attempt,
                'Recovery replaced the original attempt')
        self.record('serial-acceptance', {'taskId': task, 'sessionId': identity, 'archiveId': archive['id'],
            'singleSlotIsolated': True, 'archiveBytesPreserved': True,
            'attempts': attempts})

    def parallel(self):
        self.env.set_concurrency(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = list(pool.map(lambda name: self.submit(name, self.single), ['parallel-a', 'parallel-b']))
        details = self.wait(tasks, 'parallel')
        require(len({item['task']['sessionId'] for item in details}) == 2, 'Parallel sessions mixed')
        require(any(all(task in sample['tasks'] and any('codex' in process['name']
                    for process in sample['tasks'][task].values()) for task in tasks)
                    for sample in self.evidence.samples), 'No simultaneous real CLI process evidence')
        attempts = [self.evidence.round_evidence(task) for task in tasks]
        require(all(len(rows) == 1 for rows in attempts), 'Parallel task executed more than once')
        require(attempts[0][0]['process_id'] != attempts[1][0]['process_id'], 'Parallel PID mixed')
        self.evidence.isolation(tasks)
        for index, detail in enumerate(details):
            self.evidence.ownership(self.client, detail)
            image_evidence(self.client, detail['task']['images'], self.output, f'parallel-{index}')
        self.record('parallel-acceptance', {'taskIds': tasks, 'attempts': attempts,
            'sessions': [item['task']['sessionId'] for item in details], 'simultaneousCliObserved': True,
            'actualSandboxReadWriteIsolation': True})
        self.env.set_concurrency(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-live', action='store_true', required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    environment, run = Phase11AEnvironment(args.output), None
    try:
        with environment as env:
            run = Acceptance(env, args.inputs, args.output)
            try:
                run.setup()
                run.serial()
                run.parallel()
                from phase11a_faults import verify_cancellation_timeout
                verify_cancellation_timeout(run)
                run.report['status'] = 'passed'
            except Exception as error:
                run.report.update(status='failed', error=type(error).__name__ + ': ' + str(error))
                raise
            finally:
                run.report['resourceSamples'] = run.evidence.samples
                save_report(args.output / 'report.json', run.report)
                run.evidence.close()
                run.client.close()
    finally:
        report = run.report if run else {'status': 'failed', 'error': 'Environment startup failed'}
        report['environment'] = environment.report
        if not environment.report.get('cleanupComplete'):
            report['status'] = 'failed'
        save_report(args.output / 'report.json', report)


if __name__ == '__main__':
    main()
