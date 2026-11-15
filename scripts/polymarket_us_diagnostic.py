"""Read-only Polymarket US public API diagnostic helpers and runner."""
from __future__ import annotations

import datetime as dt
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HOST = "gateway.polymarket.us"
BASE = "https://" + HOST
MAX_BODY = 750_000

# Deliberately do not match the generic word "token": tokenId/token_id are
# public market identifiers and must remain available for outcome mapping.
_SECRET_KEYS = {
    "authorization", "proxy_authorization", "cookie", "set_cookie",
    "access_token", "refresh_token", "id_token", "api_key", "apikey",
    "client_secret", "password", "passwd", "private_key", "secret",
    "session_secret", "session_token", "csrf_token",
}


def _normalized_key(key: Any) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()


def redact_public_payload(value: Any) -> Any:
    """Recursively redact credential fields while preserving public token IDs."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized = _normalized_key(key)
            if normalized in _SECRET_KEYS or any(part in normalized for part in ("authorization", "cookie", "access_token", "refresh_token", "id_token", "api_key", "client_secret", "password", "passwd", "private_key", "session_secret", "session_token", "csrf_token")):
                cleaned[str(key)] = "[REDACTED]"
            else:
                cleaned[str(key)] = redact_public_payload(item)
        return cleaned
    if isinstance(value, list):
        return [redact_public_payload(item) for item in value]
    if isinstance(value, str):
        return value[:20_000]
    return value


def _first(mapping: dict, *keys):
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _side_label(side: Any) -> str:
    if isinstance(side, dict):
        raw = _first(side, "name", "label", "outcome", "side", "direction", "title", "sideName", "outcomeName")
        return str(raw or "").strip().lower()
    return str(side or "").strip().lower()


def _token_id(side: Any):
    if isinstance(side, dict):
        direct = _first(side, "tokenId", "token_id", "tokenID", "clobTokenId")
        if direct is not None:
            return direct
        token = side.get("token")
        if isinstance(token, dict):
            return _first(token, "id", "tokenId", "token_id")
    return None


def _extract_direction_tokens(obj: dict) -> dict:
    found = {"up_token_id": None, "down_token_id": None}
    containers = []
    for key in ("marketSides", "outcomes", "tokens", "tokenIds", "token_ids"):
        value = obj.get(key)
        if isinstance(value, list):
            containers.extend(value)
        elif isinstance(value, dict):
            for label, side in value.items():
                if isinstance(side, dict):
                    labelled = dict(side)
                    labelled.setdefault("name", label)
                    containers.append(labelled)
                else:
                    containers.append({"name": label, "tokenId": side})

    # Some schemas keep outcome labels and token IDs in parallel arrays.
    outcomes = obj.get("outcomes")
    token_ids = _first(obj, "tokenIds", "token_ids")
    if isinstance(outcomes, list) and isinstance(token_ids, list):
        for label, token_id in zip(outcomes, token_ids):
            normalized = _side_label(label)
            if normalized in ("up", "yes", "higher"):
                found["up_token_id"] = token_id
            elif normalized in ("down", "no", "lower"):
                found["down_token_id"] = token_id

    for side in containers:
        label = _side_label(side)
        token_id = _token_id(side)
        if token_id is None:
            continue
        if label in ("up", "yes", "higher") or label.startswith("up "):
            found["up_token_id"] = token_id
        elif label in ("down", "no", "lower") or label.startswith("down "):
            found["down_token_id"] = token_id

    # Preserve IDs found in common nested market-side shapes, without assigning
    # direction from array position when labels are absent.
    return found


def _parse_time(value):
    if value is None:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def extract_candidate(obj: dict, source_endpoint: str = "") -> dict | None:
    """Extract a BTC 5m UP/DOWN discovery candidate without asserting validity."""
    terms = obj.get("assetPriceTerms")
    terms = terms if isinstance(terms, dict) else {}
    asset = terms.get("asset") if isinstance(terms.get("asset"), dict) else {}
    blob = json.dumps(obj, ensure_ascii=False).lower()
    asset_symbol = _first(asset, "symbol", "assetSymbol")
    market_type = _first(terms, "marketType") or obj.get("marketType")
    horizon = _first(terms, "horizon", "timeHorizon")
    btc_match = str(asset_symbol or "").lower() == "btc" or "bitcoin" in blob or '"btc"' in blob
    updown_match = (
        str(market_type or "").lower() in ("up_down", "updown", "asset_price_market_type_up_down")
        or "up_down" in blob or "updown" in blob
        or ("up" in blob and "down" in blob)
    )
    five_min_match = (
        str(horizon or "").lower() in ("5m", "5min", "5_min", "five_minutes")
        or "5-minute" in blob or "5 minute" in blob or '"5m"' in blob
    )
    if not (btc_match and updown_match and five_min_match):
        return None

    start = _first(terms, "windowStart", "windowStartTime", "intervalStart", "startTime")
    end = _first(terms, "windowEnd", "windowEndTime", "intervalEnd", "endTime")
    start_dt, end_dt = _parse_time(start), _parse_time(end)
    duration = (end_dt - start_dt).total_seconds() if start_dt and end_dt else None
    token_map = _extract_direction_tokens(obj)

    resolution = _first(
        obj, "settlementSource", "resolutionSource", "resolution_source",
        "settlementReference", "resolutionSourceDescription", "settlementMethod", "resolutionMethod", "rulesDisclaimer",
    )
    if resolution is None:
        resolution = _first(
            terms, "settlementSource", "resolutionSource", "indexSymbol",
            "settlementReference", "resolutionSourceDescription", "settlementMethod", "resolutionMethod",
        )

    return {
        "source_endpoint": source_endpoint,
        "market_id": _first(obj, "id", "marketId", "market_id"),
        "slug": _first(obj, "slug", "marketSlug", "market_slug"),
        "question": _first(obj, "question", "title"),
        "asset_class": _first(asset, "assetClass", "class"),
        "asset_symbol": asset_symbol,
        "market_type": market_type,
        "horizon": horizon,
        "settlement_resolution_source": resolution,
        "index_symbol": terms.get("indexSymbol"),
        "start_time": start,
        "end_time": end,
        "duration_seconds": duration,
        "market_status": _first(obj, "status", "marketStatus"),
        "active": obj.get("active"),
        "closed": obj.get("closed"),
        "fee_coefficient": _first(obj, "feeCoefficient", "fee_coefficient"),
        "up_token_id": token_map["up_token_id"],
        "down_token_id": token_map["down_token_id"],
        "market_sides": obj.get("marketSides"),
        "outcomes": obj.get("outcomes"),
        "raw_candidate": redact_public_payload(obj),
        "verification_status": "UNVERIFIED_CANDIDATE",
        "verification_note": (
            "A discovery response is not proof of market eligibility or settlement. "
            "Verify the exact market detail, rules, settlement response, token mapping, "
            "300-second duration, BRTI reference, and market-specific fee coefficient."
        ),
    }


def parse_response_body(raw: bytes):
    try:
        return redact_public_payload(json.loads(raw.decode("utf-8", "replace")))
    except Exception:
        return {"non_json_body": raw.decode("utf-8", "replace")[:20_000]}


def request_endpoint(name, path, params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    started = time.perf_counter()
    result = {
        "name": name, "url": url, "http_status": None, "classification": None,
        "response_time_ms": None, "content_type": None, "response_body": None,
        "error": None,
    }
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Polybot-ReadOnly-Diagnostic/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(MAX_BODY + 1)
            result.update(
                http_status=response.status,
                content_type=response.headers.get("Content-Type"),
                response_body=parse_response_body(raw[:MAX_BODY]),
                body_truncated=len(raw) > MAX_BODY,
            )
            result["classification"] = "EMPTY_SUCCESS" if not raw else "SUCCESSFUL_RESPONSE"
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_BODY + 1)
        result.update(
            http_status=exc.code,
            content_type=exc.headers.get("Content-Type") if exc.headers else None,
            response_body=parse_response_body(raw[:MAX_BODY]),
            body_truncated=len(raw) > MAX_BODY,
            classification="HTTP_ERROR",
            error=str(exc.reason),
        )
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            kind = "DNS_FAILURE"
        elif isinstance(reason, ssl.SSLError):
            kind = "TLS_FAILURE"
        else:
            kind = "CONNECTION_FAILURE"
        result.update(classification=kind, error=type(reason).__name__ + ": " + str(reason))
    except ssl.SSLError as exc:
        result.update(classification="TLS_FAILURE", error=type(exc).__name__ + ": " + str(exc))
    except (ConnectionError, TimeoutError, OSError) as exc:
        result.update(classification="CONNECTION_FAILURE", error=type(exc).__name__ + ": " + str(exc))
    except Exception as exc:
        result.update(classification="CLIENT_ERROR", error=type(exc).__name__ + ": " + str(exc))
    result["response_time_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result


def run_diagnostic(output_dir: str = "diagnostics/latest"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        rows = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        dns = {"classification": "DNS_SUCCESS", "addresses": sorted({r[4][0] for r in rows}),
               "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
    except socket.gaierror as exc:
        dns = {"classification": "DNS_FAILURE", "error": type(exc).__name__ + ": " + str(exc),
               "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}

    specs = [
        ("markets", "/v1/markets", {"limit": 100, "offset": 0, "active": "true", "closed": "false", "archived": "false", "includeHidden": "true"}),
        ("events", "/v1/events", {"limit": 100, "offset": 0, "active": "true", "closed": "false", "archived": "false", "includeHidden": "true"}),
        ("series", "/v1/series", {"limit": 100, "offset": 0}),
        ("search", "/v1/search", {"query": "BTC", "limit": 100, "page": 1, "status": "active"}),
    ]
    results = [request_endpoint(*spec) for spec in specs]
    candidates, seen, candidate_sources = [], set(), set()
    for result in results:
        if result["http_status"] is None or not 200 <= result["http_status"] < 300:
            continue
        for item in _walk(result["response_body"]):
            candidate = extract_candidate(item, result["name"])
            if candidate is None:
                continue
            identity = json.dumps(candidate["raw_candidate"], sort_keys=True, ensure_ascii=False)
            if identity in seen:
                continue
            seen.add(identity)
            candidate_sources.add(result["name"])
            candidates.append(candidate)
    for result in results:
        if result["classification"] == "SUCCESSFUL_RESPONSE":
            result["classification"] = (
                "SUCCESSFUL_RESPONSE_WITH_MATCH" if result["name"] in candidate_sources
                else "SUCCESSFUL_RESPONSE_NO_MATCH"
            )

    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {
        "generated_at_utc": generated,
        "runner": "GitHub-hosted ubuntu-latest",
        "host": HOST,
        "scope": "Public unauthenticated GET only; no account/order/trading/private endpoints",
        "dns": dns, "endpoints": results,
        "candidate_count": len(candidates), "candidates": candidates,
        "verification_note": "Candidates remain UNVERIFIED until official market detail, rules, and settlement evidence confirms all required properties.",
    }
    (out / "polymarket-us-diagnostic.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Polymarket US API Diagnostic", "", f"- Generated UTC: {generated}",
        f"- DNS: {dns['classification']}", "",
        "| Endpoint | Classification | HTTP | Response time (ms) |",
        "|---|---|---:|---:|",
    ]
    for result in results:
        status = result["http_status"] if result["http_status"] is not None else "—"
        lines.append(f"| {result['name']} | {result['classification']} | {status} | {result['response_time_ms']} |")
    lines += ["", f"BTC UP/DOWN 5-minute discovery candidates: {len(candidates)}.", "",
              "Candidates are UNVERIFIED. Consult the JSON for returned fields, including directional token IDs."]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "dns": dns,
        "endpoints": [{key: result[key] for key in ("name", "classification", "http_status", "response_time_ms")} for result in results],
        "candidate_count": len(candidates),
    }, indent=2))
    return report


if __name__ == "__main__":
    run_diagnostic()
