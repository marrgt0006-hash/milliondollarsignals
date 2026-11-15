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


---

# Follow-up Investigation — BTC 5-Minute on Polymarket US

**Investigated:** 2026-11-15  
**Scope:** Polymarket US only. No venue or timeframe substitution.  
**Checkpoint status:** Still Checkpoint 1. No application implementation or Checkpoint 2 work performed.

## Corrected finding

The earlier statement that a BTC 5-minute market had not been found on Polymarket US was too categorical. Further research found credible, specific evidence that BTC 5-minute Up/Down markets have in fact been listed and traded on Polymarket US, and that their settlement reference is BRTI rather than the International venue's Chainlink stream.

However, Polymarket US's own published documentation is internally inconsistent or behind the observed listings: the Crypto Schema explicitly recognizes a `5m` Up/Down horizon and says it can appear in preprod ahead of listing, while also saying only 15m and 1h are listed and production currently carries hand-listed Bitcoin markets. The Crypto FAQ likewise describes 15m and 60m Up/Down cadence. The September 21, 2026 changelog says the automated crypto families were in preprod and production rollout would be announced.

**Conclusion:** BTC 5-minute is not an invented or International-only instrument: third-party datasets and Polymarket US market-data capture evidence identify BTC 5-minute Up/Down markets on the US venue with BRTI settlement. But the official docs reviewed do not document a production 5-minute listing rollout, and the public gateway could not be queried successfully from this research environment. Therefore current active/upcoming status on November 15, 2026 is not directly confirmed from a live official API response. This is an official-documentation/live-catalog discrepancy, not proof that the product is unsupported.

## Official Polymarket US documentation evidence

1. **Public discovery API inventory:** The official API introduction identifies the no-key public gateway `https://gateway.polymarket.us` and documents public discovery through:
   - `GET /v1/markets`
   - `GET /v1/events`
   - `GET /v1/series`
   - `GET /v1/search`
   - Market-by-ID and market-by-slug lookups
   - BBO, book, settlement and price-history lookups

   Official docs: https://docs.polymarket.us/api-reference/introduction

2. **Markets list filters:** The official Get Markets page documents pagination via `limit` and `offset`, plus filters for `active`, `closed`, `archived`, `startDateMin/Max`, `endDateMin/Max`, `categories`, `marketTypes`, and `includeHidden`. The market schema includes `assetPriceTerms`, status, outcomes, market slug, fee coefficient and other market fields.

   Official docs: https://docs.polymarket.us/api-reference/markets/get-markets

3. **Events list filters:** The official Get Events page documents pagination and filters for active/closed/archived, date/time ranges, tags, series IDs, categories, market types, recurrence, and live/ended state. Event responses contain child markets with `assetPriceTerms`, market status, and metadata. Its changelog warns that after October 15, 2026, event list responses return only primary markets; a full market set requires fetching each event by ID or slug. Therefore event-list absence alone is not conclusive.

   Official docs: https://docs.polymarket.us/api-reference/events/get-events  
   Official changelog: https://docs.polymarket.us/changelog

4. **Search:** The official Search endpoint supports a query, result limit, series IDs, market type, start/closed time filters, status and page number. Search is a useful discovery route but must not replace exhaustive market/series listing and metadata inspection.

   Official docs: https://docs.polymarket.us/api-reference/search/search

5. **Series:** The official Series endpoint supports pagination, slug, active and recurrence filters. The Crypto Schema says to identify crypto markets from typed metadata rather than parsing a symbol or slug.

   Official docs: https://docs.polymarket.us/api-reference/series/get-series  
   Crypto schema: https://docs.polymarket.us/trader-guide/crypto-schema

6. **Crypto typed metadata:** The official Crypto Schema defines:
   - `crypto_market_type = updown` / Retail `assetPriceTerms.marketType = ASSET_PRICE_MARKET_TYPE_UP_DOWN`
   - `crypto_horizon` enum includes `5m`, `15m`, `1h`, `4h`
   - `crypto_asset_slug = btc`
   - `crypto_index_symbol = BRTI`
   - `interval_start` and `interval_end`
   - `price_to_beat`
   
   Critically, its horizon table says 15m and 1h are listed, while 5m and 4h follow the same pattern and can appear in preprod ahead of listing. Its series table enumerates `btc-updown-15m` and `btc-updown-1h`, and says further cadences follow the pattern `btc-updown-<horizon>`. It does not list `btc-updown-5m` as a current production series.

   Official docs: https://docs.polymarket.us/trader-guide/crypto-schema

