root@vmi3187329:~/poly/polymarketmock# docker ps
CONTAINER ID   IMAGE                             COMMAND                  CREATED         STATUS                            PORTS                                                 NAMES
b367f8fec186   polymarketmock-strategyfrontend   "/docker-entrypoint.…"   3 minutes ago   Up 3 minutes                      80/tcp, 0.0.0.0:3022->3022/tcp, [::]:3022->3022/tcp   polymarketmock-strategyfrontend-1
660a0837558b   polymarketmock-strategy           "uvicorn api.app:app…"   3 minutes ago   Up 3 seconds (health: starting)   0.0.0.0:8072->8072/tcp, [::]:8072->8072/tcp           polymarketmock-strategy-1
b90abbef7a0e   polymarketmock-frontend           "/docker-entrypoint.…"   3 minutes ago   Up 3 minutes                      80/tcp, 0.0.0.0:3021->3021/tcp, [::]:3021->3021/tcp   polymarketmock-frontend-1
ca7397112461   polymarketmock-backend            "uvicorn app.main:ap…"   3 minutes ago   Up 3 minutes (healthy)            0.0.0.0:8071->8071/tcp, [::]:8071->8071/tcp           polymarketmock-backend-1
520f3c425e06   redis:7-alpine                    "docker-entrypoint.s…"   7 days ago      Up 5 days (healthy)               0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp           polymarketmock-redis-1
root@vmi3187329:~/poly/polymarketmock# docker logs 660a0837558b
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:02:48,176 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:02:48,181 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:02:48,181 core.registry INFO Registered preset: Test1
2026-04-15 05:02:48,181 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:02:48,181 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:02:48,181 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:03:16,522 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:03:16,527 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:03:16,527 core.registry INFO Registered preset: Test1
2026-04-15 05:03:16,527 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:03:16,528 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:03:16,528 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:03:44,211 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:03:44,216 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:03:44,217 core.registry INFO Registered preset: Test1
2026-04-15 05:03:44,217 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:03:44,217 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:03:44,217 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:04:11,754 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:04:11,760 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:04:11,760 core.registry INFO Registered preset: Test1
2026-04-15 05:04:11,760 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:04:11,760 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:04:11,761 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:04:36,895 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:04:36,900 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:04:36,900 core.registry INFO Registered preset: Test1
2026-04-15 05:04:36,900 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:04:36,900 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:04:36,900 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:04:58,626 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:04:58,629 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:04:58,629 core.registry INFO Registered preset: Test1
2026-04-15 05:04:58,629 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:04:58,629 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:04:58,629 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:05:20,674 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:05:20,678 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:05:20,679 core.registry INFO Registered preset: Test1
2026-04-15 05:05:20,679 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:05:20,679 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:05:20,679 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:05:48,611 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:05:48,617 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:05:48,617 core.registry INFO Registered preset: Test1
2026-04-15 05:05:48,617 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:05:48,617 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:05:48,617 api.app INFO Loaded 3 strategies
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-15 05:06:16,991 core.data_scanner INFO Loaded token map: 1462 entries
2026-04-15 05:06:16,997 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-15 05:06:16,997 core.registry INFO Registered preset: Test1
2026-04-15 05:06:16,997 core.registry INFO Registered preset: 0.89入 θ 为0.002-4.13下午
2026-04-15 05:06:16,997 core.registry INFO Registered preset: 0.89入 0.002 , 0.02利润
2026-04-15 05:06:16,997 api.app INFO Loaded 3 strategies