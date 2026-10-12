"""Close fixture writers before the paired object/database restore drill."""


def finish(processes, engines, redis, restore_objects=False):
    try:
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        if restore_objects:
            from object_restore import run
            run()
    finally:
        for engine in engines.values():
            engine.dispose()
        redis.close()
