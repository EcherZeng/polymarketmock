root@vmi3187329:~/poly/polymarketmock# docker stats --no-stream
CONTAINER ID   NAME                                CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O         PIDS
d25a30583644   polymarketmock-strategyfrontend-1   0.00%     6.516MiB / 11.68GiB   0.05%     705kB / 1.11MB    1.28MB / 8.19kB   7
99287a5b0999   polymarketmock-strategy-1           409.04%   2.303GiB / 11.68GiB   19.72%    1.09MB / 940kB    461MB / 115MB     175
9d85db13bb59   polymarketmock-frontend-1           0.00%     6.012MiB / 11.68GiB   0.05%     1.48kB / 126B     0B / 8.19kB       7
6111ac14468c   polymarketmock-backend-1            4.20%     66.78MiB / 11.68GiB   0.56%     299kB / 349kB     61.4kB / 0B       16
520f3c425e06   polymarketmock-redis-1              0.72%     13.28MiB / 11.68GiB   0.11%     87.9GB / 87.5GB   29.7GB / 128GB    8