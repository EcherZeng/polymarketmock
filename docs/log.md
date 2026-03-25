WARNING:  WatchFiles detected changes in 'app\storage\duckdb_store.py', '_test_timeline.py', 'app\models\backtest.py', 'app\config.py', 'app\main.py', 'app\routers\markets.py', 'app\services\backtest_engine.py', 'app\storage\data_collector.py', 'app\storage\redis_store.py', 'app\services\event_lifecycle.py', '_health.py'. Reloading...
 INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [16916]
WARNING:  WatchFiles detected changes in 'app\storage\data_collector.py'. Reloading...
 Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=5296, pipe_handle=612)
                                                  ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\multiprocessing\spawn.py", line 122, in spawn_main
    exitcode = _main(fd, parent_sentinel)
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\multiprocessing\spawn.py", line 132, in _main       
    self = reduction.pickle.load(from_parent)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\__init__.py", line 1, in <module>
    from uvicorn.config import Config
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\config.py", line 3, in <module>
    import asyncio
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\__init__.py", line 8, in <module>
    from .base_events import *
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\base_events.py", line 45, in <module>       
    from . import staggered
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\staggered.py", line 9, in <module>
    from . import locks
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\locks.py", line 219, in <module>
    class Condition(_ContextManagerMixin, mixins._LoopBoundMixin):
    ...<129 lines>...
            self.notify(len(self._waiters))
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\locks.py", line 219, in Condition
    class Condition(_ContextManagerMixin, mixins._LoopBoundMixin):