7. **Production rollout status:** The September 21, 2026 changelog entry states that four automated Bitcoin crypto-market families were documented ahead of production listing, were in preprod at that time, and would reach production on a schedule to be announced. It specifies 15-minute and 60-minute Up/Down windows, not five-minute. The latest changelog entries through November 13, 2026 contain no located announcement explicitly promoting BTC 5m Up/Down to production. This is evidence about the published rollout record, not definitive proof that the market has never been listed.

   Official docs: https://docs.polymarket.us/changelog

8. **Other BTC market classifications:** The Crypto Schema lists four families: `updown`, `strike`, `range`, and `hit`. Above/Below, Price Range and One-Touch are not equivalent to a five-minute Up/Down contract. The schema's documented 5m horizon belongs to the `updown` family. No alternate family in the official schema defines a BTC five-minute UP/DOWN contract.

## Independent evidence of actual Polymarket US 5-minute listings

These sources are not official Polymarket documentation, so they do not override official market rules. They do provide specific observational evidence that the US venue has had 5-minute BTC Up/Down markets:

- **PMData Polymarket US historical data details:** identifies Polymarket US as a separate US exchange with its own market slugs and order books; states that its Up/Down market-data collection had gaps affecting 5-minute rounds, and specifically calls out BTC 5-minute, ETH 5-minute and BTC 15-minute as active high-coverage products. It documents collection from the Polymarket US markets WebSocket at `wss://api.polymarket.us/v1/ws/markets`, including full L2 book and trade messages. Its stated fixes are dated November 7 and November 10, 2026.

  Source: https://pmdata.dev/docs/historical-data-details/polymarket-us

- **PMData Polymarket US market catalog:** describes a daily-updated public Parquet catalog of every Polymarket US market PMData has recorded, with exchange, event slug, market slug, dates, question, outcomes, series, category and market type. This is a way to independently inspect recorded US listings, but the catalog file itself was not successfully retrieved and filtered during this investigation.

  Source: https://pmdata.dev/docs/schemas/polymarket-us/markets-catalog

- **BTC 5m US/International side-by-side capture:** a dataset card describes a read-only recording of Polymarket US and Polymarket International BTC 5-minute Up/Down order books, trades and settlements side by side on October 27, 2026. It explicitly distinguishes US settlement on CF Benchmarks BRTI from International settlement on Chainlink. The card reports actual US REST and US markets-WebSocket frames.

  Source: https://huggingface.co/datasets/bvin02/polymarket-btc-5m

These observations make the venue distinction especially clear: a BTC 5-minute US market has been captured with BRTI settlement. It is not appropriate to reject the user's requested venue based solely on the FAQ's cadence table.

## Active, upcoming, alternate classification, support status

| Question | Finding |
|---|---|
| Has BTC 5m UP/DOWN existed on Polymarket US? | **Yes, credible independent market-data captures document it.** |
| Does official schema recognize a 5m Up/Down horizon? | **Yes.** `crypto_horizon` includes `5m` for `updown`. |
| Does official documentation say 5m is a listed production cadence? | **No.** It says 15m and 1h are listed; 5m/4h can appear in preprod ahead of listing. |
| Is an active BTC 5m US window confirmed right now (2026-11-15)? | **Not directly confirmed.** Live official gateway response was not obtained in this research environment. |
| Is an upcoming BTC 5m US window confirmed? | **Not directly confirmed.** Same live catalog limitation. |
| Is there another documented family that means 5m UP/DOWN? | **No.** The matching typed family is `updown`; other families are different contracts. |
| Is 5m unsupported by Polymarket US? | **Cannot conclude unsupported.** Actual US market captures contradict a blanket unsupported conclusion. Production listing documentation remains inconsistent/stale. |

## Exact remaining verification required — without guessing

A proper runtime confirmation should use only documented Polymarket US public routes and query every relevant discovery path:

