# Source Deep Dive: Coinbase Advanced Trade

## Role in SuperAjan12

Coinbase is primarily a spot/reference market-data source for SuperAjan12. It is not the primary futures execution venue in the MVP. Its most valuable role is to validate crypto prices against Binance and OKX and provide an additional regulated-market reference.

## Official surfaces

Docs:

- https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-overview
- https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-channels
- https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/products/get-best-bid-ask

## MVP usage

Read/reference market data:

- spot price reference
- best bid/ask where access is available
- ticker stream where available
- product metadata
- level2/orderbook stream where available
- market-trades stream where available

## Not MVP

- live order placement
- account endpoints
- user-specific channels
- portfolio data

## Reliability requirements

Coinbase connector must include:

- configured/authenticated vs not-configured state
- public/private channel distinction
- stale-data detection
- source health status
- timestamp normalization
- retry and timeout policy

Each normalized snapshot must include:

- product id
- source
- captured_at
- exchange timestamp if present
- bid/ask/last where available
- stale flag
- raw payload hash

## Known risks

- Some Advanced Trade endpoints require authorization.
- Public WebSocket and REST behavior must be verified in the runtime environment.
- Product naming differs from futures venues.
- Coinbase is mostly spot/reference for this project, not the main futures trading venue.

## UI requirements

Coinbase panel must show:

- product id
- last/reference price
- bid/ask if available
- spread
- source health
- configured/not-configured status
- comparison vs Binance and OKX

## Decision policy

Coinbase should be used as a reference and validation source. If Coinbase reference price diverges materially from Binance/OKX, crypto-related confidence should drop and the Risk Engine may block actions until the discrepancy is resolved.
