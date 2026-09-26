"""
Tier 1: Feature Coverage — Features F5 & F6.
F5: Admin REST API: Message Thread & Reply (GET/POST /api/tickets/{id}/messages)
F6: Internal Handoff Ingestion Endpoint (POST /api/v1/internal/chat-tickets)
"""

import os
import unittest
from tests.e2e.test_config import (
    LARAVEL_DIR,
    LARAVEL_HOST,
    INTERNAL_API_TOKEN,
    SanctumClient,
    InternalServiceClient,
    is_http_endpoint_alive,
    generate_unique_session,
)


class TestF5AdminMessageThreadAndReplyAPI(unittest.TestCase):
    """Test suite for F5: Admin Message Thread & Reply (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.controller_path = os.path.join(
            LARAVEL_DIR, "app", "Http", "Controllers", "Api", "TicketController.php"
        )
        cls.routes_path = os.path.join(LARAVEL_DIR, "routes", "api.php")
        cls.client = SanctumClient(LARAVEL_HOST)
        cls.internal_client = InternalServiceClient(LARAVEL_HOST)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")
        if cls.backend_alive:
            cls.client.login()

    def setUp(self):
        if self.backend_alive and not self.client.logged_in:
            self.client.login()

    def test_tc01_f5_messages_routes_defined(self):
        """TC-F5-01: Verify messages routes are declared under auth:sanctum group."""
        self.assertTrue(os.path.exists(self.routes_path))
        with open(self.routes_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertTrue("prefix('tickets')" in code or "tickets" in code)
        self.assertIn("/{id}/messages", code)

    def test_tc02_f5_unauthenticated_reply_rejected(self):
        """TC-F5-02: Verify unauthenticated POST /api/tickets/1/messages returns 401."""
        unauth = SanctumClient(LARAVEL_HOST)
        resp = unauth.post("/api/tickets/1/messages", data={"message": "Test reply"})
        self.assertIn(resp.status_code, [401, 419], f"Expected 401 or 419 for unauthenticated POST, got {resp.status_code}")

    def test_tc03_f5_admin_can_send_reply(self):
        """TC-F5-03: Verify admin can send reply returning 201 with sender_type=agent."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        # Create ticket via internal endpoint first
        sess = generate_unique_session("f5-reply")
        create_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Citizen needs assistance",
            "citizen_name": "Pak Joko",
        })
        self.assertEqual(create_resp.status_code, 201)
        ticket_id = create_resp.json()["data"]["ticket_id"]

        # Admin sends reply
        reply_resp = self.client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Halo Pak Joko, kami sedang memproses permohonan Anda.",
            "is_internal_note": False,
        })
        self.assertEqual(reply_resp.status_code, 201)
        data = reply_resp.json()["data"]
        self.assertEqual(data["sender_type"], "agent")
        self.assertIn("Pak Joko", data["message"])

    def test_tc04_f5_reply_updates_ticket_status_to_in_progress(self):
        """TC-F5-04: Verify sending an agent reply automatically moves status from open to in_progress."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("f5-status-trans")
        create_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Permohonan verifikasi akun portal",
        })
        ticket_id = create_resp.json()["data"]["ticket_id"]

        # Post reply
        self.client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Baik, mohon tunggu sebentar.",
            "is_internal_note": False,
        })

        # Verify status is now in_progress
        detail_resp = self.client.get(f"/api/tickets/{ticket_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["data"]["status"], "in_progress")

    def test_tc05_f5_internal_note_preserves_ticket_status(self):
        """TC-F5-05: Verify internal note (is_internal_note=True) does not change ticket status."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("f5-internal-note")
        create_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Pertanyaan penting",
        })
        ticket_id = create_resp.json()["data"]["ticket_id"]

        # Post internal note
        note_resp = self.client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Catatan: Jangan balas sebelum konfirmasi tim teknis",
            "is_internal_note": True,
        })
        self.assertEqual(note_resp.status_code, 201)

        # Status must remain open
        detail_resp = self.client.get(f"/api/tickets/{ticket_id}")
        self.assertEqual(detail_resp.json()["data"]["status"], "open")

    def test_tc06_f5_fetch_message_thread(self):
        """TC-F5-06: Verify GET /api/tickets/{id}/messages returns the message thread."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable")

        sess = generate_unique_session("f5-thread")
        create_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Pesan pertama dari warga",
        })
        ticket_id = create_resp.json()["data"]["ticket_id"]

        resp = self.client.get(f"/api/tickets/{ticket_id}/messages")
        self.assertEqual(resp.status_code, 200)
        messages = resp.json()["data"]
        self.assertTrue(len(messages) >= 1)
        self.assertEqual(messages[0]["message"], "Pesan pertama dari warga")


class TestF6InternalHandoffIngestionEndpoint(unittest.TestCase):
    """Test suite for F6: Internal Handoff Ingestion Endpoint (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.client = InternalServiceClient(LARAVEL_HOST, INTERNAL_API_TOKEN)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")

    def test_tc01_f6_rejects_missing_authorization(self):
        """TC-F6-01: Verify endpoint returns 401 when Authorization header is absent."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        resp = self.client.create_or_update_ticket(
            {"session_id": "test-sess", "message": "Halo"},
            token_override="",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json().get("success", True))

    def test_tc02_f6_rejects_invalid_token(self):
        """TC-F6-02: Verify endpoint returns 401 when invalid Bearer token is provided."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        resp = self.client.create_or_update_ticket(
            {"session_id": "test-sess", "message": "Halo"},
            token_override="invalid-token-xyz-123",
        )
        self.assertEqual(resp.status_code, 401)

    def test_tc03_f6_creates_ticket_with_valid_bearer_token(self):
        """TC-F6-03: Verify valid Bearer token creates ticket returning 201 with ticket metadata."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        sess = generate_unique_session("f6-create")
        resp = self.client.create_or_update_ticket({
            "session_id": sess,
            "intent": "human_escalation",
            "message": "Saya ingin bicara dengan petugas langsung",
            "citizen_name": "Siti Nurhaliza",
            "citizen_contact": "081234567890",
            "citizen_agency": "Dinas Kesehatan",
            "issue_summary": "Pertanyaan seputar izin faskes",
            "channel": "widget",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertIn("ticket_id", data)
        self.assertIn("ticket_number", data)
        self.assertEqual(data["status"], "open")
        self.assertEqual(data["session_id"], sess)

    def test_tc04_f6_accepts_custom_header_x_internal_token(self):
        """TC-F6-04: Verify endpoint authorizes request via X-Internal-Token header."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        sess = generate_unique_session("f6-custom-header")
        resp = self.client.create_or_update_ticket(
            {"session_id": sess, "message": "Pesan via X-Internal-Token"},
            use_custom_header=True,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json().get("success", False))

    def test_tc05_f6_validates_required_fields(self):
        """TC-F6-05: Verify endpoint returns 422 when required fields are missing."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        # Missing message
        resp1 = self.client.create_or_update_ticket({"session_id": "sess-missing-msg"})
        self.assertEqual(resp1.status_code, 422)

        # Missing session_id
        resp2 = self.client.create_or_update_ticket({"message": "Hello without session"})
        self.assertEqual(resp2.status_code, 422)

    def test_tc06_f6_followup_appends_to_active_ticket(self):
        """TC-F6-06: Verify subsequent message in active session appends to existing ticket returning 200."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        sess = generate_unique_session("f6-followup")

        # Initial turn
        resp1 = self.client.create_or_update_ticket({
            "session_id": sess,
            "message": "Turn 1: Saya butuh bantuan",
            "citizen_name": "Rudi",
        })
        self.assertEqual(resp1.status_code, 201)
        ticket_id = resp1.json()["data"]["ticket_id"]

        # Followup turn
        resp2 = self.client.create_or_update_ticket({
            "session_id": sess,
            "intent": "human_escalation_followup",
            "message": "Turn 2: Tambahan informasi NIK 123456",
            "citizen_contact": "081987654321",
        })
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["data"]["ticket_id"], ticket_id)


if __name__ == "__main__":
    unittest.main()
