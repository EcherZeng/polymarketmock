 => ERROR [strategyfrontend build 6/6] RUN npm run build                                                          15.8s
 => [strategy] exporting to image                                                                                  0.3s
 => => exporting layers                                                                                            0.1s
 => => exporting manifest sha256:26eda87380127158a1e60f444977046cd5d157f19e03caaf2c81c00711611af6                  0.0s
 => => exporting config sha256:f6d9989c21bd864f50b1f3b0c85a65b981e64be19d9c9e1c22fbddd6eeb595e2                    0.0s
 => => exporting attestation manifest sha256:afedd5c3d0170fb634c4f5afb577005b34945ad7774c6b4a868fada20f329a97      0.0s
 => => exporting manifest list sha256:86ddb9c1d8cd3cd4982c81787fb7cadd414a0d2a6c9248fba8726b74654b1b74             0.0s
 => => naming to docker.io/library/polymarketmock-strategy:latest                                                  0.0s
 => => unpacking to docker.io/library/polymarketmock-strategy:latest                                               0.1s
 => [frontend] resolving provenance for metadata file                                                              0.0s
 => [strategy] resolving provenance for metadata file                                                              0.0s
------
 > [strategyfrontend build 6/6] RUN npm run build:
1.852
1.852 > strategyfrontend@0.0.0 build
1.852 > tsc -b && vite build
1.852
14.36 src/pages/AiOptimizeDetailPage.tsx(64,29): error TS6133: 'isLoading' is declared but its value is never read.
15.70 npm notice
15.70 npm notice New major version of npm available! 10.8.2 -> 11.12.1
15.70 npm notice Changelog: https://github.com/npm/cli/releases/tag/v11.12.1
15.70 npm notice To update run: npm install -g npm@11.12.1
15.70 npm notice
------
[+] up 0/4
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  17.9s
 ⠙ Image polymarketmock-backend          Building                                                                  17.9s
 ⠙ Image polymarketmock-strategy         Building                                                                  17.9s
 ⠙ Image polymarketmock-frontend         Building                                                                  17.9s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2