import copy

import pytest

import domestic_studio_wiring as wiring
import joint_studio_verify as verify
import joint_studio_gate_wiring as gate


def live():
    def environment(values):
        return [key + '=' + value for key, value in values.items()]
    def mounts(values):
        return [{'Type': 'bind', 'Source': path, 'Destination': path, 'RW': rw} for path, rw in values]
    api_env = dict(wiring.native_environment(), DOMESTIC_SKILL_PUBLISH_SOCKET=wiring.SOCKET,
                   DATABASE_URL='postgresql+psycopg://domestic/db')
    pub_env = {'DATABASE_URL': api_env['DATABASE_URL'], 'DOMESTIC_SKILL_ROOT': wiring.SKILLS,
               'DOMESTIC_SKILL_TRANSFER_ROOT': wiring.TRANSFERS,
               'DOMESTIC_SKILL_PUBLISH_SOCKET': wiring.SOCKET, 'DOMESTIC_STUDIO_PROTECTED': '1'}
    result = {'domestic-api': {'Config': {'Env': environment(api_env)},
                             'Mounts': mounts(((wiring.SKILLS, False), (wiring.LOCKS, True), (wiring.SOCKET_DIR, False)))},
            wiring.PUBLISHER: {'Config': {'Env': environment(pub_env), 'User': '0:0'},
                               'HostConfig': {'Privileged': False, 'ReadonlyRootfs': True, 'CapDrop': ['ALL'],
                                              'CapAdd': ['CHOWN'], 'SecurityOpt': ['no-new-privileges:true']},
                               'Mounts': mounts(((wiring.SKILLS, True), (wiring.TRANSFERS, True),
                                                 (wiring.SOCKET_DIR, True)))}}
    for name in gate.SERVICES:
        info = result.setdefault(name, {'Config': {'Env': []}, 'Mounts': []})
        info['Config']['Env'].append(gate.ENVIRONMENT + '=' + gate.DIRECTORY)
        info['Mounts'].extend(mounts(((gate.DIRECTORY, False),)))
    return result


def contexts():
    result = {name: {'user': 1001, 'group': 1001, 'extra_groups': [986], 'env': {gate.ENVIRONMENT: gate.DIRECTORY}}
              for name in gate.NATIVE}
    for name in ('hengxin-vps-codex-worker', 'hengxin-domestic-deletions'):
        result[name]['env'].update(wiring.native_environment())
    return result


def test_accepts_exact_new_runtime_configuration():
    verify.configuration(live(), contexts())


@pytest.mark.parametrize('case', ['api_flag', 'worker_flag', 'wrong_group', 'api_mount', 'publisher_mount',
                                   'database', 'foreign_secret', 'privileged', 'extra_capability', 'exposed_port',
                                   'gate_missing', 'gate_writable', 'gate_native'])
def test_rejects_runtime_identity_permission_or_isolation_drift(case):
    containers, native = copy.deepcopy(live()), copy.deepcopy(contexts())
    if case == 'api_flag': containers['domestic-api']['Config']['Env'].remove('DOMESTIC_STUDIO_PROTECTED=1')
    elif case == 'worker_flag': native['hengxin-vps-codex-worker']['env']['DOMESTIC_STUDIO_PROTECTED'] = '0'
    elif case == 'wrong_group': native['hengxin-domestic-deletions']['extra_groups'] = []
    elif case == 'api_mount': containers['domestic-api']['Mounts'][0]['RW'] = True
    elif case == 'publisher_mount': containers[wiring.PUBLISHER]['Mounts'][0]['Source'] = '/foreign'
    elif case == 'database': containers[wiring.PUBLISHER]['Config']['Env'][0] = 'DATABASE_URL=postgresql+psycopg://foreign/db'
    elif case == 'foreign_secret': containers[wiring.PUBLISHER]['Config']['Env'].append('OVERSEAS_API_KEY=secret')
    elif case == 'privileged': containers[wiring.PUBLISHER]['HostConfig']['Privileged'] = True
    elif case == 'extra_capability': containers[wiring.PUBLISHER]['HostConfig']['CapAdd'].append('SYS_ADMIN')
    elif case == 'exposed_port': containers[wiring.PUBLISHER]['HostConfig']['PortBindings'] = {'8080/tcp': [{}]}
    elif case == 'gate_missing': containers['overseas-api']['Config']['Env'].clear()
    elif case == 'gate_writable': containers['overseas-api']['Mounts'][0]['RW'] = True
    else: native['hengxin-codex-auth']['env'][gate.ENVIRONMENT] = '/other'
    with pytest.raises(RuntimeError):
        verify.configuration(containers, native)
