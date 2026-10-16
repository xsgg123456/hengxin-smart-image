from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


def compete(fn):
    barrier = Barrier(2)
    def call(i):
        barrier.wait(timeout=10)
        return fn(i)
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(call, range(2)))
