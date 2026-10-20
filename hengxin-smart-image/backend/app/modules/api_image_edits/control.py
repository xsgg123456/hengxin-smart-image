from .service import enabled
from .state import channel
from .claims import adopt_legacy


def resume(session, user):
    enabled()
    gate = channel(session)
    adopt_legacy(session, gate)
    gate.paused, gate.reason = False, None
    session.commit()
