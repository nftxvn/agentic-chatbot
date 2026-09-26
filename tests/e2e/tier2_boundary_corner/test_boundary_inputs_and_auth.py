"""
Tier 2: Boundary & Corner Cases — Input Validation & Authorization Limits.
Verifies empty inputs, extreme string sizes, missing keys, and invalid tokens.
"""

import unittest
from tests.e2e.test_config import (
    LARAVEL_HOST,
    INTERNAL_API_TOKEN,
    InternalServiceClient,
    SanctumClient,
    is_http_endpoint_alive,
    generate_unique_session,
)


class TestBoundaryInputsAndAuth(unittest.TestCase):
    """Test suite for boundary inputs, payloads, and authentication security (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.internal_client = InternalServiceClient(LARAVEL_HOST, INTERNAL_API_TOKEN)
        cls.sanctum_client = SanctumClient(LARAVEL_HOST)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")
        if cls.backend_alive:
            cls.sanctum_client.login()

    def test_tc01_bnd_empty_json_payload_returns_422(self):
        """TC-BND-01: Verify submitting empty JSON object {} returns 422 Unprocessable Content."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        resp = self.internal_client.create_or_update_ticket({})
        self.assertEqual(resp.status_code, 422)
        errors = resp.json().get("errors", {})
        self.assertIn("session_id", errors)
        self.assertIn("message", errors)

    def test_tc02_bnd_empty_string_values_returns_422(self):
        """TC-BND-02: Verify submitting empty string values '' returns 422 validation errors."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": "",
            "message": "",
        })
        self.assertEqual(resp.status_code, 422)

    def test_tc03_bnd_tampered_bearer_token_returns_401(self):
        """TC-BND-03: Verify tampered token (off by one character) is rejected with 401."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        tampered_token = INTERNAL_API_TOKEN[:-1] + "X"
        resp = self.internal_client.create_or_update_ticket(
            {"session_id": "bnd-tamper", "message": "Test"},
            token_override=tampered_token,
        )
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json().get("success", True))

    def test_tc04_bnd_empty_bearer_token_header(self):
        """TC-BND-04: Verify header 'Authorization: Bearer ' with empty string token returns 401."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        resp = self.internal_client.create_or_update_ticket(
            {"session_id": "bnd-empty-tok", "message": "Test"},
            token_override="",
        )
        self.assertEqual(resp.status_code, 401)

    def test_tc05_bnd_extra_unrecognized_fields_handled_gracefully(self):
        """TC-BND-05: Verify unexpected extra fields in payload do not cause 500 error."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        sess = generate_unique_session("bnd-extra-fields")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Valid citizen message with extra fields",
            "unknown_extra_field_1": 12345,
            "malicious_looking_key": {"nested": "payload"},
        })
        self.assertEqual(resp.status_code, 201)

    def test_tc06_bnd_oversized_message_payload(self):
        """TC-BND-06: Verify handling large text payload (8,000 characters) without buffer overflow."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        sess = generate_unique_session("bnd-oversize")
        large_message = "Kendala sistem berulang. " * 320  # ~8,000 chars
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": large_message,
        })
        self.assertEqual(resp.status_code, 201)
        self.assertIn("ticket_id", resp.json()["data"])


if __name__ == "__main__":
    unittest.main()
