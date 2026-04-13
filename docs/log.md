 => [strategy stage-1  7/10] COPY core/ core/                                                                      0.3s
 => [backend] exporting to image                                                                                   0.4s
 => => exporting layers                                                                                            0.0s
 => => exporting manifest sha256:658b4837782e877c46d509597e8dcea09030ed615ba92c60cc5593bc2da944a5                  0.0s
 => => exporting config sha256:43025d622fc1637e9448fc8a07ef61d114c579369e700876f70cd1dd0861dac5                    0.0s
 => => exporting attestation manifest sha256:24a246ec94c5277cb8c8417482a681e840619a3d8883f989c60adb00e1b8d3f6      0.2s
 => => exporting manifest list sha256:9cdac531193ccf79f8d119ececc76df5b6b651103183f49ad2e8cee88b39230d             0.0s
 => => naming to docker.io/library/polymarketmock-backend:latest                                                   0.0s
 => => unpacking to docker.io/library/polymarketmock-backend:latest                                                0.0s
 => ERROR [strategyfrontend build 6/6] RUN npm run build                                                          14.0s
 => [strategy stage-1  8/10] COPY api/ api/                                                                        0.1s
 => [strategy stage-1  9/10] COPY strategies/ strategies/                                                          0.1s
 => [strategy stage-1 10/10] RUN mkdir -p /app/results                                                             0.5s
 => [frontend] resolving provenance for metadata file                                                              0.0s
 => [backend] resolving provenance for metadata file                                                               0.0s
 => [strategy] exporting to image                                                                                  0.4s
 => => exporting layers                                                                                            0.2s
 => => exporting manifest sha256:1023695c31c163b75e0681193bde5c6681fbec9b5ea0b638a77af13313233d74                  0.0s
 => => exporting config sha256:243ce24a0358b2585ee38350c427959db0dfd9740111450b67a82307e6d4f602                    0.0s
 => => exporting attestation manifest sha256:b79d95b756b5669b4472b454885fe908042cbcf2385e55e3d36af7d512b21c3e      0.0s
 => => exporting manifest list sha256:31bf5c3c5d806f6042ae85f1c07139a1ae4955967f766b40c1cdb214f9048a11             0.0s
 => => naming to docker.io/library/polymarketmock-strategy:latest                                                  0.0s
 => => unpacking to docker.io/library/polymarketmock-strategy:latest                                               0.1s
 => [strategy] resolving provenance for metadata file                                                              0.0s
------
 > [strategyfrontend build 6/6] RUN npm run build:
1.575
1.575 > strategyfrontend@0.0.0 build
1.575 > tsc -b && vite build
1.575
12.80 src/pages/ResultsCleanupPage.tsx(12,53): error TS6196: 'BatchStatItem' is declared but never used.
------
[+] up 0/4
 ⠙ Image polymarketmock-frontend         Building                                                                  16.5s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  16.5s
 ⠙ Image polymarketmock-backend          Building                                                                  16.5s
 ⠙ Image polymarketmock-strategy         Building                                                                  16.5s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2

root@vmi3187329:~/poly/polymarketmock#