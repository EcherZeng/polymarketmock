 => ERROR [strategyfrontend build 6/6] RUN npm run build                                                          12.0s
 => [strategy] exporting to image                                                                                  0.4s
 => => exporting layers                                                                                            0.2s
 => => exporting manifest sha256:e36d18644f332c6e42e7f2fe5d28a779c049ee08e3446533a1183ad6abcecc47                  0.0s
 => => exporting config sha256:91ce9cbff3d924a144addd9cc0bb7979cbce6b30fed1c84cbcffce59b3b8416d                    0.0s
 => => exporting attestation manifest sha256:6062188ab0d2f7ae86b7612e28c2b42c8dabb91499b06b1f1e5c04586bb0d7d3      0.0s
 => => exporting manifest list sha256:439f5e1445f1ad90a89821ceba99e2bf19b74b7e43b44f2199a90a2a9387bb1d             0.0s
 => => naming to docker.io/library/polymarketmock-strategy:latest                                                  0.0s
 => => unpacking to docker.io/library/polymarketmock-strategy:latest                                               0.1s
 => [frontend] resolving provenance for metadata file                                                              0.0s
 => [strategy] resolving provenance for metadata file                                                              0.0s
------
 > [strategyfrontend build 6/6] RUN npm run build:
0.671
0.671 > strategyfrontend@0.0.0 build
0.671 > tsc -b && vite build
0.671
10.88 src/pages/AiOptimizePage.tsx(138,50): error TS2345: Argument of type 'string | string[]' is not assignable to parameter of type 'string'.
10.88   Type 'string[]' is not assignable to type 'string'.
10.88 src/pages/AiOptimizePage.tsx(186,50): error TS2345: Argument of type 'string | string[]' is not assignable to parameter of type 'string'.
10.88   Type 'string[]' is not assignable to type 'string'.
10.88 src/pages/AiOptimizePage.tsx(219,51): error TS2345: Argument of type 'string | string[]' is not assignable to parameter of type 'string'.
10.88   Type 'string[]' is not assignable to type 'string'.
------
[+] up 0/4
 ⠙ Image polymarketmock-frontend         Building                                                                  14.2s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  14.2s
 ⠙ Image polymarketmock-backend          Building                                                                  14.2s
 ⠙ Image polymarketmock-strategy         Building                                                                  14.2s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2
