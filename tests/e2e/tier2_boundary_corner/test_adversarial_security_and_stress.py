"""
Tier 2: Boundary & Corner Cases — Adversarial Security & Stress Verification.
Verifies resilience against SQL injection, XSS polyglots, Unicode/emojis, and burst traffic.
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


class TestAdversarialSecurityAndStress(unittest.TestCase):
    """Test suite for adversarial attack inputs and burst traffic (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.internal_client = InternalServiceClient(LARAVEL_HOST, INTERNAL_API_TOKEN)
        cls.sanctum_client = SanctumClient(LARAVEL_HOST)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")
        if cls.backend_alive:
            cls.sanctum_client.login()

    def setUp(self):
        if self.backend_alive and not self.sanctum_client.logged_in:
            self.sanctum_client.login()

    def test_tc01_adv_sql_injection_in_message_and_name(self):
        """TC-ADV-01: Verify SQL injection payloads are safely parameterized without DB compromise."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE chat_tickets; --",
            "admin' UNION SELECT id, name, email FROM users --",
            "1' or 1=1--",
        ]
        for idx, sqli in enumerate(sqli_payloads):
            sess = generate_unique_session(f"adv-sqli-{idx}")
            resp = self.internal_client.create_or_update_ticket({
                "session_id": sess,
                "message": f"Help needed: {sqli}",
                "citizen_name": sqli,
                "issue_summary": sqli,
            })
            self.assertEqual(resp.status_code, 201)
            # Verify the ticket was stored with exact text, not executed as SQL
            ticket_id = resp.json()["data"]["ticket_id"]
            if self.sanctum_client.logged_in:
                detail = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(detail.json()["data"]["citizen_name"], sqli)

    def test_tc02_adv_xss_polyglot_payload_in_message(self):
        """TC-ADV-02: Verify XSS script tags and event handlers are safely stored and returned intact."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        xss_payload = '<script>alert("XSS")</script><img src=x onerror=alert(1)>'
        sess = generate_unique_session("adv-xss")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": xss_payload,
            "citizen_name": "Test XSS",
        })
        self.assertEqual(resp.status_code, 201)
        ticket_id = resp.json()["data"]["ticket_id"]

        if self.sanctum_client.logged_in:
            detail = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
            self.assertEqual(detail.status_code, 200)
            messages = detail.json()["data"].get("messages", [])
            self.assertTrue(len(messages) >= 1)
            self.assertEqual(messages[0]["message"], xss_payload)

    def test_tc03_adv_unicode_and_emojis_utf8mb4(self):
        """TC-ADV-03: Verify Indonesian text with emojis and Unicode symbols is preserved without encoding corruption."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        emoji_text = "🚨 Laporan Darurat SPBE: Server down! 🔥 Tolong segera ditangani 👨‍💻🇮🇩 Terima kasih 🙏"
        sess = generate_unique_session("adv-emoji")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": emoji_text,
            "citizen_name": "Pak Budi 👍",
        })
        self.assertEqual(resp.status_code, 201)
        ticket_id = resp.json()["data"]["ticket_id"]

        if self.sanctum_client.logged_in:
            detail = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["data"]["citizen_name"], "Pak Budi 👍")
            messages = detail.json()["data"].get("messages", [])
            self.assertEqual(messages[0]["message"], emoji_text)

    def test_tc04_adv_rapid_sequential_burst_traffic(self):
        """TC-ADV-04: Verify rapid sequence of 5 requests for the same session does not cause deadlocks or race conditions."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        sess = generate_unique_session("adv-burst")
        # 1. Initial creation
        resp_init = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Burst message 0",
        })
        self.assertEqual(resp_init.status_code, 201)
        ticket_id = resp_init.json()["data"]["ticket_id"]

        # 2. Four rapid follow-ups
        for i in range(1, 5):
            resp_follow = self.internal_client.create_or_update_ticket({
                "session_id": sess,
                "ticket_id": ticket_id,
                "message": f"Burst message {i}",
            })
            self.assertEqual(resp_follow.status_code, 200)
            self.assertEqual(resp_follow.json()["data"]["ticket_id"], ticket_id)

        # 3. Verify total messages count is 5
        if self.sanctum_client.logged_in:
            thread_resp = self.sanctum_client.get(f"/api/tickets/{ticket_id}/messages")
            self.assertEqual(thread_resp.status_code, 200)
            self.assertEqual(len(thread_resp.json()["data"]), 5)

    def test_tc05_adv_special_html_entities_and_slashes(self):
        """TC-ADV-05: Verify quotes, slashes, ampersands, and angle brackets are correctly preserved."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        special_text = 'Test: "quotes", \'single\', backslash \\, forward / slash & ampersand <tags>'
        sess = generate_unique_session("adv-special-chars")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": special_text,
        })
        self.assertEqual(resp.status_code, 201)
        ticket_id = resp.json()["data"]["ticket_id"]

        if self.sanctum_client.logged_in:
            detail = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
            self.assertEqual(detail.status_code, 200)
            messages = detail.json()["data"].get("messages", [])
            self.assertEqual(messages[0]["message"], special_text)


if __name__ == "__main__":
    unittest.main()