1. Page through `GET https://gateway.polymarket.us/v1/markets` using documented `limit` and `offset`; inspect active, inactive, closed, hidden and date-bounded results. Do not filter only by title or guessed slug.
2. Page through `GET /v1/series`; inspect all series, active and inactive, and search BTC crypto-related series. The series endpoint documents slug, active and recurrence filters.
3. Page through `GET /v1/events` with crypto-related categories and date ranges, then fetch full event details by ID/slug because the event list can return only primary markets.
4. Query `GET /v1/search` with Bitcoin/BTC/Up Down queries and inspect all pages/statuses.
5. For every candidate, inspect typed Retail `assetPriceTerms`: require asset class crypto, symbol BTC, market type Up/Down, and exact 300-second difference between `windowStartTime` and `windowEndTime`. Verify market/event status and explicit Yes/No direction mapping. Do not rely on the market title or slug alone.
6. Fetch the candidate's official rules, BBO, book and settlement endpoint. Require BRTI settlement terms matching the exact instrument.
7. For upcoming markets, verify future window start/end and actual tradability/listing status; do not infer upcoming from a generic series pattern.
8. Save the raw responses, request URLs, timestamps, and response hashes as evidence.

**Tool limitation in this investigation:** The official documentation pages were accessible and reviewed, but direct opening of the public API gateway URLs from this web research environment returned an access/tool error rather than a JSON response. This is not an HTTP status from Polymarket and must not be reported as an API 404 or as evidence of no market.

## Corrected project decision

Keep the required target as **Polymarket US BTC 5-minute UP/DOWN settled by the instrument's verified Polymarket US/BRTI rules**. Do not switch to International, Chainlink, 15-minute markets, or another crypto market family. Until an official live candidate is resolved and its terms verified, the signal terminal must show market-discovery status as `UNVERIFIED` / `NO CALL`, not substitute a different instrument.

No code has been changed. No Checkpoint 2 work has begun. The only action permitted by this follow-up was documentation research.


---

# Final Checkpoint 1 Live API Attempt — 2026-11-15

**Scope:** Polymarket US public API only. BTC UP/DOWN, exact 300-second duration, CF Benchmarks BRTI.  
**No code implementation, no collector, no Checkpoint 2.**

## Official API documentation and exact discovery routes

The official API introduction explicitly separates:
- Public read-only market-data API: `https://gateway.polymarket.us` (no API key).
- Authenticated trading/account API: `https://api.polymarket.us` (API key required).

Only the public gateway was used in this investigation. No authenticated endpoint was called.

Official documentation: https://docs.polymarket.us/api-reference/introduction

### 1. GET /v1/markets

Documented route:
`GET https://gateway.polymarket.us/v1/markets`

Documented query parameters include:
`limit`, `offset`, `orderBy`, `orderDirection`, `id`, `slug`, `archived`, `active`, `closed`, `startDateMin`, `startDateMax`, `endDateMin`, `endDateMax`, `categories`, `marketTypes`, `includeHidden`, and `tagIds`.

Response schema includes market `id`, `slug`, `question`, `active`, `closed`, `archived`, `marketType`, `marketSides`, `outcomes`, `status`, `assetPriceTerms`, `feeCoefficient`, `rulesDisclaimer`, and related fields.

Official docs: https://docs.polymarket.us/api-reference/markets/get-markets

**Runtime request attempted:**
`GET https://gateway.polymarket.us/v1/markets?limit=100&offset=0&active=true&closed=false&archived=false&includeHidden=true`

**Runtime result:** DNS resolution failed before an HTTP connection was established:
`urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`

HTTP status: **not received**. Content-Type: **not received**. Response body: **none**. This is not an HTTP 404 and not an empty market list.

### 2. GET /v1/events

Documented route:
`GET https://gateway.polymarket.us/v1/events`

Documented query parameters include pagination (`limit`, `offset`), status (`active`, `closed`, `archived`, `ended`, `live`), date/time windows (`startDateMin/Max`, `endDateMin/Max`, `startTimeMin/Max`, `eventDate`), `seriesId`, `categories`, `marketTypes`, `tagSlug`, `tagIds`, `recurrence`, `includeTemplate`, and `includeHidden`.

Event responses contain child `markets` with their IDs, slugs, status, market type, market sides, and asset price terms. Because event-list responses may return only primary markets, full event detail lookup is required for candidates.

