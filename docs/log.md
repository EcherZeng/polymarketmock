****刚启动服务时
root@vmi3187329:~/poly/polymarketmock# docker stats --no-stream
CONTAINER ID   NAME                                CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O        PIDS
13b3ac869c92   polymarketmock-strategyfrontend-1   0.00%     6.297MiB / 11.68GiB   0.05%     101kB / 100kB     0B / 8.19kB      7
40c4fccde887   polymarketmock-strategy-1           0.43%     187.7MiB / 11.68GiB   1.57%     4.95kB / 95.5kB   16.4kB / 0B      13
af1154e94497   polymarketmock-frontend-1           0.00%     6.086MiB / 11.68GiB   0.05%     1.37kB / 126B     0B / 8.19kB      7
91efaebd8ef8   polymarketmock-backend-1            1.22%     66.59MiB / 11.68GiB   0.56%     183kB / 230kB     0B / 0B          16
520f3c425e06   polymarketmock-redis-1              0.72%     12.93MiB / 11.68GiB   0.11%     87.9GB / 87.5GB   29.7GB / 128GB   8
****准备开始批量测试任务前
root@vmi3187329:~/poly/polymarketmock# docker stats --no-stream
CONTAINER ID   NAME                                CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O        PIDS
13b3ac869c92   polymarketmock-strategyfrontend-1   0.00%     6.32MiB / 11.68GiB    0.05%     123kB / 122kB     0B / 8.19kB      7
40c4fccde887   polymarketmock-strategy-1           419.46%   549.3MiB / 11.68GiB   4.59%     139kB / 138kB     15.6MB / 102kB   86
af1154e94497   polymarketmock-frontend-1           0.00%     6.086MiB / 11.68GiB   0.05%     1.41kB / 126B     0B / 8.19kB      7
91efaebd8ef8   polymarketmock-backend-1            16.14%    66.6MiB / 11.68GiB    0.56%     193kB / 239kB     0B / 0B          16
520f3c425e06   polymarketmock-redis-1              0.61%     12.93MiB / 11.68GiB   0.11%     87.9GB / 87.5GB   29.7GB / 128GB   8
****批量任务结束后
root@vmi3187329:~/poly/polymarketmock# docker stats --no-stream
CONTAINER ID   NAME                                CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O         PIDS
13b3ac869c92   polymarketmock-strategyfrontend-1   0.00%     6.316MiB / 11.68GiB   0.05%     278kB / 278kB     0B / 8.19kB       7
40c4fccde887   polymarketmock-strategy-1           0.31%     2.973GiB / 11.68GiB   25.46%    718kB / 415kB     87.3MB / 90.8MB   415
af1154e94497   polymarketmock-frontend-1           0.00%     6.086MiB / 11.68GiB   0.05%     1.41kB / 126B     0B / 8.19kB       7
91efaebd8ef8   polymarketmock-backend-1            0.42%     66.6MiB / 11.68GiB    0.56%     216kB / 265kB     0B / 0B           16
520f3c425e06   polymarketmock-redis-1              0.77%     12.93MiB / 11.68GiB   0.11%     87.9GB / 87.5GB   29.7GB / 128GB    8
root@vmi3187329:~/poly/polymarketmock#
****新开另一批量任务结束后
root@vmi3187329:~/poly/polymarketmock# docker stats --no-stream
CONTAINER ID   NAME                                CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O        PIDS
13b3ac869c92   polymarketmock-strategyfrontend-1   0.00%     6.512MiB / 11.68GiB   0.05%     1.33MB / 1.34MB   0B / 8.19kB      7
40c4fccde887   polymarketmock-strategy-1           0.29%     8.884GiB / 11.68GiB   76.06%    2.25MB / 1.73MB   704MB / 510MB    1247
af1154e94497   polymarketmock-frontend-1           0.00%     6.086MiB / 11.68GiB   0.05%     1.48kB / 126B     0B / 8.19kB      7
91efaebd8ef8   polymarketmock-backend-1            78.37%    66.63MiB / 11.68GiB   0.56%     287kB / 344kB     2.59MB / 0B      16
520f3c425e06   polymarketmock-redis-1              0.63%     12.91MiB / 11.68GiB   0.11%     87.9GB / 87.5GB   29.7GB / 128GB   8
root@vmi3187329:~/poly/polymarketmock#