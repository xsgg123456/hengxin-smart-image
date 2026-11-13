"""Private domestic publisher using the same server and package pipeline as overseas."""
import os
from pathlib import Path

from app.core.config import get_settings
from app.db.session import session_factory
from app.overseas.management.skill_publisher import create_app, serve
from app.overseas.management.skill_transfer_store import TransferStore
from . import skill_publication
from .installed_skills import DOMESTIC_ROOT, DomesticInstalledSkills
from .management_router import PUBLISH_SOCKET
from . import protected as protection

TRANSFER_ROOT = Path('/var/lib/hengxin-domestic/skill-transfers')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Skill publisher must run as root')
    os.umask(0o022)
    settings = get_settings()
    root = Path(os.environ.get('DOMESTIC_SKILL_ROOT', str(DOMESTIC_ROOT)))
    transfer_root = Path(os.environ.get('DOMESTIC_SKILL_TRANSFER_ROOT', str(TRANSFER_ROOT)))
    socket = os.environ.get('DOMESTIC_SKILL_PUBLISH_SOCKET', PUBLISH_SOCKET)
    protected = protection.enabled(settings)
    DomesticInstalledSkills(root, protected=protected)
    if protected and (transfer_root != TRANSFER_ROOT or socket != PUBLISH_SOCKET):
        raise ValueError('Unapproved domestic publisher paths')
    if not root.is_dir():
        raise ValueError('Domestic Skill directory must be provisioned before starting publisher')
    store = TransferStore(transfer_root, root, protected=protected)
    app = create_app(store, session_factory(), publication=skill_publication, allow_maintenance=False)
    serve(store, app, socket)


if __name__ == '__main__':
    main()