Official docs: https://docs.polymarket.us/api-reference/events/get-events

**Runtime request attempted:**
`GET https://gateway.polymarket.us/v1/events?limit=100&offset=0&active=true&closed=false&archived=false&includeHidden=true&startTimeMin=2026-11-15T00:00:00Z`

**Runtime result:** DNS resolution failed before an HTTP connection was established:
`urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`

HTTP status: **not received**. Content-Type: **not received**. Response body: **none**. This is not an HTTP 404 and not an empty event list.

### 3. GET /v1/series

Documented route:
`GET https://gateway.polymarket.us/v1/series`

Documented query parameters include `limit`, `offset`, `orderBy`, `orderDirection`, `slug`, `active`, and `recurrence`. The documented response returns series IDs, slugs, titles, recurrence and active status.

Official docs: https://docs.polymarket.us/api-reference/series/get-series

**Runtime request attempted:**
`GET https://gateway.polymarket.us/v1/series?limit=100&offset=0`

**Runtime result:** DNS resolution failed before an HTTP connection was established:
`urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`

HTTP status: **not received**. Content-Type: **not received**. Response body: **none**. This is not an HTTP 404 and not an empty series list.

### 4. GET /v1/search

Documented route:
`GET https://gateway.polymarket.us/v1/search`

Documented query parameters include `query`, `limit`, `seriesIds`, `marketType`, `startTimeMin/Max`, `closedTimeMin/Max`, `status`, `page`, and `comboEnabledOnly`.

Official docs: https://docs.polymarket.us/api-reference/search/search

**Runtime request attempted:**
`GET https://gateway.polymarket.us/v1/search?query=BTC&limit=100&page=1&status=active`

**Runtime result:** DNS resolution failed before an HTTP connection was established:
`urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`

HTTP status: **not received**. Content-Type: **not received**. Response body: **none**. This is not an HTTP 404 and not an empty search result.

### 5. Market lookup by ID and slug

The official API documents:
- `GET /v1/market/id/{id}` — https://docs.polymarket.us/api-reference/markets/get-market-by-id
- `GET /v1/market/slug/{slug}` — https://docs.polymarket.us/api-reference/markets/get-market-by-slug

The market detail schema exposes the fields needed for final validation: `id`, `slug`, `status`, `marketSides`, `outcomes`, `assetPriceTerms.marketType`, `assetPriceTerms.asset.assetClass`, `assetPriceTerms.asset.symbol`, `assetPriceTerms.indexSymbol`, `assetPriceTerms.horizon`, `assetPriceTerms.windowStart`, `assetPriceTerms.windowEnd`, `assetPriceTerms.direction`, and `feeCoefficient`.

No actual candidate ID or slug was available from an official live response, so no placeholder or guessed identifier was sent to either lookup route. Both lookups remain unexecuted for that reason. The documented route formats are verified; runtime response status is not.

## Actual runtime evidence summary

The runtime test was executed from the available container environment on 2026-11-15 using Python's standard-library HTTPS client with an Accept: application/json header and a 15-second timeout. Four independent public discovery requests were attempted. All four failed at DNS name resolution for `gateway.polymarket.us`, with the same exact error `[Errno -3] Temporary failure in name resolution`.

| Route | Attempted | HTTP status | Result |
|---|---:|---|---|
| `GET /v1/markets` | Yes | None | DNS resolution failure |
| `GET /v1/events` | Yes | None | DNS resolution failure |
| `GET /v1/series` | Yes | None | DNS resolution failure |
| `GET /v1/search` | Yes | None | DNS resolution failure |
| `GET /v1/market/id/{id}` | No | None | No verified candidate ID; no guessing |
| `GET /v1/market/slug/{slug}` | No | None | No verified candidate slug; no guessing |

No response format or actual market fields were received at runtime. The documented response format is JSON, but that is documentation evidence, not an observed live response.

## Requested market verification result

| Required property | Runtime result |
|---|---|
| Live BTC 5m US market found | **Not determined** |
| Upcoming BTC 5m US market found | **Not determined** |
| Actual market ID | Not obtained |
| Actual market slug | Not obtained |
| Actual opening timestamp | Not obtained |
| Actual closing timestamp | Not obtained |
| Exact 300-second duration | Not runtime verified |
| UP/DOWN outcome mapping | Not runtime verified |
| BRTI index reference on a current candidate | Not runtime verified |
| Market-specific `feeCoefficient` | Not runtime verified |

