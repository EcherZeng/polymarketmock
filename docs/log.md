 => => naming to docker.io/library/polymarketmock-frontend:latest                                                  0.0s
 => => unpacking to docker.io/library/polymarketmock-frontend:latest                                               0.0s
 => ERROR [tradefrontend build 6/6] RUN npm run build                                                             10.7s
 => [frontend] resolving provenance for metadata file                                                              0.0s
 => [strategyfrontend] resolving provenance for metadata file                                                      0.0s
------
 > [tradefrontend build 6/6] RUN npm run build:
0.852
0.852 > tradefrontend@0.0.0 build
0.852 > tsc -b && vite build
0.852
9.226 src/hooks/useLiveWs.ts(120,17): error TS6133: '_snapshots' is declared but its value is never read.
------
[+] up 0/6
 ⠙ Image polymarketmock-strategy         Building                                                                  12.6s
 ⠙ Image polymarketmock-frontend         Building                                                                  12.6s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  12.6s
 ⠙ Image polymarketmock-trade            Building                                                                  12.6s
 ⠙ Image polymarketmock-tradefrontend    Building                                                                  12.6s
 ⠙ Image polymarketmock-backend          Building                                                                  12.6s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target tradefrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2
