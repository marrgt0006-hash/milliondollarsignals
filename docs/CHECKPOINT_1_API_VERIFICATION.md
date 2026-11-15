# Polybot — Checkpoint 1: Documentation and API Verification

**Status:** Documentation review prepared; implementation has not started.  
**Date:** 2026-11-15  
**Repository:** https://github.com/marrgt0006-hash/milliondollarsignals  
**Default branch:** `main`

## Scope and architecture decisions

Polybot is one integrated, read-only BTC five-minute signal terminal. The single `run.py` process owns the live runtime lifecycle: market discovery, exchange WebSocket ingestion, candle/feature state, signal generation, immutable prediction records, settlement reconciliation, scoreboard updates, and dashboard serving.

There is no standalone collector, no `collector.py`, no second collection process, no trading/account/order API use, and no requirement to pre-collect a set number of markets. In-process prediction recordkeeping is part of the running application. When the process stops, ingestion and signal generation stop; committed SQLite prediction history remains.

Signal eligibility must fail closed. It requires valid live data, correct market identity, feed freshness, causal timestamps, and at least 30 minutes of valid volatility observations. Missing calibration history must be reported; the engine must not fabricate history. Strategy disagreement or missing required inputs produces NO CALL. Exactly one immutable locked decision is permitted per market window.

## Official documentation reviewed

### Polymarket US — read-only public market data

- Documentation home: https://docs.polymarket.us/
- API introduction: https://docs.polymarket.us/api-reference/introduction
- Public gateway: `https://gateway.polymarket.us`
- Market list: `GET /v1/markets`
- Market BBO: `GET /v1/markets/{slug}/bbo`
- Market book: `GET /v1/markets/{slug}/book`
- Market settlement: `GET /v1/markets/{slug}/settlement`
- Price history: `GET /v1/price-history`
- Crypto FAQ: https://docs.polymarket.us/faqs/crypto-faqs
- Asset-price history: `GET /v1/asset-prices/history`

The Retail public gateway is documented as no-key read access for market, event, series, order-book, BBO, settlement, and historical price information. The API listing schema includes structured `assetPriceTerms` fields (asset symbol/class, market type, window start/end, priceToBeat, settlementPrice), plus market identifier, slug, bid/ask quotes, feeCoefficient, volume, and market status.

Polymarket US documentation describes BRTI crypto Up/Down products at 15-minute and 60-minute horizons (along with other crypto market families) in its September 21, 2026 changelog entry. Its FAQ describes the Up/Down settlement statistic as the simple average of 60 one-second index prices from 59 seconds before the settlement instant through that instant; equality settles Up. Missing settlement-minute index observations defer settlement rather than settling on partial data.

**Critical unresolved requirement:** The requested five-minute BTC instrument was not found documented as a Polymarket US product. Five-minute BTC Up/Down markets were found on Polymarket International, but they use Chainlink BTC/USD 60-second TWAP and are a different venue. Those instruments must not be substituted or labeled as Polymarket US. Before proceeding, the public US market list must be runtime-queried and an exact five-minute BTC US market (if any) must be verified by structured fields and rules. If none exists, implementation must stop at the documented blocker rather than silently switch venues or durations.

### Coinbase market data

Official Coinbase Exchange WebSocket documentation:
- https://help.coinbase.com/en/developer-platform/websocket-feeds/exchange
- Production public endpoint: `wss://ws-feed.exchange.coinbase.com`
- Heartbeat, ticker, Level-2, Level-2 batch, and matches channels are documented.
- Heartbeat provides per-second product liveness; Level-2 supplies bid/ask side, price and size; matches supplies trade events.

Coinbase Advanced Trade WebSocket documentation:
- https://help.coinbase.com/en/developer-platform/websocket-feeds/advanced-trade
- Market-data channels include ticker, ticker batch, Level-2, and status.

The live connection, protocol handshake, subscription, BTC-USD feed availability, and reconnection behavior have **not** been runtime-tested in this checkpoint.

### BRTI reference and licensing

