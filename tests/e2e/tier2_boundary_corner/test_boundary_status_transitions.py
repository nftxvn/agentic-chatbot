"""
Tier 2: Boundary & Corner Cases — Status Transitions & Admin State Changes.
Verifies invalid status transitions, non-existent ticket IDs, and empty reply validations.
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


class TestBoundaryStatusTransitions(unittest.TestCase):
    """Test suite for boundary status transitions and admin endpoints (>= 5 test cases)."""

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

    def test_tc01_bnd_invalid_status_value_returns_422(self):
        """TC-BND-STAT-01: Verify patching status to unrecognized value ('deleted', 'pending') returns 422."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("bnd-stat-invalid")
        c_resp = self.internal_client.create_or_update_ticket({"session_id": sess, "message": "Test"})
        ticket_id = c_resp.json()["data"]["ticket_id"]

        resp = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={"status": "invalid_status"})
        self.assertEqual(resp.status_code, 422)

    def test_tc02_bnd_missing_status_field_returns_422(self):
        """TC-BND-STAT-02: Verify PATCH /api/tickets/{id}/status without 'status' field returns 422."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("bnd-stat-missing")
        c_resp = self.internal_client.create_or_update_ticket({"session_id": sess, "message": "Test"})
        ticket_id = c_resp.json()["data"]["ticket_id"]

        resp = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={})
        self.assertEqual(resp.status_code, 422)

    def test_tc03_bnd_update_status_on_nonexistent_ticket_returns_404(self):
        """TC-BND-STAT-03: Verify PATCH /api/tickets/999999/status returns 404 Not Found."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        resp = self.sanctum_client.patch("/api/tickets/999999/status", data={"status": "resolved"})
        self.assertEqual(resp.status_code, 404)

    def test_tc04_bnd_assign_nonexistent_admin_returns_422(self):
        """TC-BND-STAT-04: Verify assigning ticket to non-existent admin ID returns 422 validation error."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("bnd-assign-nonexistent")
        c_resp = self.internal_client.create_or_update_ticket({"session_id": sess, "message": "Test"})
        ticket_id = c_resp.json()["data"]["ticket_id"]

        resp = self.sanctum_client.post(f"/api/tickets/{ticket_id}/assign", data={"admin_id": 999999})
        self.assertEqual(resp.status_code, 422)

    def test_tc05_bnd_empty_reply_message_returns_422(self):
        """TC-BND-STAT-05: Verify admin sending empty reply message body returns 422."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("bnd-reply-empty")
        c_resp = self.internal_client.create_or_update_ticket({"session_id": sess, "message": "Test"})
        ticket_id = c_resp.json()["data"]["ticket_id"]

        resp = self.sanctum_client.post(f"/api/tickets/{ticket_id}/messages", data={"message": ""})
        self.assertEqual(resp.status_code, 422)

    def test_tc06_bnd_consecutive_status_transitions(self):
        """TC-BND-STAT-06: Verify full sequence: open -> in_progress -> resolved -> closed."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("bnd-lifecycle")
        c_resp = self.internal_client.create_or_update_ticket({"session_id": sess, "message": "Test lifecycle"})
        ticket_id = c_resp.json()["data"]["ticket_id"]

        # open -> in_progress
        r1 = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={"status": "in_progress"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["data"]["status"], "in_progress")

        # in_progress -> resolved
        r2 = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={"status": "resolved"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["data"]["status"], "resolved")

        # resolved -> closed
        r3 = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={"status": "closed"})
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()["data"]["status"], "closed")


if __name__ == "__main__":
    unittest.main()
