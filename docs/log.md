root@vmi3187329:~/poly/polymarketmock# docker logs 369ed141ee8f
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-07 05:47:11,965 core.data_scanner INFO Loaded token map: 1292 entries
2026-04-07 05:47:11,970 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-07 05:47:11,970 core.registry INFO Registered preset: solid_core
2026-04-07 05:47:11,970 core.registry INFO Registered preset: main_force
2026-04-07 05:47:11,970 core.registry INFO Registered preset: high_freq_coverage
2026-04-07 05:47:11,970 core.registry INFO Registered preset: Test预设
2026-04-07 05:47:11,971 api.app INFO Loaded 4 strategies
2026-04-07 05:47:22,493 api.result_store INFO Loaded 1079 persisted results from /app/results
2026-04-07 05:47:22,523 api.result_store INFO Loaded 49 persisted batches from /app/results/batches
2026-04-07 05:47:22,525 api.result_store INFO Loaded 3 persisted portfolios from /app/results/portfolios
2026-04-07 05:47:22,525 api.app WARNING STRATEGY_LLM_API_KEY is not set — AI optimization will fail. Set it in .env or as an environment variable.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8072 (Press CTRL+C to quit)
root@vmi3187329:~/poly/polymarketmock#