- Official index page: https://www.cfbenchmarks.com/data/indices/BRTI
- Official documentation index: https://www.cfbenchmarks.com/documentation/indices

CF Benchmarks describes BRTI as a Bitcoin real-time benchmark and notes licensing requirements for use/distribution of index data in products and services. Polybot must not scrape the public webpage or treat displayed public values as an unrestricted licensed feed. The safest settlement-grade outcome source for the target exchange is the official market settlement endpoint and the exchange's market rules. Any use of a licensed live BRTI feed requires licensing/permission to be independently confirmed.

### Fee schedule

- Official notice: https://www.polymarketexchange.com/files/notices/Exchange%20Notice%20-%20Weekly%20Notification%20%282026.09.21%29.pdf
- Published formula: `Fee = Theta * C * p * (1-p)`
- September 17, 2026 standard taker coefficient amendment: `Theta = 0.0695`
- October 13 amendment changed table-tennis-specific coefficient only; it did not amend the coefficient for other straight trades.
- The market response exposes `feeCoefficient`; runtime calculation must use the actual target market's field and the current applicable official schedule, not an unverified constant.

## Five-minute market and settlement distinction

Public web search found examples of Polymarket International `BTC Up or Down 5m` markets. Their listed resolution source is Chainlink BTC/USD TWAP 60-second stream. These do not establish that the same instrument exists on Polymarket US. Polymarket US's documented crypto-market family and settlement method differ.

Therefore market discovery must be a strict typed validation, not a slug guess:
1. Query only the official Polymarket US public gateway.
2. Identify BTC via structured asset fields (not title matching alone).
3. Require exact five-minute window duration from verified structured start/end values.
4. Require Up/Down market type and explicit direction/outcome mapping.
5. Read market rules and settlement source; require the requested settlement definition.
6. Verify active/current status, BBO/book availability, fee coefficient, and settlement endpoint.
7. Otherwise set market status to BLOCKED and display NO CALL.

## Implementation constraints carried forward

- One process only: `run.py`.
- No collector script/service/process or external trading process.
- Read-only market data only; do not call order, account, balance, portfolio, or authenticated private endpoints.
- The Polymarket US market data WebSocket in docs requires API-key authentication, so do not assume it is a public unauthenticated socket. The public REST gateway is documented for no-key market data; live streaming availability must be validated before selection.
- Coinbase market-data WebSocket is a separate feed and is not the Polymarket settlement oracle.
- Build candles from received observations only; retain exchange and receive timestamps; reject out-of-order/future/stale records.
- Require 30 minutes of valid volatility observations before issuing an actionable call.
- No fabricated candles, backfilled synthetic history, or fabricated calibration.
- Save prediction snapshots and hash-chain records in SQLite as part of the live process.
- Lock one call per market window using a database uniqueness constraint and transactional insert.
- Grade only against verified final settlement; unresolved or incomplete settlement stays pending.
- Hypothetical five-share grading must be explicitly labeled hypothetical and include verified fees only when applicable.
- Walk-forward evaluation and benchmarks must use time-ordered splits and leakage-safe features.
- No trading execution, no orders, no account access, no secrets.

## Checkpoint 1 completion report

| Item | Status |
|---|---|
| Empty repository and permissions inspected | Verified |
| Polymarket US public REST docs | Verified |
| Polymarket US market/order-book/settlement endpoint references | Verified |
| Coinbase public WebSocket docs | Verified |
| BRTI methodology and licensing caveat | Verified |
| Official fee amendment | Verified |
| Exact five-minute BTC Polymarket US market | **Not verified — blocker** |
| Live endpoint connectivity | Not runtime-tested |
| Strategy A/B/C definitions from original prompt | Not present in repository/context available for this checkpoint |
| Original full dashboard panel list and five checkpoint acceptance tests | Not present in repository/context available for this checkpoint |

**No application code has been implemented. No test results are claimed. No live data process has been started.**

## Approval gate

Checkpoint 2 must not begin until the user explicitly approves Checkpoint 1. Before Checkpoint 2, resolve the instrument/venue mismatch. Do not move to Polymarket International or change settlement source without explicit authorization.
