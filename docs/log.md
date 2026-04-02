 => [strategyfrontend build 6/6] RUN npm run build                                                                     9.0s
 => => # > strategyfrontend@0.0.0 build                                                                                 
 => => # > tsc -b && vite build                                                                                         
 => [strategy stage-1  7/10] COPY core/ core/                                                                          0.2s
[+] Building 12.0s (54/56)
 => [internal] load local bake definitions                                                                         0.0s
 => => reading from stdin 1.95kB                                                                                   0.0s0
 => [frontend internal] load build definition from Dockerfile                                                      0.0s
 => => transferring dockerfile: 717B                                                                               0.0s0
 => [strategyfrontend internal] load build definition from Dockerfile                                              0.0s
 => => transferring dockerfile: 717B                                                                               0.0s0
 => [backend internal] load build definition from Dockerfile                                                       0.1s
 => => transferring dockerfile: 1.23kB                                                                             0.0s0
 => [strategy internal] load build definition from Dockerfile                                                      0.0s
 => => transferring dockerfile: 1.09kB                                                                             0.0s0
 => [backend internal] load metadata for docker.io/library/python:3.11-slim                                        1.0s
 => [strategyfrontend internal] load metadata for docker.io/library/nginx:alpine                                   1.0s0
 => [frontend internal] load metadata for docker.io/library/node:20-alpine                                         1.0s
 => [frontend internal] load .dockerignore                                                                         0.0s0
 => => transferring context: 110B                                                                                  0.0s
 => [strategyfrontend internal] load .dockerignore                                                                 0.0s0
 => => transferring context: 110B                                                                                  0.0s
 => [strategyfrontend internal] load build context                                                                 0.0s0
 => => transferring context: 37.38kB                                                                               0.0s
 => [frontend build 1/6] FROM docker.io/library/node:20-alpine@sha256:f598378b5240225e6beab68fa9f356db1fb8efe5517  0.1s0
 => => resolve docker.io/library/node:20-alpine@sha256:f598378b5240225e6beab68fa9f356db1fb8efe55173e6d4d8153113bb  0.1s
 => [strategyfrontend stage-1 1/3] FROM docker.io/library/nginx:alpine@sha256:e7257f1ef28ba17cf7c248cb8ccf6f0c6e0  0.1s0
 => => resolve docker.io/library/nginx:alpine@sha256:e7257f1ef28ba17cf7c248cb8ccf6f0c6e0228ab9c315c152f9c203cd34c  0.1s
 => [frontend internal] load build context                                                                         0.0s0
 => => transferring context: 3.01kB                                                                                0.0s
 => [strategy internal] load .dockerignore                                                                         0.0s0
 => => transferring context: 146B                                                                                  0.0s
 => [backend internal] load .dockerignore                                                                          0.0s
 => => transferring context: 289B                                                                                  0.0s
 => [backend internal] load build context                                                                          0.0s
 => => transferring context: 1.61kB                                                                                0.0s
 => [backend builder 1/5] FROM docker.io/library/python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5da  0.1s
 => => resolve docker.io/library/python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb  0.0s
 => [strategy internal] load build context                                                                         0.0s
 => => transferring context: 48.23kB                                                                               0.0s
 => CACHED [frontend build 2/6] WORKDIR /app                                                                       0.0s
 => CACHED [strategyfrontend build 3/6] COPY package.json package-lock.json ./                                     0.0s
 => CACHED [strategyfrontend build 4/6] RUN npm ci                                                                 0.0s
 => [strategyfrontend build 5/6] COPY . .                                                                          0.1s
 => CACHED [frontend build 3/6] COPY package.json package-lock.json ./                                             0.0s
 => CACHED [frontend build 4/6] RUN npm ci                                                                         0.0s
 => CACHED [frontend build 5/6] COPY . .                                                                           0.0s
 => CACHED [frontend build 6/6] RUN npm run build                                                                  0.0s
 => CACHED [frontend stage-1 2/3] COPY --from=build /app/dist /usr/share/nginx/html                                0.0s
 => CACHED [frontend stage-1 3/3] COPY nginx.conf /etc/nginx/conf.d/default.conf                                   0.0s
 => [frontend] exporting to image                                                                                  0.3s
 => => exporting layers                                                                                            0.0s
 => => exporting manifest sha256:fd355e10bc1a98233ad7443883f912cc12402c9db01debbe895f54f14160b23f                  0.0s
 => => exporting config sha256:8ef1ec902dc4eaba0aa58e8facdf4b02b23f9d950eb97f86834106816b91a363                    0.0s
 => => exporting attestation manifest sha256:d57bce0c5491b1bbbcbf36ffc2c7390aaf5ab2cc6ef4892b24afac6c763a0e58      0.1s
 => => exporting manifest list sha256:c9a9b5aebfa86c7bcd297736e29d9a35687860b5c16d8c89f52db971b8bed607             0.0s
 => => naming to docker.io/library/polymarketmock-frontend:latest                                                  0.0s
 => => unpacking to docker.io/library/polymarketmock-frontend:latest                                               0.0s
 => CACHED [strategy builder 2/5] WORKDIR /app                                                                     0.0s
 => CACHED [backend builder 3/5] COPY pyproject.toml .                                                             0.0s
 => CACHED [backend builder 4/5] RUN python -m venv /opt/venv                                                      0.0s
 => CACHED [backend builder 5/5] RUN pip install --no-cache-dir --upgrade pip  && pip install --no-cache-dir .     0.0s
 => CACHED [backend stage-1 3/5] COPY --from=builder /opt/venv /opt/venv                                           0.0s
 => CACHED [backend stage-1 4/5] COPY app/ app/                                                                    0.0s
 => CACHED [backend stage-1 5/5] RUN mkdir -p /app/data/sessions /app/data/logs                                    0.0s
 => CACHED [strategy builder 3/5] COPY requirements.txt .                                                          0.0s
 => CACHED [strategy builder 4/5] RUN python -m venv /opt/venv                                                     0.0s
 => CACHED [strategy builder 5/5] RUN pip install --no-cache-dir --upgrade pip  && pip install --no-cache-dir -r   0.0s
 => CACHED [strategy stage-1  3/10] COPY --from=builder /opt/venv /opt/venv                                        0.0s
 => CACHED [strategy stage-1  4/10] COPY config.py .                                                               0.0s
 => CACHED [strategy stage-1  5/10] COPY main.py .                                                                 0.0s
 => [strategy stage-1  6/10] COPY strategy_presets.json .                                                          0.1s
 => [backend] exporting to image                                                                                   0.2s
 => => exporting layers                                                                                            0.0s
 => => exporting manifest sha256:2148517cfcaa49e6c60c2df4bcfa355e440cb7db175f94bf972b4c3211966613                  0.0s
 => => exporting config sha256:941a79779425fd679359dc07743c760bd2819f5537ce7be2164b70df8c3f4db5                    0.0s
 => => exporting attestation manifest sha256:77cd64ef6d907beeeb9a4dfbc3b1923b4c8d362f5c42d382cabee9b1448b8704      0.1s
 => => exporting manifest list sha256:6744288d76eadf8e2d019d842bd7739ad81458483275d9e0520a952a99a9ecff             0.0s
 => => naming to docker.io/library/polymarketmock-backend:latest                                                   0.0s
 => => unpacking to docker.io/library/polymarketmock-backend:latest                                                0.0s
 => ERROR [strategyfrontend build 6/6] RUN npm run build                                                          10.3s
 => [strategy stage-1  7/10] COPY core/ core/                                                                      0.2s
 => [strategy stage-1  8/10] COPY api/ api/                                                                        0.1s
 => [strategy stage-1  9/10] COPY strategies/ strategies/                                                          0.1s
 => [strategy stage-1 10/10] RUN mkdir -p /app/results                                                             0.4s
 => [frontend] resolving provenance for metadata file                                                              0.0s
 => [backend] resolving provenance for metadata file                                                               0.0s
 => [strategy] exporting to image                                                                                  0.5s
 => => exporting layers                                                                                            0.2s
 => => exporting manifest sha256:556571aa362626ba215007b80b86a56cf0521b324c16dc7a63699923b86d2c3f                  0.0s
 => => exporting config sha256:b4a0dc4b4068b70bf9090af2b15cf66359c2665c7cea80377abbe976cec18d32                    0.0s
 => => exporting attestation manifest sha256:69ef8bee7e04dfa01d4734ff1d8619cde647b0a78c164e6b7e142725120d7321      0.0s
 => => exporting manifest list sha256:ab2d954c25e6bc15981725d82913cfc14c1cfce7e5aaf10f5df57a56f35c474d             0.0s
 => => naming to docker.io/library/polymarketmock-strategy:latest                                                  0.0s
 => => unpacking to docker.io/library/polymarketmock-strategy:latest                                               0.1s
 => [strategy] resolving provenance for metadata file                                                              0.0s
------
 > [strategyfrontend build 6/6] RUN npm run build:
1.636
1.636 > strategyfrontend@0.0.0 build
1.636 > tsc -b && vite build
1.636
9.034 src/pages/DataCleanupPage.tsx(5,15): error TS6196: 'IncompleteItem' is declared but never used.
------
[+] up 0/4
 ⠙ Image polymarketmock-backend          Building                                                                  12.2s
 ⠙ Image polymarketmock-strategy         Building                                                                  12.2s
 ⠙ Image polymarketmock-frontend         Building                                                                  12.2s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  12.2s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2
