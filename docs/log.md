Traceback (most recent call last):
  File "/app/core/batch_runner.py", line 275, in run_one
    session = await asyncio.wait_for(
              ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/asyncio/tasks.py", line 489, in wait_for
    return fut.result()
           ^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/asyncio/threads.py", line 25, in to_thread
    return await loop.run_in_executor(None, func_call)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/concurrent/futures/thread.py", line 58, in run
    result = self.fn(*self.args, **self.kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/core/runner.py", line 168, in run_backtest
    if param_active(merged_config, "btc_trend_enabled") and merged_config.get("btc_trend_enabled"):
                    ^^^^^^^^^^^^^
UnboundLocalError: cannot access local variable 'merged_config' where it is not associated with a value