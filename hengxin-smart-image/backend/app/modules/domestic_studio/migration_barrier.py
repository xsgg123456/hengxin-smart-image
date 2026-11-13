"""Serialize a Studio schema migration against post-crash recovery probes."""
from sqlalchemy import text

KEY = 0x485853545544494F


def acquire(connection):
    connection.execute(text("SET LOCAL lock_timeout = '20s'"))
    connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': KEY})