The market schema documents the fields necessary to verify all of these, including a BTC crypto asset, UP/DOWN market type, index symbol, horizon, window timestamps, direction/outcome metadata, and fee coefficient. But no live JSON payload was obtained, so none of these candidate-specific values can be truthfully reported.

## Failure classification and remaining limitation

This was a **network/DNS failure**, not an HTTP error. No HTTP request reached the Polymarket API server, so it is impossible to classify any endpoint as returning 200, 404, 429, 5xx, or an empty collection. It would be incorrect to say that no BTC 5-minute market exists based on this run.

The current environment cannot resolve the official API hostname. A repeat from a network environment with working DNS/egress (for example the user's Mac or a GitHub Actions runner) is required to collect real response headers, status codes, and sanitized JSON evidence. If a candidate is returned, its actual ID/slug must be passed to the official detail route and its BRTI terms, 300-second timestamp delta, UP/DOWN mapping, and feeCoefficient verified from that response.

## Final checkpoint decision

The required target remains unchanged: **Polymarket US BTC UP/DOWN, exactly 300 seconds, CF Benchmarks BRTI**. No International, Chainlink, or 15-minute substitution is permitted.

**Checkpoint 1 live API investigation is blocked by DNS resolution failure in this execution environment.** Historical US listing evidence and official schema support remain documented in the earlier sections, but present active/upcoming status is not established.

No application code was written, no collector was started, and Checkpoint 2 was not started. Stop here pending user decision and/or a repeat API test from a network with DNS access.


---

# One-Time GitHub Actions API Diagnostic — 2026-11-15

**Authorization:** User explicitly authorized creation and execution of a one-time, manually triggered GitHub Actions diagnostic.  
**Workflow file:** `.github/workflows/polymarket-us-diagnostic.yml`  
**Workflow commit:** `6135c8ce7d4846783c38b394c530689c69583c1b`  
**Workflow URL:** https://github.com/marrgt0006-hash/milliondollarsignals/actions/workflows/polymarket-us-diagnostic.yml

## Workflow contents

- Trigger: `workflow_dispatch` only.
- Runner: GitHub-hosted `ubuntu-latest`.
- DNS: resolves `gateway.polymarket.us` and records resolved addresses or a classified DNS error.
- Public endpoints:
  - `GET /v1/markets?limit=100&offset=0&active=true&closed=false&archived=false&includeHidden=true`
  - `GET /v1/events?limit=100&offset=0&active=true&closed=false&archived=false&includeHidden=true`
  - `GET /v1/series?limit=100&offset=0`
  - `GET /v1/search?query=BTC&limit=100&page=1&status=active`
- Records request URL, HTTP status when received, response time, content type, classified network/HTTP result, and sanitized/truncated response body.
- Distinguishes DNS failure, connection failure, TLS failure, HTTP error, empty 2xx response, and successful response with/without candidate match.
- Scans successful JSON payloads for BTC + UP/DOWN + five-minute candidate objects and classifies match/no-match separately for each endpoint. Candidate extraction records only returned fields, including asset, market type, horizon, BRTI index symbol, timestamps, computed duration when both timestamps parse, outcomes/market sides, status and fee coefficient. Missing fields remain null.
- Discovery text matches are not treated as verification. Final verification still requires official market detail/rules/settlement evidence for BTC crypto asset, UP/DOWN family, five-minute horizon, exactly 300 seconds, BRTI reference, opening/closing timestamps, explicit outcome/token mapping and the market-specific fee coefficient.
- Uploads `diagnostics/latest/` as artifact `polymarket-us-api-diagnostic` (30-day retention).
- Commits `diagnostics/latest/` to the repository after the diagnostic completes.
- Makes only unauthenticated public GET requests. It does not call account, order, trading, or private endpoints and does not use secrets or cookies.

## Execution status — not yet run

The workflow file was created and its contents were read back from GitHub. However, the GitHub integration available to this session does not expose a workflow-dispatch action. Therefore I could not start the `workflow_dispatch` run from this session.

**No GitHub Actions run ID exists in the evidence available here. No runner DNS result, endpoint HTTP status, response time, response body, candidate result, or downloadable artifact has yet been produced.** The earlier local DNS failure documented above remains the only observed API connectivity result; it must not be confused with a GitHub-hosted runner result.

To execute the authorized diagnostic, open the workflow URL above, select **Run workflow**, keep branch `main), and confirm **Run workflow**. GitHub Actions will then produce the run result and artifact. This manual trigger is required because the connected GitHub action set in this session has no dispatch capability.

## Checkpoint and stop decision

This is infrastructure/API diagnosis only. No Polybot application code, collector, trading functionality, or Checkpoint 2 implementation was added. The target remains Polymarket US BTC UP/DOWN, exactly 300 seconds, CF Benchmarks BRTI. Do not substitute Polymarket International, Chainlink, or a 15-minute market.

**Checkpoint 1 remains blocked pending the actual GitHub Actions run and candidate-level verification. Stop here and wait for the user's approval after the diagnostic results are available.**


---

# Diagnostic Redaction and Candidate Extraction Fix — 2026-11-15

**Scope:** Fix the one-time Polymarket US public API diagnostic only. No market, venue, timeframe, settlement, or application architecture changes.

## Changes committed

- Workflow: `.github/workflows/polymarket-us-diagnostic.yml`
  - Runs YAML parsing and the focused unit tests before making the four public GET requests.
  - Continues to use `workflow_dispatch`, `ubuntu-latest`, public unauthenticated GET requests only, artifact upload, and diagnostic-results commit.
- Testable diagnostic module: `scripts/polymarket_us_diagnostic.py`
- Regression tests: `tests/test_polymarket_us_diagnostic.py`

## Redaction correction

The previous generic `token` key match could redact public market identifiers. The updated redactor deliberately preserves `tokenId`, `token_id`, and other public outcome token ID fields. It redacts explicit credential keys, including authorization, proxy authorization, cookies/set-cookie, access tokens, refresh tokens, ID tokens, API keys, client secrets, passwords, private keys, session secrets/tokens, and CSRF tokens. Camel-case and separator variations are normalized. Plain-text error bodies also redact credential-like header/parameter values without matching public `tokenId` fields.

## Candidate extraction

Every discovered BTC 5-minute UP/DOWN candidate now explicitly records, when present in the response:

- Market ID and slug
- Asset class/symbol, market family and horizon
- Settlement/resolution source, including explicit settlement/resolution fields and BRTI index symbol
- Start and end timestamps, and computed duration when both timestamps parse
- Market status, active/closed flags and market-specific fee coefficient
- UP token ID and DOWN token ID, extracted from labeled market sides or labeled outcomes/token ID arrays

The extractor does not assign UP/DOWN by array position when labels are missing. Missing fields remain null. Every extracted object is marked `UNVERIFIED_CANDIDATE`; an API discovery match alone is not market verification. Official market detail, rules and settlement evidence must still confirm BTC, UP/DOWN, five-minute horizon, exact 300-second interval, BRTI settlement, outcome/token mapping, and the market-specific fee coefficient.

## Verification performed for this fix

- YAML syntax: parsed successfully using a local YAML parser against the committed workflow content.
- Focused regression logic checks: 7 focused local regression scenarios passed for public token ID preservation, credential redaction (including camel-case and plain-text cases), candidate metadata extraction, direction-labeled token mapping, no positional token inference, and rejection of non-BTC candidates.
- The repository now contains 7 committed `unittest` test methods, and the workflow runs that suite as a preflight step. The GitHub-hosted workflow itself has not been dispatched from this session, so no GitHub Actions test-run result is claimed.
- No Polymarket endpoint was called as part of this code fix. No market is newly verified or declared missing.

## Commit references

- Workflow update: `2ab00ba4fa19e867220bfaa303d7b4da90dbd3a7`
- Diagnostic module updates: latest `6a23735011ced3f95b6ecfdb7bb769a0ed1af9ea`
- Regression tests: latest `4c931718a94891bdc52d2b7d88437382a906b4ec`

The project remains **Polymarket US BTC UP/DOWN, exactly 300 seconds, CF Benchmarks BRTI**. This diagnostic remains read-only. No account access, trading, order placement, collector, or Checkpoint 2 work has been introduced.
