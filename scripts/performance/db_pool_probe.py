"""Real PostgreSQL/fork/billiard/role-pool checks inside a disposable Linux container."""
from concurrent.futures import ThreadPoolExecutor
import json
import multiprocessing as mp
import os
from pathlib import Path
from threading import Barrier, Event, Thread
import time

from billiard import Pool
from celery.signals import worker_process_init
import psycopg
from sqlalchemy import exc, text

from app.core.config import get_settings
from app.db import session as db, worker_budget  # noqa: F401 - actual signal registration


def identify():
    with db.get_engine().connect() as connection:
        return os.getpid(), connection.scalar(text('SELECT pg_backend_pid()'))


def fork_child(pipe):
    try:
        pipe.send(identify())
    finally:
        db.get_engine().dispose()
        pipe.close()


def celery_child():
    worker_process_init.send(sender=None)


def check_fork(engine):
    with engine.connect() as parent:
        parent_backend = parent.scalar(text('SELECT pg_backend_pid()'))
        parent.commit()
        with engine.connect() as idle:
            idle_backend = idle.scalar(text('SELECT pg_backend_pid()'))
        children = []
        # Reproduce a fork while another parent thread owns the singleton lock.
        entered, release = Event(), Event()
        def lock_thread():
            with db._engine_lock:
                entered.set()
                release.wait(10)
        thread = Thread(target=lock_thread)
        thread.start()
        assert entered.wait(5)
        try:
            for _ in range(3):
                left, right = mp.get_context('fork').Pipe()
                process = mp.get_context('fork').Process(target=fork_child, args=(right,))
                process.start(); right.close()
                try:
                    assert left.poll(10), 'child deadlocked on inherited engine lock'
                    children.append(left.recv())
                    process.join(5)
                    assert process.exitcode == 0
                finally:
                    if process.is_alive(): process.kill(); process.join(5)
                    left.close()
        finally:
            release.set(); thread.join(5)
        assert all(pid != os.getpid() and backend not in (parent_backend, idle_backend)
                   for pid, backend in children)
        assert parent.scalar(text('SELECT pg_backend_pid()')) == parent_backend
        parent.commit()
        # Actual billiard prefork + child replacement, as used by Celery.
        with Pool(processes=2, initializer=celery_child, maxtasksperchild=1) as pool:
            jobs = [pool.apply_async(identify) for _ in range(4)]
            replacements = [job.get(timeout=25) for job in jobs]
        assert len({pid for pid, _ in replacements}) == 4
        assert len({backend for _, backend in replacements}) == 4
        assert all(backend not in (parent_backend, idle_backend) for _, backend in replacements)
        assert parent.scalar(text('SELECT pg_backend_pid()')) == parent_backend
    return {'fork_children': len(children), 'billiard_replacement_children': len(replacements),
            'parent_connection_survived': True}


def role_child(pipe, role):
    os.environ.update(DB_POOL_SIZE=str(role['size']), DB_MAX_OVERFLOW='0', DB_APPLICATION_NAME=role['label'])
    get_settings.cache_clear()
    engine = db.get_engine()
    connections = []
    try:
        for _ in range(role['size']):
            conn = engine.connect()
            connections.append(conn)
            conn.execute(text('SELECT 1')); conn.commit()
        try:
            engine.connect()
            raise AssertionError('pool exceeded its bound')
        except exc.TimeoutError:
            pass
        pipe.send({'ready': True, 'label': role['label'], 'connections': len(connections)})
        assert pipe.poll(90), 'test coordinator disappeared'
        pipe.recv()
    finally:
        for conn in connections: conn.close()
        engine.dispose()
        pipe.close()


def check_roles(engine, roles):
    workers = []
    try:
        for role in roles:
            for _ in range(role['processes']):
                left, right = mp.get_context('spawn').Pipe()
                child = mp.get_context('spawn').Process(target=role_child, args=(right, role))
                child.start(); right.close()
                workers.append((child, left))
        for child, pipe in workers:
            assert pipe.poll(60), 'role pool did not initialize'
            assert pipe.recv()['ready']
        with engine.connect() as connection:
            rows = dict(connection.execute(text("SELECT application_name,count(*) FROM pg_stat_activity "
                          "WHERE datname=current_database() GROUP BY application_name")).all())
            for role in roles:
                assert rows.get(role['label']) == role['processes'] * role['size'], rows
            assert int(connection.scalar(text('SHOW max_connections'))) == 100
            assert int(connection.scalar(text('SHOW superuser_reserved_connections'))) == 3
        # Application pools saturated; migration and maintenance still connect.
        dsn = get_settings().database_url.replace('postgresql+psycopg://', 'postgresql://', 1)
        spare = []
        try:
            for index in range(11):
                conn = psycopg.connect(dsn, connect_timeout=3, autocommit=True,
                                      application_name='hx-migrate' if index == 10 else 'hx-maintenance')
                spare.append(conn)
                assert conn.execute('SELECT 1').fetchone()[0] == 1
        finally:
            for conn in spare: conn.close()
        return {'application_connections': sum(role['processes'] * role['size'] for role in roles),
                'process_pools': len(workers), 'all_overflow_rejected': True, 'spare_connections': 11}
    finally:
        for child, pipe in workers:
            try: pipe.send('release')
            except (BrokenPipeError, EOFError): pass
        for child, pipe in workers:
            child.join(10)
            if child.is_alive(): child.kill(); child.join(5)
            pipe.close()
        assert all(child.exitcode == 0 for child, _ in workers), 'role child failed or did not stop'


def main():
    assert get_settings().app_env == 'test' and get_settings().database_url.endswith('/media_test')
    barrier = Barrier(16)
    def first(_):
        barrier.wait()
        return db.get_engine()
    with ThreadPoolExecutor(max_workers=16) as pool:
        engines = list(pool.map(first, range(16)))
    assert all(engine is engines[0] for engine in engines)
    engine = engines[0]
    for attempt in range(30):
        try:
            identify(); break
        except Exception:
            if attempt == 29: raise
            time.sleep(.3)
    result = {'cold_threads_one_pool': 16, **check_fork(engine)}
    print('PASS cold start, real fork and billiard replacement', flush=True)
    roles = json.loads(Path('/fixtures/db-budget.json').read_text())
    result.update(check_roles(engine, roles))
    with engine.connect() as connection:
        for attempt in range(30):
            labels = set(connection.scalars(text("SELECT application_name FROM pg_stat_activity WHERE datname=current_database()")))
            if not labels.intersection(role['label'] for role in roles): break
            connection.rollback()
            time.sleep(.1)
        else: raise AssertionError('role connections leaked after child exit')
    result['role_connections_released'] = True
    engine.dispose()
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
