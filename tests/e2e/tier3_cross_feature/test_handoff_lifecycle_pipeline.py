"""
Tier 3: Cross-Feature Interactions — Complete Handoff Lifecycle Pipeline.
Executes the full 9-step human escalation lifecycle from ingestion through resolution.
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


class TestHandoffLifecyclePipeline(unittest.TestCase):
    """Full lifecycle integration test: Creation -> Ingestion -> Admin pickup -> Notes -> Reply -> Followup -> Resolution."""

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

    def test_complete_human_handoff_lifecycle_pipeline(self):
        """Execute the full 9-stage handoff pipeline."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("pipeline-full")

        # -------------------------------------------------------------
        # STAGE 1: Citizen Triggers Escalation (Python AI -> Laravel)
        # -------------------------------------------------------------
        create_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "intent": "human_escalation",
            "message": "Halo, saya tidak bisa login ke portal SPBE. Mohon dibantu petugas.",
            "citizen_name": "Cut Meurah",
            "citizen_contact": "081234567890",
            "citizen_agency": "Dinas Koperasi dan UKM",
            "issue_summary": "Gagal login portal SPBE",
            "channel": "widget",
        })
        self.assertEqual(create_resp.status_code, 201)
        ticket_data = create_resp.json()["data"]
        ticket_id = ticket_data["ticket_id"]
        ticket_num = ticket_data["ticket_number"]
        self.assertEqual(ticket_data["status"], "open")
        self.assertTrue(ticket_num.startswith("TICK-"))

        # -------------------------------------------------------------
        # STAGE 2: Admin Queue Lists the Incoming Ticket
        # -------------------------------------------------------------
        queue_resp = self.sanctum_client.get("/api/tickets", params={"status": "open"})
        self.assertEqual(queue_resp.status_code, 200)
        open_tickets = queue_resp.json().get("data", [])
        found = any(t["id"] == ticket_id for t in open_tickets)
        self.assertTrue(found, f"Ticket {ticket_id} must appear in open tickets queue")

        # -------------------------------------------------------------
        # STAGE 3: Admin Views Ticket Details & Initial Message
        # -------------------------------------------------------------
        detail_resp = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail = detail_resp.json()["data"]
        self.assertEqual(detail["citizen_name"], "Cut Meurah")
        self.assertEqual(detail["citizen_contact"], "081234567890")
        self.assertEqual(detail["citizen_agency"], "Dinas Koperasi dan UKM")
        self.assertEqual(len(detail["messages"]), 1)
        self.assertEqual(detail["messages"][0]["sender_type"], "citizen")

        # -------------------------------------------------------------
        # STAGE 4: Admin Self-Assigns the Ticket
        # -------------------------------------------------------------
        assign_resp = self.sanctum_client.post(f"/api/tickets/{ticket_id}/assign", data={})
        self.assertEqual(assign_resp.status_code, 200)
        self.assertEqual(assign_resp.json()["data"]["status"], "in_progress")
        self.assertIsNotNone(assign_resp.json()["data"]["assigned_admin_id"])

        # -------------------------------------------------------------
        # STAGE 5: Admin Adds Internal Note (Private to Staff)
        # -------------------------------------------------------------
        note_resp = self.sanctum_client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Catatan internal: Sudah dikoordinasikan dengan tim IT SPBE.",
            "is_internal_note": True,
        })
        self.assertEqual(note_resp.status_code, 201)

        # -------------------------------------------------------------
        # STAGE 6: Admin Sends Public Reply to Citizen
        # -------------------------------------------------------------
        reply_resp = self.sanctum_client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Halo Ibu Cut Meurah, akun Anda sudah kami reset password sementara. Silakan login kembali.",
            "is_internal_note": False,
        })
        self.assertEqual(reply_resp.status_code, 201)
        self.assertEqual(reply_resp.json()["data"]["sender_type"], "agent")

        # -------------------------------------------------------------
        # STAGE 7: Citizen Sends Follow-Up in Same Session
        # -------------------------------------------------------------
        follow_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "ticket_id": ticket_id,
            "intent": "human_escalation_followup",
            "message": "Terima kasih banyak, saya sudah berhasil login!",
        })
        self.assertEqual(follow_resp.status_code, 200)
        self.assertEqual(follow_resp.json()["data"]["ticket_id"], ticket_id)

        # -------------------------------------------------------------
        # STAGE 8: Verify Complete Message Thread
        # -------------------------------------------------------------
        thread_resp = self.sanctum_client.get(f"/api/tickets/{ticket_id}/messages")
        self.assertEqual(thread_resp.status_code, 200)
        messages = thread_resp.json()["data"]
        # Expected: 1 initial citizen + 1 internal note + 1 admin reply + 1 citizen followup = 4 messages
        self.assertEqual(len(messages), 4)

        # -------------------------------------------------------------
        # STAGE 9: Admin Resolves and Closes Ticket
        # -------------------------------------------------------------
        res_resp = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={"status": "resolved"})
        self.assertEqual(res_resp.status_code, 200)
        self.assertEqual(res_resp.json()["data"]["status"], "resolved")

        close_resp = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={"status": "closed"})
        self.assertEqual(close_resp.status_code, 200)
        self.assertEqual(close_resp.json()["data"]["status"], "closed")


if __name__ == "__main__":
    unittest.main()
