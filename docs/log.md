 => [backend] resolving provenance for metadata file                                                               0.0s
 => ERROR [strategyfrontend build 6/6] RUN npm run build                                                          16.9s
 => [frontend] resolving provenance for metadata file                                                              0.0s
 => CANCELED [strategy builder 5/5] RUN pip install --no-cache-dir --upgrade pip  && pip install --no-cache-dir -  7.9s
------
 > [strategyfrontend build 6/6] RUN npm run build:
2.047
2.047 > strategyfrontend@0.0.0 build
2.047 > tsc -b && vite build
2.047
14.93 src/components/AnchorBulletin.tsx(128,9): error TS6133: 'getLabel' is declared but its value is never read.
------
[+] up 0/4
 ⠙ Image polymarketmock-strategy         Building                                                                  19.9s
 ⠙ Image polymarketmock-frontend         Building                                                                  19.9s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  19.9s
 ⠙ Image polymarketmock-backend          Building                                                                  19.9s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2
