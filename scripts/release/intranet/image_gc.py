"""Docker retention for two complete deployments; caller owns release lock/history."""
import json
import re
import time


IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')
REPORT = 'intranet-image-cleanup.json'
DF = ['curl', '--silent', '--show-error', '--fail', '--unix-socket',
      '/var/run/docker.sock', 'http://localhost/system/df']


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def image_id(value):
    require(isinstance(value, str) and IMAGE.fullmatch(value), 'Invalid full image ID')
    return value


def expected(u):
    names = set(u.APPS) | set(u.DATA) | {'https'}
    require(len(names) == 17, 'Expected exactly 17 deployment services')
    return names


def containers(u):
    ids = u.run(['docker', 'ps', '-aq', '--no-trunc']).split()
    require(len(ids) == len(set(ids)), 'Duplicate container inventory')
    result = json.loads(u.run(['docker', 'inspect', *ids])) if ids else []
    require(isinstance(result, list) and len(result) == len(ids)
            and {item['Id'] for item in result} == set(ids), 'Incomplete container inventory')
    for item in result:
        image_id(item['Image'])
    return result


def live(u, inventory):
    names, result = expected(u), {}
    for item in inventory:
        labels = item['Config'].get('Labels') or {}
        project = labels.get('com.docker.compose.project')
        name = item['Name'].removeprefix('/')
        if project not in ('hengxin-lan', 'hengxin-lan-edge') and name not in {
                'hengxin-lan-' + service for service in names}:
            continue
        service = labels.get('com.docker.compose.service')
        require(service in names and service not in result, 'Unexpected/duplicate deployment service')
        require(project == ('hengxin-lan-edge' if service == 'https' else 'hengxin-lan')
                and name == 'hengxin-lan-' + service, 'Deployment container identity changed')
        state = item['State']
        require(state.get('Running') is True and not state.get('Paused')
                and not state.get('Restarting')
                and state.get('Health', {}).get('Status', 'healthy') == 'healthy',
                'Deployment container not healthy: ' + service)
        result[service] = image_id(item['Image'])
    require(set(result) == names, 'Incomplete deployment container set')
    return result


def capture(u):
    return live(u, containers(u))


def images(u):
    return {image_id(value) for value in u.run(
        ['docker', 'image', 'ls', '-aq', '--no-trunc']).split()}


def layer_bytes(u):
    value = json.loads(u.run(DF))['LayersSize']
    require(type(value) is int and value >= 0, 'Invalid Docker deduplicated layer size')
    return value


def check_map(u, value):
    require(isinstance(value, dict) and set(value) == expected(u), 'Incomplete deployment image map')
    return {image_id(image) for image in value.values()}


def checked(u, current, retained):
    inventory = containers(u)
    require(live(u, inventory) == current, 'Live deployment images changed')
    present = images(u)
    require(retained <= present, 'Retained deployment image is missing')
    return present, {item['Image'] for item in inventory}


def execute(u, store, current, previous, known, apply=False):
    """No version advancement: maps come from the atomic full-deployment ledger."""
    retained = check_map(u, current)
    if previous is not None:
        retained |= check_map(u, previous)
    require(isinstance(known, set), 'Known image history must be a set')
    known = {image_id(value) for value in known}
    present, referenced = checked(u, current, retained)
    kept = {}
    for value in sorted(present):
        reasons = []
        if value in retained:
            reasons.append('retained-deployment')
        if value in referenced:
            reasons.append('container-reference')
        if value not in known:
            reasons.append('unknown-or-unpublished-image')
        if reasons:
            kept[value] = reasons
    report = {'status': 'preview', 'time_ns': time.time_ns(), 'kept': kept,
              'candidates': sorted((present & known) - retained - referenced),
              'deleted': [], 'errors': [], 'before_bytes': layer_bytes(u),
              'bytes_scope': 'docker-system-df-LayersSize',
              'receipt_accounting': 'caller-measures-state-directory-growth'}
    if not apply:
        return report
    report['status'] = 'cleaning'
    store.report(REPORT, report)
    for value in report['candidates']:
        try:
            now, refs = checked(u, current, retained)
        except Exception as exc:
            report['errors'].append({'image': value, 'type': type(exc).__name__, 'stage': 'recheck'})
            break
        if value in refs:
            report['kept'][value] = ['new-container-reference']
            continue
        if value not in now:
            report['kept'][value] = ['already-absent-before-delete']
            continue
        failed = False
        try:
            u.run(['docker', 'image', 'rm', '--no-prune', value])
        except Exception as exc:
            failed = True
            report['errors'].append({'image': value, 'type': type(exc).__name__, 'stage': 'remove'})
        try:
            after = images(u)
            if value in after:
                report['kept'][value] = ['docker-conflict-or-image-still-present']
                if not failed:
                    report['errors'].append({'image': value, 'type': 'ImageStillPresent', 'stage': 'verify'})
            elif not failed:
                report['deleted'].append(value)
        except Exception as exc:
            report['errors'].append({'image': value, 'type': type(exc).__name__, 'stage': 'verify'})
            break
        store.report(REPORT, report)
    try:
        checked(u, current, retained)
        report['after_bytes'] = layer_bytes(u)
        report['released_bytes'] = report['before_bytes'] - report['after_bytes']
    except Exception as exc:
        report['errors'].append({'type': type(exc).__name__, 'stage': 'postcheck'})
    report['status'] = 'warning' if report['errors'] else 'complete'
    store.report(REPORT, report)
    return report
