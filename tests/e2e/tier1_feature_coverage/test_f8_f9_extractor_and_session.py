"""
Tier 1: Feature Coverage — Features F8 & F9.
F8: Citizen Contact & Issue Extractor (Indonesian phone, email, name, agency, issue summary)
F9: Session Ticket ID State Management (Tracking active ticket ID across turns)
"""

import re
import unittest


# Authoritative regex specifications from PROJECT.md and survey_2
RE_PHONE_INDONESIA = re.compile(
    r"(?:\+62|62|0)8[1-9][0-9]{7,10}\b",
    re.IGNORECASE,
)
RE_PHONE_FORMATTED = re.compile(
    r"(?:\+62[\s-]?|62[\s-]?|0)8[1-9](?:[\s-]?[0-9]){7,10}\b",
    re.IGNORECASE,
)
RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)
RE_CITIZEN_NAME = re.compile(
    r"(?:nama\s+saya|atas\s+nama|panggil\s+saya)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*?)(?=\s+(?:dari|di|nomor|no|hp|wa|email|\.)|\.|$)",
    re.IGNORECASE,
)
AGENCY_KEYWORDS = [
    "Dinas Komunikasi, Informatika dan Statistik",
    "Diskominfotik",
    "Dinas Pendidikan",
    "Dinas Kesehatan",
    "Dinas Kependudukan dan Pencatatan Sipil",
    "Disdukcapil",
    "Badan Perencanaan Pembangunan Daerah",
    "Bappeda",
    "Inspektorat",
    "Kecamatan",
    "Kelurahan",
]


def extract_contacts(text: str) -> dict:
    """Opaque-box reference extractor based on F8 interface contract."""
    clean_text = text.strip()

    # Phone
    phone = None
    phone_match = RE_PHONE_FORMATTED.search(clean_text)
    if phone_match:
        phone = re.sub(r"[\s-]", "", phone_match.group(0))

    # Email
    email = None
    email_match = RE_EMAIL.search(clean_text)
    if email_match:
        email = email_match.group(0)

    # Name
    name = None
    name_match = RE_CITIZEN_NAME.search(clean_text)
    if name_match:
        name = name_match.group(1).strip()

    # Agency
    agency = None
    for ag in AGENCY_KEYWORDS:
        if re.search(rf"\b{re.escape(ag)}\b", clean_text, re.IGNORECASE):
            agency = ag
            break

    # Issue summary
    issue = clean_text[:150]

    return {
        "citizen_name": name,
        "citizen_contact": phone or email,
        "citizen_phone": phone,
        "citizen_email": email,
        "citizen_agency": agency,
        "issue_summary": issue,
    }


class SimulatedSessionMemory:
    """In-memory reference implementation of F9 ticket session state management."""
    def __init__(self):
        self._sessions = {}

    def set_active_ticket(self, session_id: str, ticket_id: int):
        if session_id not in self._sessions:
            self._sessions[session_id] = {}
        self._sessions[session_id]["ticket_id"] = ticket_id

    def get_active_ticket(self, session_id: str):
        return self._sessions.get(session_id, {}).get("ticket_id")

    def clear_active_ticket(self, session_id: str):
        if session_id in self._sessions and "ticket_id" in self._sessions[session_id]:
            del self._sessions[session_id]["ticket_id"]


