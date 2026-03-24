PS C:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\backend> uvicorn app.main:app --reload --host 0.0.0.0 --port 8071
INFO:     Will watch for changes in these directories: ['C:\\Users\\v-yujieceng\\Documents\\Ls\\poly\\polymarketmock\\backend']
INFO:     Uvicorn running on http://0.0.0.0:8071 (Press CTRL+C to quit)
INFO:     Started reloader process [28752] using WatchFiles
Process SpawnProcess-1:
Traceback (most recent call last):
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\multiprocessing\process.py", line 313, in _bootstrap
    self.run()
    ~~~~~~~~^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\multiprocessing\process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\site-packages\uvicorn\_subprocess.py", line 80, in subprocess_started
    target(sockets=sockets)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\site-packages\uvicorn\server.py", line 75, in run
    return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\runners.py", line 195, in run
    return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\asyncio\base_events.py", line 725, in run_until_complete       
    return future.result()
           ~~~~~~~~~~~~~^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\site-packages\uvicorn\server.py", line 79, in serve
    await self._serve(sockets)
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\site-packages\uvicorn\server.py", line 86, in _serve
    config.load()
    ~~~~~~~~~~~^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\site-packages\uvicorn\config.py", line 441, in load
    self.loaded_app = import_from_string(self.app)
                      ~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\site-packages\uvicorn\importer.py", line 22, in import_from_string
    raise exc from None
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\site-packages\uvicorn\importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
  File "C:\Users\v-yujieceng\AppData\Local\Programs\Python\Python313\Lib\importlib\__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1023, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "C:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\backend\app\main.py", line 6, in <module>
    from app.routers import account, backtest, markets, trading
  File "C:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\backend\app\routers\backtest.py", line 8, in <module>
    from app.services.backtest_engine import get_backtest_markets, run_backtest
  File "C:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\backend\app\services\backtest_engine.py", line 8, in <module>
    from app.storage.duckdb_store import list_available_markets, query_orderbooks, query_prices
  File "C:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\backend\app\storage\duckdb_store.py", line 9, in <module>
    import duckdb
ModuleNotFoundError: No module named 'duckdb'