"""A local config must target the same database/storage protected by the idle gate."""
import json

import pytest

from test_local_codex_control import config, control  # noqa: F401


def inspection(config):
    c = control.Controller('hx-local-test', *config)
    containers = []
    for service, internal, external in [('postgres', '5432/tcp', '55433'), ('minio', '9000/tcp', '59002')]:
        containers.append({
            'Id': service, 'State': {'Running': True},
            'Config': {'Labels': {'com.docker.compose.project': c.project,
                'com.docker.compose.project.working_dir': str(control.INFRA),
                'com.docker.compose.project.config_files': str(control.INFRA / 'compose.yaml'),
                'com.docker.compose.service': service}, 'Env': ['POSTGRES_PASSWORD=secret']},
            'NetworkSettings': {'Ports': {internal: [{'HostIp': '127.0.0.1', 'HostPort': external}]}}
        })
    def run(argv, **kwargs):
        if 'context' in argv:
            return json.dumps([{'Endpoints': {'docker': {'Host': 'npipe:////./pipe/dockerDesktopLinuxEngine'}}}])
        if 'ps' in argv:
            return 'postgres minio'
        return json.dumps(containers)
    c.run = run
    return c, containers


def test_matching_project_endpoints_pass(config):
    c, _ = inspection(config)
    c.inspect()


@pytest.mark.parametrize('key', ['POSTGRES_PORT', 'MINIO_PORT'])
def test_config_pointing_at_other_project_is_refused(config, key):
    c, _ = inspection(config)
    c.base[key] = '59999'  # Same credentials and project labels cannot excuse wrong ports.
    with pytest.raises(control.Refused, match='loopback port'):
        c.inspect()


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('binding', [None, [], [{'HostIp': '0.0.0.0', 'HostPort': '55433'}]])
def test_missing_or_nonloopback_bindings_refused(config, index, binding):
    c, containers = inspection(config)
    port = next(iter(containers[index]['NetworkSettings']['Ports']))
    containers[index]['NetworkSettings']['Ports'][port] = binding
    with pytest.raises(control.Refused, match='loopback port'):
        c.inspect()
