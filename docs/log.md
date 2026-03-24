Request URL
http://localhost:5173/api/markets/1689303
Request Method
GET
Status Code
200 OK

{
    "id": "1689303",
    "question": "Bitcoin Up or Down - March 24, 2:35AM-2:40AM ET",
    "conditionId": "0xeb8d50cefcb367c18d701a405db7e20426e2065580231a8cfa1b40fc453caf49",
    "slug": "btc-updown-5m-1774334100",
    "resolutionSource": "https://data.chain.link/streams/btc-usd",
    "endDate": "2026-03-24T06:40:00Z",
    "startDate": "2026-03-23T06:43:17.317045Z",
    "image": "https://polymarket-upload.s3.us-east-2.amazonaws.com/BTC+fullsize.png",
    "icon": "https://polymarket-upload.s3.us-east-2.amazonaws.com/BTC+fullsize.png",
    "description": "This market will resolve to \"Up\" if the Bitcoin price at the end of the time range specified in the title is greater than or equal to the price at the beginning of that range. Otherwise, it will resolve to \"Down\".\nThe resolution source for this market is information from Chainlink, specifically the BTC/USD data stream available at https://data.chain.link/streams/btc-usd.\nPlease note that this market is about the price according to Chainlink data stream BTC/USD, not according to other sources or spot markets.",
    "outcomes": "[\"Up\", \"Down\"]",
    "outcomePrices": "[\"1\", \"0\"]",
    "volume": "147043.20902699974",
    "active": true,
    "closed": true,
    "marketMakerAddress": "",
    "createdAt": "2026-03-23T06:42:07.4836Z",
    "updatedAt": "2026-03-24T06:49:29.967248Z",
    "closedTime": "2026-03-24 06:40:23+00",
    "new": false,
    "featured": false,
    "archived": false,
    "restricted": true,
    "groupItemThreshold": "0",
    "questionID": "0xa039e15852152cfd2b4fe9213af289928e47751171dc2453c92d70005ddc5021",
    "umaEndDate": "2026-03-24T06:40:23Z",
    "enableOrderBook": true,
    "orderPriceMinTickSize": 0.001,
    "orderMinSize": 5,
    "umaResolutionStatus": "resolved",
    "volumeNum": 147043.20902699974,
    "endDateIso": "2026-03-24",
    "startDateIso": "2026-03-23",
    "hasReviewedDates": true,
    "volume24hr": 147043.20902699992,
    "volume1wk": 147043.20902699992,
    "volume1mo": 147043.20902699992,
    "volume1yr": 147043.20902699992,
    "clobTokenIds": "[\"76113456775305083620588924844077855692564580220877311373887058720584900078128\", \"34812490117597092926676691594130607461359451376213032675677765803451137597140\"]",
    "volume24hrClob": 147043.20902699992,
    "volume1wkClob": 147043.20902699992,
    "volume1moClob": 147043.20902699992,
    "volume1yrClob": 147043.20902699992,
    "volumeClob": 147043.20902699974,
    "makerBaseFee": 1000,
    "takerBaseFee": 1000,
    "acceptingOrders": false,
    "negRisk": false,
    "ready": false,
    "funded": false,
    "acceptingOrdersTimestamp": "2026-03-23T06:42:11Z",
    "cyom": false,
    "pagerDutyNotificationEnabled": false,
    "approved": true,
    "rewardsMinSize": 50,
    "rewardsMaxSpread": 4.5,
    "spread": 0.01,
    "automaticallyResolved": true,
    "lastTradePrice": 0.999,
    "bestBid": 0.99,
    "bestAsk": 1,
    "automaticallyActive": true,
    "clearBookOnStart": false,
    "showGmpSeries": false,
    "showGmpOutcome": false,
    "manualActivation": false,
    "negRiskOther": false,
    "umaResolutionStatuses": "[]",
    "pendingDeployment": false,
    "deploying": false,
    "rfqEnabled": false,
    "eventStartTime": "2026-03-24T06:35:00Z",
    "holdingRewardsEnabled": false,
    "feesEnabled": true,
    "requiresTranslation": false,
    "makerRebatesFeeShareBps": 10000,
    "feeType": "crypto_fees",
    "feeSchedule": {
        "exponent": 2,
        "rate": 0.25,
        "takerOnly": true,
        "rebateRate": 0.2
    }
}






--------------------

Request URL
http://localhost:5173/api/orderbook?token_id=%5B%2276113456775305083620588924844077855692564580220877311373887058720584900078128%22
Request Method
GET
Status Code
502 Bad Gateway

Request URL
http://localhost:5173/api/midpoint?token_id=%5B%2276113456775305083620588924844077855692564580220877311373887058720584900078128%22
Request Method
GET
Status Code
502 Bad Gateway