 => ERROR [strategyfrontend build 6/6] RUN npm run build                                                          12.0s
 => [strategy stage-1  6/10] COPY strategy_presets.json .                                                          0.0s
 => [strategy stage-1  7/10] COPY core/ core/                                                                      0.1s
 => [strategy stage-1  8/10] COPY api/ api/                                                                        0.0s
 => [strategy stage-1  9/10] COPY strategies/ strategies/                                                          0.0s
 => [strategy stage-1 10/10] RUN mkdir -p /app/results                                                             0.4s
 => [frontend] resolving provenance for metadata file                                                              0.0s
 => [backend] resolving provenance for metadata file                                                               0.0s
 => [strategy] exporting to image                                                                                  0.4s
 => => exporting layers                                                                                            0.2s
 => => exporting manifest sha256:dd41dbdfe4885f29af57308394a2cccf51b253cba7df82833334c4a385efeb02                  0.0s
 => => exporting config sha256:84a9e588f645c24fa06869a601a24650368c76bb430734016191043d26f23dcf                    0.0s
 => => exporting attestation manifest sha256:534beeeba0a827f52e2f0fc03897c067b598a616105121287d9f9b06d1d94858      0.0s
 => => exporting manifest list sha256:5fb44f9d444dc832b26e8d69c8e824032d667f3f632b914fe219ffb71cea85d1             0.0s
 => => naming to docker.io/library/polymarketmock-strategy:latest                                                  0.0s
 => => unpacking to docker.io/library/polymarketmock-strategy:latest                                               0.1s
 => [strategy] resolving provenance for metadata file                                                              0.0s
------
 > [strategyfrontend build 6/6] RUN npm run build:
1.282
1.282 > strategyfrontend@0.0.0 build
1.282 > tsc -b && vite build
1.282
10.87 src/pages/ResultDetailPage.tsx(4,49): error TS6196: 'BtcTrendInfo' is declared but never used.
------
[+] up 0/4
 ⠙ Image polymarketmock-strategy         Building                                                                  13.9s
 ⠙ Image polymarketmock-frontend         Building                                                                  13.9s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  13.9s
 ⠙ Image polymarketmock-backend          Building                                                                  13.9s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2
