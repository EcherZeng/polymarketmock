 > [strategyfrontend build 6/6] RUN npm run build:
1.747
1.747 > strategyfrontend@0.0.0 build
1.747 > tsc -b && vite build
1.747
15.46 src/components/ReturnDistributionChart.tsx(127,15): error TS2322: Type '(value: number, name: string) => [string, string] | [number, string]' is not assignable to type 'Formatter<ValueType, NameType> & ((value: ValueType, name: NameType, item: TooltipPayloadEntry, index: number, payload: TooltipPayload) => ReactNode | [...])'.
15.46   Type '(value: number, name: string) => [string, string] | [number, string]' is not assignable to type 'Formatter<ValueType, NameType>'.
15.46     Types of parameters 'value' and 'value' are incompatible.
15.46       Type 'ValueType | undefined' is not assignable to type 'number'.
15.46         Type 'undefined' is not assignable to type 'number'.
16.90 npm notice
16.90 npm notice New major version of npm available! 10.8.2 -> 11.12.1
16.90 npm notice Changelog: https://github.com/npm/cli/releases/tag/v11.12.1
16.90 npm notice To update run: npm install -g npm@11.12.1
16.90 npm notice
------
[+] up 0/4
 ⠙ Image polymarketmock-frontend         Building                                                                  18.6s
 ⠙ Image polymarketmock-strategyfrontend Building                                                                  18.6s
 ⠙ Image polymarketmock-backend          Building                                                                  18.6s
 ⠙ Image polymarketmock-strategy         Building                                                                  18.6s
Dockerfile:8

--------------------

   6 |     RUN npm ci

   7 |     COPY . .

   8 | >>> RUN npm run build

   9 |

  10 |     # ── Stage 2: nginx serve ─────────────────────────────────────────────────────

--------------------

target strategyfrontend: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2