# Source Deep Dive: Binance USD-M Futures

## Role in SuperAjan12

Binance USD-M Futures is a primary futures market-data source candidate. It is useful for high-liquidity crypto futures intelligence: mark price, index price, funding, open interest, orderbook depth, trades, candles and volatility analysis.

## Official surfaces

Docs:

- https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price
- https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest
- https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book
- https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

## MVP usage

Read-only futures intelligence:

- mark price
- index price
- last funding rate
- next funding time
- open interest
- orderbook depth
- ticker
- klines
- recent trades where useful

## Not MVP

- live order placement
- account endpoints
- leverage/margin changes
- authenticated futures trading

## Reliability requirements

Binance connector must include:

- timeout
- retry
- rate-limit awareness
- endpoint weight metadata where available
- stale-data detection
- circuit breaker
- source health state

Each snapshot must include:

- symbol
- source
- endpoint
- captured_at
- exchange timestamp if present
- raw payload hash
- normalized fields

## Known risks

- Regional/platform eligibility constraints.
- Rate limits and endpoint weights.
- WebSocket disconnects and reconnection logic.
- Funding can flip around volatile periods.
- Open interest can be interpreted incorrectly without price context.
- Orderbook snapshots must be synchronized carefully if later combined with WebSocket deltas.

## UI requirements

Binance Futures panel must show:

- symbol
- mark price
- index price
- funding rate
- next funding time
- open interest
- 24h volume
- spread
- orderbook depth
- volatility
- source health
- latency/staleness

## Decision policy

Binance futures data can feed market intelligence and paper/shadow strategies. It must not directly create live orders. Risk Engine must account for liquidation distance, funding, spread/slippage and data freshness before any future execution path.
