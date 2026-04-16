ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:27,440 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775446200 completed: return=0.00% in 0.2s
2026-04-16 08:23:27,503 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775440800 completed: return=0.00% in 0.2s
2026-04-16 08:23:27,562 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775439900 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775441700/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775442600/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:27,667 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775449800 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775439000/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775438100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
INFO:     172.18.0.6:40726 - "GET /tasks HTTP/1.1" 200 OK
2026-04-16 08:23:28,048 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775441700 completed: return=0.00% in 0.3s
2026-04-16 08:23:28,097 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775439000 completed: return=0.00% in 0.3s
2026-04-16 08:23:28,127 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775442600 completed: return=0.00% in 0.3s
2026-04-16 08:23:28,168 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775438100 completed: return=0.00% in 0.2s
2026-04-16 08:23:28,277 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775436300000&endTime=1775437200000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,280 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775435400000&endTime=1775436300000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,285 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775432700000&endTime=1775433600000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,286 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775437200000&endTime=1775438100000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,288 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775433600000&endTime=1775434500000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,294 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775434500000&endTime=1775435400000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,298 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775431800000&endTime=1775432700000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,303 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775430000000&endTime=1775430900000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,308 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775428200000&endTime=1775429100000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,311 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775426400000&endTime=1775427300000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,314 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775430900000&endTime=1775431800000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,318 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775425500000&endTime=1775426400000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,322 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775427300000&endTime=1775428200000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,326 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775423700000&endTime=1775424600000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,329 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775429100000&endTime=1775430000000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,334 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775422800000&endTime=1775423700000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,338 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775421900000&endTime=1775422800000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,340 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775421000000&endTime=1775421900000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,343 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775420100000&endTime=1775421000000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:28,344 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775424600000&endTime=1775425500000&limit=1000 "HTTP/1.1 200 OK"
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775436300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775435400/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775432700/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775437200/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
INFO:     172.18.0.6:40730 - "GET /tasks/bc968f6e7f3c HTTP/1.1" 200 OK
2026-04-16 08:23:28,837 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775436300 completed: return=0.00% in 0.3s
2026-04-16 08:23:28,864 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775435400 completed: return=0.00% in 0.3s
2026-04-16 08:23:28,894 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775432700 completed: return=0.00% in 0.3s
2026-04-16 08:23:28,923 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775437200 completed: return=0.00% in 0.3s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775433600/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775431800/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775430000/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775434500/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:29,415 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775433600 completed: return=0.00% in 0.2s
2026-04-16 08:23:29,473 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775431800 completed: return=0.00% in 0.2s
2026-04-16 08:23:29,500 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775430000 completed: return=0.00% in 0.2s
2026-04-16 08:23:29,531 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775434500 completed: return=0.00% in 0.3s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775428200/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775430900/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775426400/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775425500/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:29,934 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775428200 completed: return=0.00% in 0.2s
2026-04-16 08:23:30,035 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775430900 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775427300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:30,067 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775425500 completed: return=0.00% in 0.2s
2026-04-16 08:23:30,095 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775426400 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775423700/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775429100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775422800/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:30,423 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775427300 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775421900/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:30,544 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775423700 completed: return=0.00% in 0.2s
2026-04-16 08:23:30,602 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775429100 completed: return=0.00% in 0.2s
2026-04-16 08:23:30,626 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775422800 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775421000/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775420100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775424600/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
INFO:     172.18.0.6:40742 - "GET /tasks/bc968f6e7f3c HTTP/1.1" 200 OK
2026-04-16 08:23:31,034 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775421900 completed: return=0.00% in 0.3s
INFO:     172.18.0.6:40756 - "GET /tasks HTTP/1.1" 200 OK
2026-04-16 08:23:31,087 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775420100 completed: return=0.00% in 0.2s
2026-04-16 08:23:31,116 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775421000 completed: return=0.00% in 0.2s
2026-04-16 08:23:31,140 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775424600 completed: return=0.00% in 0.2s
2026-04-16 08:23:31,257 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775419200000&endTime=1775420100000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,263 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775418300000&endTime=1775419200000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,264 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775415600000&endTime=1775416500000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,273 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775416500000&endTime=1775417400000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,274 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775412900000&endTime=1775413800000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,281 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775417400000&endTime=1775418300000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,287 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775413800000&endTime=1775414700000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,292 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775411100000&endTime=1775412000000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,295 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775409300000&endTime=1775410200000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,301 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775407500000&endTime=1775408400000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,305 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775412000000&endTime=1775412900000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,309 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775410200000&endTime=1775411100000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,317 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775406600000&endTime=1775407500000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,321 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775405700000&endTime=1775406600000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,324 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775408400000&endTime=1775409300000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,325 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775414700000&endTime=1775415600000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,329 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775403900000&endTime=1775404800000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,334 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775402100000&endTime=1775403000000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,336 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775403000000&endTime=1775403900000&limit=1000 "HTTP/1.1 200 OK"
2026-04-16 08:23:31,337 httpx INFO HTTP Request: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1775404800000&endTime=1775405700000&limit=1000 "HTTP/1.1 200 OK"
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775419200/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775415600/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775416500/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775418300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:31,792 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775416500 completed: return=0.00% in 0.2s
2026-04-16 08:23:31,821 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775418300 completed: return=0.00% in 0.2s
2026-04-16 08:23:31,849 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775415600 completed: return=0.00% in 0.2s
2026-04-16 08:23:31,876 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775419200 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775412900/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775417400/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775413800/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775411100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:23:32,273 core.batch_runner INFO Batch bc968f6e7f3c slug btc-updown-15m-1775412900 completed: return=0.00% in 0.2s
INFO:     172.18.0.6:40760 - "POST /tasks/bc968f6e7f3c/cancel HTTP/1.1" 200 OK
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1775409300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
INFO:     172.18.0.6:40768 - "GET /tasks/bc968f6e7f3c HTTP/1.1" 200 OK
INFO:     172.18.0.6:40774 - "GET /tasks HTTP/1.1" 200 OK
INFO:     172.18.0.6:40778 - "POST /results-cleanup/by-batch/bc968f6e7f3c HTTP/1.1" 200 OK
INFO:     172.18.0.6:40788 - "GET /tasks HTTP/1.1" 200 OK
INFO:     172.18.0.6:41530 - "GET /tasks HTTP/1.1" 200 OK
INFO:     172.18.0.6:41540 - "GET /strategies HTTP/1.1" 200 OK
INFO:     172.18.0.6:41556 - "GET /portfolios HTTP/1.1" 200 OK
INFO:     172.18.0.6:41568 - "GET /data/tracked HTTP/1.1" 200 OK
INFO:     172.18.0.6:41570 - "GET /data/archives HTTP/1.1" 200 OK
INFO:     172.18.0.6:41584 - "GET /tasks/bc968f6e7f3c HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:50350 - "GET /health HTTP/1.1" 200 OK
INFO:     172.18.0.6:53114 - "GET /tasks/bc968f6e7f3c HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:56602 - "GET /results/898e7b0575b0 HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:56604 - "GET /results/898e7b0575b0/btc-klines HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:56618 - "GET /results/898e7b0575b0 HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:56634 - "GET /results/898e7b0575b0/btc-klines HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:56646 - "GET /tasks/bc968f6e7f3c HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:56652 - "GET /tasks/bc968f6e7f3c HTTP/1.1" 404 Not Found
2026-04-16 08:24:16,301 core.registry INFO Renamed preset: 0.89 0.0012 -lei -> 0.89 0.0015 -lei
INFO:     172.18.0.6:58752 - "PATCH /presets/0.89%200.0012%20-lei/rename HTTP/1.1" 200 OK
INFO:     172.18.0.6:58764 - "GET /strategies HTTP/1.1" 200 OK
INFO:     127.0.0.1:46744 - "GET /health HTTP/1.1" 200 OK
INFO:     172.18.0.6:58780 - "GET /results/898e7b0575b0 HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:58796 - "GET /results/898e7b0575b0/btc-klines HTTP/1.1" 404 Not Found
2026-04-16 08:24:24,797 core.registry INFO Saved preset: 0.89 0.0015 -lei
INFO:     172.18.0.6:58808 - "PUT /presets/0.89%200.0015%20-lei HTTP/1.1" 200 OK
INFO:     172.18.0.6:58818 - "GET /strategies HTTP/1.1" 200 OK
INFO:     172.18.0.6:58834 - "GET /tasks/f499484ec83d HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:57262 - "GET /tasks/f499484ec83d HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:57276 - "GET /tasks/f499484ec83d HTTP/1.1" 404 Not Found
INFO:     172.18.0.6:57278 - "POST /batch HTTP/1.1" 200 OK
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776141000/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776138300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776140100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776139200/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:30,584 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776141000 completed: return=0.00% in 0.2s
2026-04-16 08:24:30,644 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776138300 completed: return=0.00% in 0.2s
2026-04-16 08:24:30,670 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776139200 completed: return=0.00% in 0.2s
INFO:     172.18.0.6:57290 - "GET /tasks/f17bf2eae552 HTTP/1.1" 200 OK
2026-04-16 08:24:30,727 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776140100 completed: return=0.00% in 0.3s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776137400/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776136500/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776135600/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776134700/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:31,098 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776137400 completed: return=0.00% in 0.2s
2026-04-16 08:24:31,195 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776134700 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776133800/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:31,282 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776136500 completed: return=0.00% in 0.3s
2026-04-16 08:24:31,318 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776135600 completed: return=0.00% in 0.3s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776132900/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776132000/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776131100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:31,608 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776133800 completed: return=0.00% in 0.2s
2026-04-16 08:24:31,737 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776132900 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776130200/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776129300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:31,900 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776131100 completed: return=0.00% in 0.3s
2026-04-16 08:24:31,942 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776132000 completed: return=0.00% in 0.3s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776128400/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776127500/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:32,172 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776130200 completed: return=0.00% in 0.3s
2026-04-16 08:24:32,298 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776129300 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776126600/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776125700/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:32,489 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776127500 completed: return=0.00% in 0.2s
2026-04-16 08:24:32,521 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776128400 completed: return=0.00% in 0.2s
INFO:     172.18.0.6:57296 - "GET /tasks/f499484ec83d HTTP/1.1" 404 Not Found
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776124800/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776123900/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:32,713 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776126600 completed: return=0.00% in 0.2s
2026-04-16 08:24:32,884 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776125700 completed: return=0.00% in 0.2s
INFO:     172.18.0.6:57302 - "GET /tasks/f17bf2eae552 HTTP/1.1" 200 OK
2026-04-16 08:24:32,973 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776124800 completed: return=0.00% in 0.2s
2026-04-16 08:24:33,078 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776123900 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776123000/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776120300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776121200/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776122100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:33,755 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776123000 completed: return=0.00% in 0.2s
2026-04-16 08:24:33,792 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776121200 completed: return=-0.02% in 0.2s
2026-04-16 08:24:33,812 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776120300 completed: return=0.00% in 0.2s
2026-04-16 08:24:33,839 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776122100 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776118500/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776117600/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776119400/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776116700/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:34,359 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776118500 completed: return=0.00% in 0.2s
2026-04-16 08:24:34,410 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776119400 completed: return=0.00% in 0.2s
2026-04-16 08:24:34,440 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776117600 completed: return=0.00% in 0.3s
2026-04-16 08:24:34,480 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776116700 completed: return=0.00% in 0.3s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776115800/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776114900/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776114000/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776113100/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:34,888 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776115800 completed: return=0.00% in 0.2s
2026-04-16 08:24:34,931 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776114900 completed: return=0.00% in 0.2s
2026-04-16 08:24:34,972 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776114000 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776112200/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
2026-04-16 08:24:35,028 core.batch_runner INFO Batch f17bf2eae552 slug btc-updown-15m-1776113100 completed: return=0.00% in 0.2s
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776111300/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776110400/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'
WARNING:core.data_loader:Failed to read /app/data/sessions/btc-updown-15m-1776109500/archive/ob_deltas.parquet: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No module named 'pytz'