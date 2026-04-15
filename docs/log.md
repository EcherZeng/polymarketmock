[plugin:vite:oxc] Transform failed with 3 errors:

[PARSE_ERROR] Error: Identifier `mean` has already been declared
    ╭─[ src/components/ReturnDistributionChart.tsx:30:9 ]
    │
 30 │   const mean = pctReturns.reduce((a, b) => a + b, 0) / pctReturns.length
    │         ──┬─  
    │           ╰─── `mean` has already been declared here
    │ 
 45 │   const mean = pctReturns.reduce((a, b) => a + b, 0) / pctReturns.length
    │         ──┬─  
    │           ╰─── It can not be redeclared here
────╯

[PARSE_ERROR] Error: Identifier `variance` has already been declared
    ╭─[ src/components/ReturnDistributionChart.tsx:31:9 ]
    │
 31 │   const variance = pctReturns.length > 1
    │         ────┬───  
    │             ╰───── `variance` has already been declared here
    │ 
 46 │   const variance = pctReturns.reduce((a, x) => a + (x - mean) ** 2, 0) / pctReturns.length
    │         ────┬───  
    │             ╰───── It can not be redeclared here
────╯

[PARSE_ERROR] Error: Identifier `std` has already been declared
    ╭─[ src/components/ReturnDistributionChart.tsx:34:9 ]
    │
 34 │   const std = Math.sqrt(variance)
    │         ─┬─  
    │          ╰─── `std` has already been declared here
    │ 
 47 │   const std = Math.sqrt(variance)
    │         ─┬─  
    │          ╰─── It can not be redeclared here
────╯
C:/Users/v-yujieceng/Documents/Ls/poly/polymarketmock/Strategyfrontend/src/components/ReturnDistributionChart.tsx
    at transformWithOxc (file:///C:/Users/v-yujieceng/Documents/Ls/poly/polymarketmock/Strategyfrontend/node_modules/vite/dist/node/chunks/node.js:3720:19)
    at TransformPluginContext.transform (file:///C:/Users/v-yujieceng/Documents/Ls/poly/polymarketmock/Strategyfrontend/node_modules/vite/dist/node/chunks/node.js:3788:26)
    at EnvironmentPluginContainer.transform (file:///C:/Users/v-yujieceng/Documents/Ls/poly/polymarketmock/Strategyfrontend/node_modules/vite/dist/node/chunks/node.js:30048:51)
    at async loadAndTransform (file:///C:/Users/v-yujieceng/Documents/Ls/poly/polymarketmock/Strategyfrontend/node_modules/vite/dist/node/chunks/node.js:24177:26)
    at async viteTransformMiddleware (file:///C:/Users/v-yujieceng/Documents/Ls/poly/polymarketmock/Strategyfrontend/node_modules/vite/dist/node/chunks/node.js:24986:20)
Click outside, press Esc key, or fix the code to dismiss.
You can also disable this overlay by setting server.hmr.overlay to false in vite.config.ts.