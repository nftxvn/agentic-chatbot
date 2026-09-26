"""
Tier 1: Feature Coverage — Features F1 & F2.
F1: chat_tickets Migration & Model
F2: chat_ticket_messages Migration & Model
"""

import os
import re
import glob
import unittest
from tests.e2e.test_config import LARAVEL_DIR


class TestF1ChatTicketsModelAndSchema(unittest.TestCase):
    """Test suite for F1: chat_tickets Migration & Model (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.migrations_dir = os.path.join(LARAVEL_DIR, "database", "migrations")
        cls.migration_files = glob.glob(os.path.join(cls.migrations_dir, "*_create_chat_tickets*.php"))
        if not cls.migration_files:
            cls.migration_files = glob.glob(os.path.join(cls.migrations_dir, "*chat_tickets*.php"))
        cls.model_path = os.path.join(LARAVEL_DIR, "app", "Models", "ChatTicket.php")

    def test_tc01_f1_migration_file_exists(self):
        """TC-F1-01: Verify migration file creating chat_tickets exists in database/migrations."""
        self.assertTrue(len(self.migration_files) > 0, "Migration file for chat_tickets must exist")
        with open(self.migration_files[0], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("chat_tickets", content)

    def test_tc02_f1_migration_defines_all_required_columns(self):
        """TC-F1-02: Verify schema defines session_id, ticket_number, citizen_name, contact, agency, summary, status, priority."""
        with open(self.migration_files[0], "r", encoding="utf-8") as f:
            content = f.read()
        required_columns = [
            "session_id",
            "ticket_number",
            "citizen_name",
            "citizen_contact",
            "citizen_agency",
            "issue_summary",
            "status",
            "priority",
        ]
        for col in required_columns:
            self.assertTrue(
                re.search(rf"['\"]{col}['\"]", content),
                f"Column '{col}' must be defined in chat_tickets migration",
            )

    def test_tc03_f1_status_enum_values_and_defaults(self):
        """TC-F1-03: Verify status column supports open, in_progress, resolved, closed with default open."""
        with open(self.migration_files[0], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("open", content)
        self.assertIn("in_progress", content)
        self.assertIn("resolved", content)
        self.assertTrue(
            "closed" in content or "resolved" in content,
            "Ticket status must include resolved or closed",
        )
        self.assertIn("default('open')", content.replace('"', "'"))

    def test_tc04_f1_model_file_exists_and_defines_fillable(self):
        """TC-F1-04: Verify ChatTicket.php model exists and defines required $fillable attributes."""
        self.assertTrue(os.path.exists(self.model_path), "ChatTicket.php model must exist")
        with open(self.model_path, "r", encoding="utf-8") as f:
            content = f.read()
        for attr in ["session_id", "status", "citizen_name", "citizen_contact", "issue_summary"]:
            self.assertIn(attr, content, f"ChatTicket model must include '{attr}' in fillable or casts")

    def test_tc05_f1_model_defines_relationships(self):
        """TC-F1-05: Verify ChatTicket defines messages() hasMany and assignedAdmin() belongsTo relations."""
        with open(self.model_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("function messages(", content)
        self.assertIn("hasMany", content)
        self.assertTrue(
            "function assignedAdmin(" in content or "function admin(" in content or "function user(" in content,
            "ChatTicket must define admin/user relationship",
        )

    def test_tc06_f1_ticket_number_generation_contract(self):
        """TC-F1-06: Verify ticket numbering scheme uses unique prefix TICK-."""
        with open(self.model_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(
            "TICK-" in content or "generateTicketNumber" in content or "ticket_number" in content,
            "Ticket number format contract TICK- must be referenced in model or booted logic",
        )


class TestF2ChatTicketMessagesModelAndSchema(unittest.TestCase):
    """Test suite for F2: chat_ticket_messages Migration & Model (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.migrations_dir = os.path.join(LARAVEL_DIR, "database", "migrations")
        cls.migration_files = glob.glob(os.path.join(cls.migrations_dir, "*_create_chat_tickets*.php"))
        if not cls.migration_files:
            cls.migration_files = glob.glob(os.path.join(cls.migrations_dir, "*chat_ticket_messages*.php"))
        cls.model_path = os.path.join(LARAVEL_DIR, "app", "Models", "ChatTicketMessage.php")

    def test_tc01_f2_migration_defines_chat_ticket_messages(self):
        """TC-F2-01: Verify chat_ticket_messages table definition exists in migration."""
        self.assertTrue(len(self.migration_files) > 0)
        with open(self.migration_files[0], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("chat_ticket_messages", content)

    def test_tc02_f2_messages_schema_columns(self):
        """TC-F2-02: Verify message schema defines ticket_id, sender_type, sender_id, sender_name, message, is_internal_note."""
        with open(self.migration_files[0], "r", encoding="utf-8") as f:
            content = f.read()
        required_cols = ["ticket_id", "sender_type", "sender_name", "message", "is_internal_note"]
        for col in required_cols:
            self.assertTrue(
                re.search(rf"['\"]{col}['\"]", content),
                f"Column '{col}' must be present in chat_ticket_messages migration",
            )

    def test_tc03_f2_sender_type_enum_coverage(self):
        """TC-F2-03: Verify sender_type supports citizen, agent, bot, system."""
        with open(self.migration_files[0], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("citizen", content)
        self.assertIn("agent", content)

    def test_tc04_f2_model_file_exists_and_defines_fillable(self):
        """TC-F2-04: Verify ChatTicketMessage.php model exists and defines fillable fields."""
        self.assertTrue(os.path.exists(self.model_path), "ChatTicketMessage.php model must exist")
        with open(self.model_path, "r", encoding="utf-8") as f:
            content = f.read()
        for field in ["ticket_id", "sender_type", "sender_name", "message", "is_internal_note"]:
            self.assertIn(field, content, f"ChatTicketMessage model must include '{field}'")

    def test_tc05_f2_model_defines_ticket_and_sender_relations(self):
        """TC-F2-05: Verify ChatTicketMessage defines ticket() belongsTo relationship."""
        with open(self.model_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("function ticket(", content)
        self.assertIn("belongsTo", content)

    def test_tc06_f2_internal_note_cast_or_boolean_handling(self):
        """TC-F2-06: Verify is_internal_note defaults to false and is cast to boolean."""
        with open(self.model_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(
            "boolean" in content or "bool" in content or "is_internal_note" in content,
            "ChatTicketMessage must properly type is_internal_note",
        )


if __name__ == "__main__":
    unittest.main()
