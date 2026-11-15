import unittest

from scripts.polymarket_us_diagnostic import extract_candidate, redact_public_payload


class RedactionTests(unittest.TestCase):
    def test_public_token_ids_are_preserved(self):
        payload = {
            "tokenId": "public-up-123",
            "token_id": "public-down-456",
            "marketSides": [
                {"name": "UP", "tokenId": "public-up-123"},
                {"name": "DOWN", "token_id": "public-down-456"},
            ],
        }
        cleaned = redact_public_payload(payload)
        self.assertEqual(cleaned["tokenId"], "public-up-123")
        self.assertEqual(cleaned["token_id"], "public-down-456")
        self.assertEqual(cleaned["marketSides"][0]["tokenId"], "public-up-123")
        self.assertEqual(cleaned["marketSides"][1]["token_id"], "public-down-456")

    def test_credentials_are_redacted_recursively(self):
        payload = {
            "Authorization": "Bearer secret",
            "cookie": "session=secret",
            "accessToken": "access-secret",
            "refresh_token": "refresh-secret",
            "apiKey": "api-secret",
            "api_key": "api-secret-2",
            "password": "pw",
            "privateKey": "private",
            "sessionSecret": "session-secret",
            "nested": {"client_secret": "client-secret", "tokenId": "public-id"},
        }
        cleaned = redact_public_payload(payload)
        for key in ("Authorization", "cookie", "accessToken", "refresh_token",
                    "apiKey", "api_key", "password", "privateKey", "sessionSecret"):
            self.assertEqual(cleaned[key], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["client_secret"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["tokenId"], "public-id")


class CandidateExtractionTests(unittest.TestCase):
    def test_extracts_market_metadata_and_directional_token_ids(self):
        market = {
            "id": "market-abc",
            "slug": "btc-updown-5m-123",
            "status": "ACTIVE",
            "feeCoefficient": 0.071,
            "assetPriceTerms": {
                "asset": {"assetClass": "CRYPTO", "symbol": "BTC"},
                "marketType": "ASSET_PRICE_MARKET_TYPE_UP_DOWN",
                "horizon": "5m",
                "indexSymbol": "BRTI",
                "windowStart": "2026-11-15T12:00:00Z",
                "windowEnd": "2026-11-15T12:05:00Z",
                "resolutionSource": "CF Benchmarks BRTI",
            },
            "marketSides": [
                {"name": "UP", "tokenId": "token-up-001"},
                {"name": "DOWN", "token_id": "token-down-002"},
            ],
            "outcomes": ["UP", "DOWN"],
        }
        candidate = extract_candidate(market, "markets")
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["market_id"], "market-abc")
        self.assertEqual(candidate["slug"], "btc-updown-5m-123")
        self.assertEqual(candidate["duration_seconds"], 300.0)
        self.assertEqual(candidate["start_time"], "2026-11-15T12:00:00Z")
        self.assertEqual(candidate["end_time"], "2026-11-15T12:05:00Z")
        self.assertEqual(candidate["market_status"], "ACTIVE")
        self.assertEqual(candidate["fee_coefficient"], 0.071)
        self.assertEqual(candidate["settlement_resolution_source"], "CF Benchmarks BRTI")
        self.assertEqual(candidate["up_token_id"], "token-up-001")
        self.assertEqual(candidate["down_token_id"], "token-down-002")
        self.assertEqual(candidate["verification_status"], "UNVERIFIED_CANDIDATE")

    def test_does_not_infer_direction_from_unlabelled_token_order(self):
        market = {
            "id": "m1",
            "assetPriceTerms": {
                "asset": {"symbol": "BTC"},
                "marketType": "UP_DOWN",
                "horizon": "5m",
            },
            "tokenIds": ["first", "second"],
        }
        candidate = extract_candidate(market)
        self.assertIsNotNone(candidate)
        self.assertIsNone(candidate["up_token_id"])
        self.assertIsNone(candidate["down_token_id"])

    def test_non_btc_five_minute_market_is_not_candidate(self):
        market = {
            "assetPriceTerms": {
                "asset": {"symbol": "ETH"},
                "marketType": "UP_DOWN",
                "horizon": "5m",
            }
        }
        self.assertIsNone(extract_candidate(market))


if __name__ == "__main__":
    unittest.main()
