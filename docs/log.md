=> ERROR [strategyfrontend build 6/6] RUN npm run build                                                              13.2s
 => [backend] resolving provenance for metadata file                                                                   0.1s
 => [frontend] resolving provenance for metadata file                                                                  0.1s
 => [strategy] resolving provenance for metadata file                                                                  0.0s
------
 > [strategyfrontend build 6/6] RUN npm run build:
2.169
2.169 > strategyfrontend@0.0.0 build
2.169 > tsc -b && vite build
2.169
12.06 src/pages/AiOptimizeDetailPage.tsx(22,7): error TS6133: 'metricLabels' is declared but its value is never read.
12.06 src/pages/AiOptimizeDetailPage.tsx(32,10): error TS6133: 'formatMetric' is declared but its value is never read.
13.12 npm notice
13.12 npm notice New major version of npm available! 10.8.2 -> 11.12.1
13.12 npm notice Changelog: https://github.com/npm/cli/releases/tag/v11.12.1
13.12 npm notice To update run: npm install -g npm@11.12.1
13.12 npm notice
------
[+] up 0/4
 ⠙ Image polymarketmock-backend          Building                                                                      14.9s
 ⠙ Image polymarketmock-strategy         Building                                                                      14.9s
 ⠙ Image polymarketmock-frontend         Building                                                                      14.9s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                      14.9s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2