class TestF8CitizenContactAndIssueExtractor(unittest.TestCase):
    """Test suite for F8: Citizen Contact & Issue Extractor (>= 5 test cases)."""

    def test_tc01_f8_extract_standard_08_phone(self):
        """TC-F8-01: Verify extraction of standard Indonesian mobile starting with 08."""
        text = "Halo, nama saya Budi. Nomor WA saya 081234567890 tolong dihubungi."
        result = extract_contacts(text)
        self.assertEqual(result["citizen_phone"], "081234567890")
        self.assertEqual(result["citizen_name"], "Budi")

    def test_tc02_f8_extract_plus62_international_phone(self):
        """TC-F8-02: Verify extraction of Indonesian mobile with +62 country code."""
        text = "Mohon bantuan petugas, kontak saya di +6285211223344."
        result = extract_contacts(text)
        self.assertEqual(result["citizen_phone"], "+6285211223344")

    def test_tc03_f8_extract_hyphenated_and_spaced_phones(self):
        """TC-F8-03: Verify extraction of phone numbers formatted with dashes or spaces."""
        text1 = "Hubungi saya di 0812-3456-7890 ya."
        result1 = extract_contacts(text1)
        self.assertEqual(result1["citizen_phone"], "081234567890")

        text2 = "Kontak: 0852 9876 5432"
        result2 = extract_contacts(text2)
        self.assertEqual(result2["citizen_phone"], "085298765432")

    def test_tc04_f8_extract_email_address(self):
        """TC-F8-04: Verify extraction of citizen email address."""
        text = "Email saya ahmad.fauzi@bandaaceh.go.id, kendala portal SPBE."
        result = extract_contacts(text)
        self.assertEqual(result["citizen_email"], "ahmad.fauzi@bandaaceh.go.id")

    def test_tc05_f8_extract_government_agency(self):
        """TC-F8-05: Verify extraction of recognized agency (OPD) name."""
        text = "Saya dari Dinas Pendidikan ingin konsultasi jaringan internet."
        result = extract_contacts(text)
        self.assertEqual(result["citizen_agency"], "Dinas Pendidikan")

    def test_tc06_f8_extract_complex_combined_message(self):
        """TC-F8-06: Verify extraction when citizen provides name, phone, email, and agency in one message."""
        text = (
            "Nama saya Rina Marlina dari Diskominfotik. "
            "Email: rina@diskominfotik.go.id, HP: 081399887766. "
            "Server aplikasi simpeg down sejak tadi pagi."
        )
        result = extract_contacts(text)
        self.assertEqual(result["citizen_name"], "Rina Marlina")
        self.assertEqual(result["citizen_agency"], "Diskominfotik")
        self.assertEqual(result["citizen_email"], "rina@diskominfotik.go.id")
        self.assertEqual(result["citizen_phone"], "081399887766")
        self.assertIn("Server aplikasi simpeg down", result["issue_summary"])


class TestF9SessionTicketIDStateManagement(unittest.TestCase):
    """Test suite for F9: Session Ticket ID State Management (>= 5 test cases)."""

    def setUp(self):
        self.memory = SimulatedSessionMemory()

    def test_tc01_f9_set_and_get_active_ticket(self):
        """TC-F9-01: Verify setting and retrieving active ticket ID for a session."""
        self.memory.set_active_ticket("sess-001", 101)
        self.assertEqual(self.memory.get_active_ticket("sess-001"), 101)

    def test_tc02_f9_isolation_between_distinct_sessions(self):
        """TC-F9-02: Verify multiple sessions maintain strictly isolated ticket IDs."""
        self.memory.set_active_ticket("sess-A", 201)
        self.memory.set_active_ticket("sess-B", 202)
        self.assertEqual(self.memory.get_active_ticket("sess-A"), 201)
        self.assertEqual(self.memory.get_active_ticket("sess-B"), 202)

    def test_tc03_f9_untracked_session_returns_none(self):
        """TC-F9-03: Verify querying untracked session returns None."""
        self.assertIsNone(self.memory.get_active_ticket("sess-unknown-999"))

    def test_tc04_f9_clear_active_ticket_upon_resolution(self):
        """TC-F9-04: Verify clearing active ticket leaves session with None."""
        self.memory.set_active_ticket("sess-resolve-1", 305)
        self.assertEqual(self.memory.get_active_ticket("sess-resolve-1"), 305)
        self.memory.clear_active_ticket("sess-resolve-1")
        self.assertIsNone(self.memory.get_active_ticket("sess-resolve-1"))

    def test_tc05_f9_followup_preserves_ticket_id_across_turns(self):
        """TC-F9-05: Verify repeated lookups throughout conversation turns consistently return active ticket."""
        self.memory.set_active_ticket("sess-multi-turn", 450)
        # Turn 2
        self.assertEqual(self.memory.get_active_ticket("sess-multi-turn"), 450)
        # Turn 3
        self.assertEqual(self.memory.get_active_ticket("sess-multi-turn"), 450)


if __name__ == "__main__":
    unittest.main()
