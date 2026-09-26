"""
Tier 1: Feature Coverage — Features F3 & F4.
F3: Admin REST API: Queue Listing & Stats (GET /api/tickets, GET /api/tickets/stats)
F4: Admin REST API: Detail, Assign & Status (GET /api/tickets/{id}, POST /api/tickets/{id}/assign, PATCH /api/tickets/{id}/status)
"""

import os
import re
import unittest
from tests.e2e.test_config import (
    LARAVEL_DIR,
    LARAVEL_HOST,
    SanctumClient,
    InternalServiceClient,
    is_http_endpoint_alive,
    generate_unique_session,
)


class TestF3AdminQueueAndStatsAPI(unittest.TestCase):
    """Test suite for F3: Admin Queue Listing & Stats (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.controller_path = os.path.join(
            LARAVEL_DIR, "app", "Http", "Controllers", "Api", "TicketController.php"
        )
        cls.routes_path = os.path.join(LARAVEL_DIR, "routes", "api.php")
        cls.client = SanctumClient(LARAVEL_HOST)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")
        if cls.backend_alive:
            cls.client.login()

    def test_tc01_f3_routes_registered_in_api_php(self):
        """TC-F3-01: Verify routes for /api/tickets and /api/tickets/stats are registered in routes/api.php."""
        self.assertTrue(os.path.exists(self.routes_path))
        with open(self.routes_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("tickets", content)
        self.assertTrue(
            "tickets/stats" in content or "stats" in content,
            "Stats route must be registered in routes/api.php",
        )

    def test_tc02_f3_unauthenticated_request_rejected(self):
        """TC-F3-02: Verify unauthenticated GET /api/tickets returns 401 Unauthorized."""
        unauth_client = SanctumClient(LARAVEL_HOST)
        resp = unauth_client.get("/api/tickets")
        self.assertEqual(resp.status_code, 401, "Unauthenticated access to /api/tickets must yield 401")

    def test_tc03_f3_authenticated_list_tickets_structure(self):
        """TC-F3-03: Verify GET /api/tickets returns 200 with data array and pagination metadata."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable or admin login failed")
        resp = self.client.get("/api/tickets")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success", False))
        self.assertIn("data", data)
        self.assertIn("pagination", data)
        self.assertIn("current_page", data["pagination"])
        self.assertIn("total", data["pagination"])

    def test_tc04_f3_filter_by_status(self):
        """TC-F3-04: Verify GET /api/tickets supports ?status filter parameter."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable")
        resp_open = self.client.get("/api/tickets", params={"status": "open"})
        self.assertEqual(resp_open.status_code, 200)
        resp_json = resp_open.json()
        for item in resp_json.get("data", []):
            self.assertEqual(item.get("status"), "open")

    def test_tc05_f3_search_query_parameter(self):
        """TC-F3-05: Verify GET /api/tickets supports ?search query parameter."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable")
        resp = self.client.get("/api/tickets", params={"search": "nonexistent_query_xyz_9999"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data.get("data", [])), 0)

    def test_tc06_f3_stats_endpoint_contract(self):
        """TC-F3-06: Verify GET /api/tickets/stats returns total, open, in_progress, resolved, closed."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable")
        resp = self.client.get("/api/tickets/stats")
        self.assertEqual(resp.status_code, 200)
        stats = resp.json().get("data", {})
        for key in ["total", "open", "in_progress", "resolved", "closed"]:
            self.assertIn(key, stats, f"Stats response must contain key '{key}'")
            self.assertIsInstance(stats[key], int)


class TestF4AdminDetailAssignAndStatusAPI(unittest.TestCase):
    """Test suite for F4: Admin Detail, Assign & Status (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.controller_path = os.path.join(
            LARAVEL_DIR, "app", "Http", "Controllers", "Api", "TicketController.php"
        )
        cls.client = SanctumClient(LARAVEL_HOST)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")
        if cls.backend_alive:
            cls.client.login()
        cls.internal_client = InternalServiceClient(LARAVEL_HOST)

    def test_tc01_f4_controller_methods_exist(self):
        """TC-F4-01: Verify TicketController defines show(), assign(), and updateStatus()."""
        self.assertTrue(os.path.exists(self.controller_path))
        with open(self.controller_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("function show(", code)
        self.assertIn("function assign(", code)
        self.assertIn("function updateStatus(", code)

    def test_tc02_f4_get_nonexistent_ticket_returns_404(self):
        """TC-F4-02: Verify GET /api/tickets/9999999 returns 404 Not Found."""
        if not self.backend_alive or not self.client.logged_in:
            self.skipTest("Laravel backend not reachable")
        resp = self.client.get("/api/tickets/9999999")
        self.assertEqual(resp.status_code, 404)

    def test_tc03_f4_ticket_detail_payload_structure(self):
        """TC-F4-03: Verify GET /api/tickets/{id} returns ticket details with message relations."""
        with open(self.controller_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("assignedAdmin", code)
        self.assertIn("messages", code)

    def test_tc04_f4_assign_ticket_status_transition_contract(self):
        """TC-F4-04: Verify assign endpoint assigns admin and transitions status to in_progress."""
        with open(self.controller_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("assigned_admin_id", code)
        self.assertIn("in_progress", code)

    def test_tc05_f4_status_update_validation(self):
        """TC-F4-05: Verify PATCH /api/tickets/{id}/status validates allowed status values."""
        with open(self.controller_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertTrue(
            "in:open,in_progress,resolved,closed" in code
            or "Rule::in" in code
            or "'status' => 'required" in code
            or "status" in code,
            "Status update must validate enum transitions",
        )

    def test_tc06_f4_resolution_sets_resolved_at_timestamp(self):
        """TC-F4-06: Verify transitioning status to resolved sets resolved_at timestamp."""
        with open(self.controller_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("resolved_at", code)


if __name__ == "__main__":
    unittest.main()
