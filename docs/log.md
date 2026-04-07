root@vmi3187329:~/poly/polymarketmock# docker logs 17868e4ba30d
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-04-07 05:50:40,307 core.data_scanner INFO Loaded token map: 1292 entries
2026-04-07 05:50:40,312 core.registry INFO Loaded strategy class: unified (unified_strategy.py)
2026-04-07 05:50:40,313 core.registry INFO Registered preset: solid_core
2026-04-07 05:50:40,313 core.registry INFO Registered preset: main_force
2026-04-07 05:50:40,313 core.registry INFO Registered preset: high_freq_coverage
2026-04-07 05:50:40,313 core.registry INFO Registered preset: Test预设
2026-04-07 05:50:40,313 api.app INFO Loaded 4 strategies
2026-04-07 05:50:51,152 api.result_store INFO Loaded 1079 persisted results from /app/results
2026-04-07 05:50:51,182 api.result_store INFO Loaded 49 persisted batches from /app/results/batches
2026-04-07 05:50:51,183 api.result_store INFO Loaded 3 persisted portfolios from /app/results/portfolios
2026-04-07 05:50:51,184 api.app INFO LLM API key configured (model: deepseek-chat)
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8072 (Press CTRL+C to quit)
INFO:     172.18.0.6:52606 - "GET /strategies HTTP/1.1" 200 OK
INFO:     172.18.0.6:52612 - "GET /presets HTTP/1.1" 200 OK
INFO:     172.18.0.6:52620 - "GET /portfolios HTTP/1.1" 200 OK
INFO:     172.18.0.6:52626 - "GET /data/archives HTTP/1.1" 200 OK
INFO:     172.18.0.6:52630 - "GET /data/tracked HTTP/1.1" 200 OK
2026-04-07 05:52:23,477 core.registry INFO Saved preset: Test预设
INFO:     172.18.0.6:49334 - "PUT /presets/Test%E9%A2%84%E8%AE%BE HTTP/1.1" 200 OK
INFO:     172.18.0.6:49342 - "GET /strategies HTTP/1.1" 200 OK
INFO:     172.18.0.6:49344 - "GET /presets HTTP/1.1" 200 OK
2026-04-07 05:52:46,073 core.registry INFO Saved preset: 0.89入场
INFO:     172.18.0.6:52554 - "PUT /presets/0.89%E5%85%A5%E5%9C%BA HTTP/1.1" 200 OK
INFO:     172.18.0.6:52564 - "GET /strategies HTTP/1.1" 200 OK
INFO:     172.18.0.6:52574 - "GET /presets HTTP/1.1" 200 OK
INFO:     172.18.0.6:35032 - "GET /strategies HTTP/1.1" 200 OK
INFO:     172.18.0.6:35036 - "GET /presets HTTP/1.1" 200 OK
INFO:     172.18.0.6:35046 - "GET /ai-optimize/models HTTP/1.1" 200 OK
INFO:     172.18.0.6:35056 - "GET /ai-optimize HTTP/1.1" 200 OK
INFO:     172.18.0.6:35066 - "GET /portfolios HTTP/1.1" 200 OK
INFO:     172.18.0.6:35076 - "GET /ai-optimize HTTP/1.1" 200 OK
INFO:     172.18.0.6:35090 - "GET /ai-optimize HTTP/1.1" 200 OK
INFO:     172.18.0.6:35106 - "GET /ai-optimize HTTP/1.1" 200 OK
INFO:     172.18.0.6:42876 - "POST /ai-optimize HTTP/1.1" 200 OK
INFO:     172.18.0.6:42888 - "GET /ai-optimize HTTP/1.1" 200 OK
INFO:     172.18.0.6:42898 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
INFO:     172.18.0.6:42914 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:05,949 core.data_loader INFO Loaded archive btc-updown-15m-1775199600: 330 prices, 726 orderbooks, 236164 deltas, 3616 trades
INFO:     172.18.0.6:42924 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:09,828 core.data_loader INFO Loaded archive btc-updown-15m-1775188800: 314 prices, 668 orderbooks, 171998 deltas, 2366 trades
INFO:     172.18.0.6:50378 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
INFO:     172.18.0.6:50390 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:14,469 core.data_loader INFO Loaded archive btc-updown-15m-1775186100: 320 prices, 688 orderbooks, 210624 deltas, 2678 trades
INFO:     172.18.0.6:50396 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:18,935 core.data_loader INFO Loaded archive btc-updown-15m-1775185200: 304 prices, 648 orderbooks, 188715 deltas, 2439 trades
INFO:     172.18.0.6:57386 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:23,933 core.data_loader INFO Loaded archive btc-updown-15m-1775182500: 293 prices, 647 orderbooks, 209683 deltas, 2341 trades
INFO:     172.18.0.6:57388 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:28,268 core.data_loader INFO Loaded archive btc-updown-15m-1775177100: 316 prices, 648 orderbooks, 192712 deltas, 2066 trades
INFO:     172.18.0.6:59206 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:32,270 core.data_loader INFO Loaded archive btc-updown-15m-1775175300: 326 prices, 696 orderbooks, 180292 deltas, 2605 trades
INFO:     172.18.0.6:59218 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:35,943 core.data_loader INFO Loaded archive btc-updown-15m-1775172600: 318 prices, 654 orderbooks, 168132 deltas, 2168 trades
INFO:     172.18.0.6:59222 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
INFO:     172.18.0.6:48346 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:53:40,668 core.data_loader INFO Loaded archive btc-updown-15m-1775171700: 330 prices, 736 orderbooks, 202480 deltas, 3093 trades
2026-04-07 05:53:45,514 core.data_loader INFO Loaded archive btc-updown-15m-1775170800: 328 prices, 728 orderbooks, 207946 deltas, 3286 trades
2026-04-07 05:53:50,900 core.data_loader INFO Loaded archive btc-updown-15m-1775168100: 322 prices, 706 orderbooks, 240172 deltas, 3529 trades
2026-04-07 05:53:55,050 core.data_loader INFO Loaded archive btc-updown-15m-1775164500: 322 prices, 724 orderbooks, 184084 deltas, 3058 trades
2026-04-07 05:54:02,257 core.data_loader INFO Loaded archive btc-updown-15m-1775159100: 328 prices, 696 orderbooks, 306730 deltas, 3142 trades
INFO:     172.18.0.6:43992 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:54:10,702 core.data_loader INFO Loaded archive btc-updown-15m-1775152800: 336 prices, 726 orderbooks, 360180 deltas, 3494 trades
INFO:     172.18.0.6:44004 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:54:16,722 core.data_loader INFO Loaded archive btc-updown-15m-1775149200: 322 prices, 680 orderbooks, 293772 deltas, 2836 trades
INFO:     172.18.0.6:44014 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
INFO:     172.18.0.6:49608 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
INFO:     172.18.0.6:49622 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:54:25,311 core.data_loader INFO Loaded archive btc-updown-15m-1775146500: 336 prices, 728 orderbooks, 398904 deltas, 3613 trades
2026-04-07 05:54:26,804 core.data_loader INFO Loaded archive btc-updown-15m-1775284200: 302 prices, 604 orderbooks, 74174 deltas, 2530 trades
INFO:     172.18.0.6:49632 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:54:28,919 core.data_loader INFO Loaded archive btc-updown-15m-1775280600: 304 prices, 612 orderbooks, 84200 deltas, 1912 trades
INFO:     172.18.0.6:54802 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:54:30,679 core.data_loader INFO Loaded archive btc-updown-15m-1775275200: 290 prices, 584 orderbooks, 78430 deltas, 1920 trades
2026-04-07 05:54:33,255 core.data_loader INFO Loaded archive btc-updown-15m-1775270700: 312 prices, 640 orderbooks, 92760 deltas, 2780 trades
INFO:     172.18.0.6:54814 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
2026-04-07 05:54:35,985 core.data_loader INFO Loaded archive btc-updown-15m-1775269800: 315 prices, 646 orderbooks, 116418 deltas, 2804 trades
2026-04-07 05:54:39,497 core.data_loader INFO Loaded archive btc-updown-15m-1775245500: 306 prices, 652 orderbooks, 138684 deltas, 2312 trades
2026-04-07 05:54:43,844 core.data_loader INFO Loaded archive btc-updown-15m-1775242800: 320 prices, 668 orderbooks, 161400 deltas, 2747 trades
2026-04-07 05:54:47,701 core.data_loader INFO Loaded archive btc-updown-15m-1775235600: 320 prices, 680 orderbooks, 158504 deltas, 2849 trades
2026-04-07 05:54:55,022 core.data_loader INFO Loaded archive btc-updown-15m-1775228400: 330 prices, 702 orderbooks, 297130 deltas, 3051 trades
2026-04-07 05:54:55,348 httpx INFO HTTP Request: POST https://api.deepseek.com/v1/chat/completions "HTTP/1.1 401 Unauthorized"
2026-04-07 05:54:55,350 core.ai_optimizer ERROR AI optimizer e7001b3e5338 round 1 LLM call failed: Client error '401 Unauthorized' for url 'https://api.deepseek.com/v1/chat/completions'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401
INFO:     172.18.0.6:43462 - "GET /ai-optimize/e7001b3e5338 HTTP/1.1" 200 OK
root@vmi3187329:~/poly/polymarketmock#