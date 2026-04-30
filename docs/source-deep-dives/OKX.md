# Source Deep Dive: OKX

## Role in SuperAjan12

OKX is a secondary futures/market-data source and an important cross-check against Binance. It can provide public market data, ticker data, orderbook data, trades, candles and derivatives-related market information depending on endpoint/channel.

## Official surfaces

Docs:

- https://www.okx.com/docs-v5/en
- https://www.okx.com/docs-v5/trick_en

## MVP usage

Read-only market intelligence:

- ticker
- best bid/ask
- orderbook snapshot
- trades
- candles
- funding/open interest if available for selected instruments
- source health and latency comparison against Binance

## Not MVP

- authenticated trading
- account information
- order placement
- private WebSocket channels

## Reliability requirements

OKX connector must include:

- timeout and retry policy
- source health state
- stale-data detection
- endpoint/channel capability flags
- instrument mapping table
- rate-limit observation
- circuit breaker for repeated source failures

Each normalized snapshot must include:

- source
- instrument id
- endpoint/channel
- captured_at
- exchange timestamp if present
- stale flag
- normalized price fields
- raw payload hash

## Known risks

- Some high-speed data channels may require login or specific account tiers.
- Instrument naming differs from Binance and Coinbase.
- Funding/open-interest endpoints require product-type awareness.
- REST snapshots and WebSocket streams need separate freshness policies.
- Source latency and update frequency may differ by endpoint.

## UI requirements

OKX panel must show:

- instrument
- last price
- bid/ask
- spread
- 24h volume
- funding/open interest where available
- latency
- stale/offline status
- comparison vs Binance and Coinbase reference

## Decision policy

OKX is a validation and market-intelligence source. If Binance and OKX diverge beyond threshold, the system must lower confidence or block crypto/futures-related actions until the discrepancy is understood.
