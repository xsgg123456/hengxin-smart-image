"""Private, atomic release ledger and one host-wide project lock."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile

GROUPS = ('domestic', 'overseas', 'identity')
IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')
RELEASE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def images(value):
    require(isinstance(value, dict) and value, 'Empty or invalid image set')
    require(all(isinstance(k, str) and isinstance(v, str) and IMAGE.fullmatch(v)
                for k, v in value.items()), 'Invalid image identity')


def validate(data):
    require(isinstance(data, dict) and data.get('version') == 1, 'Invalid retention version')
    require(isinstance(data.get('groups'), dict) and set(data['groups']) <= set(GROUPS),
            'Invalid retention groups')
    for value in data['groups'].values():
        require(isinstance(value, dict) and set(value) == {'current', 'previous'},
                'Invalid group history')
        images(value['current'])
        if value['previous'] is not None:
            images(value['previous'])
            require(set(value['previous']) == set(value['current']), 'Inconsistent service history')
    require(isinstance(data.get('pending'), dict), 'Invalid pending releases')
    for release, value in data['pending'].items():
        require(RELEASE.fullmatch(release) and isinstance(value, dict), 'Invalid candidate')
        require(value.get('phase') in ('build', 'built', 'prepare', 'prepared',
                                      'deploy', 'failed', 'verified'), 'Invalid candidate phase')
        require(value.get('image') is None or (isinstance(value['image'], str)
                and IMAGE.fullmatch(value['image'])), 'Invalid candidate ID')
        if 'before' in value:
            require(set(value['before']) == set(GROUPS), 'Incomplete deployment snapshot')
            for group in value['before'].values():
                images(group)
    require(isinstance(data.get('completed', {}), dict), 'Invalid completed releases')
    for release, snapshot in data.get('completed', {}).items():
        require(RELEASE.fullmatch(release) and isinstance(snapshot, dict)
                and set(snapshot) == set(GROUPS), 'Invalid completed snapshot')
        for group in snapshot.values():
            images(group)
    return data


def advance(data, before, after):
    """Only called after the existing deploy function and verification returned."""
    for group in GROUPS:
        old = data['groups'].get(group)
        if old:
            require(old['current'] == before[group], 'Recorded current version drift: ' + group)
        if before[group] != after[group]:
            data['groups'][group] = {'current': after[group], 'previous': before[group]}
        elif not old:
            data['groups'][group] = {'current': after[group], 'previous': None}
    return validate(data)


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('HENGXIN_RELEASE_STATE_DIR',
                                                '/var/lib/hengxin-release'))
        require(not self.root.is_symlink(), 'State directory must not be a symlink')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.root / 'retention.json'

    @contextmanager
    def locked(self):
        path = self.root / 'release.lock'
        require(not path.is_symlink(), 'Lock must not be a symlink')
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b'0')
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def load(self):
        require(not self.path.is_symlink(), 'Ledger must not be a symlink')
        if not self.path.exists():
            return {'version': 1, 'groups': {}, 'pending': {}}
        return validate(json.loads(self.path.read_text(encoding='utf-8')))

    def write(self, data):
        validate(data)
        self.report('retention.json', data)

    def report(self, name, data):
        require(Path(name).name == name, 'Invalid report path')
        fd, name_tmp = tempfile.mkstemp(prefix='.retention-', dir=self.root)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name_tmp, self.root / name)
            if os.name != 'nt':
                directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if os.path.exists(name_tmp):
                os.unlink(name_tmp)
