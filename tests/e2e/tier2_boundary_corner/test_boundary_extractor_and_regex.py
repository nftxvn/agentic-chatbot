"""
Tier 2: Boundary & Corner Cases — Contact Extractor & Regex Boundary Values.
Verifies malformed phone numbers, unusual emails, special characters, and missing contacts.
"""

import unittest
from tests.e2e.tier1_feature_coverage.test_f8_f9_extractor_and_session import (
    extract_contacts,
    RE_PHONE_INDONESIA,
    RE_EMAIL,
)


class TestBoundaryExtractorAndRegex(unittest.TestCase):
    """Test suite for extractor boundaries and edge cases (>= 5 test cases)."""

    def test_tc01_bnd_phone_too_short_is_ignored(self):
        """TC-BND-EXT-01: Verify phone numbers with fewer than 9 digits are ignored."""
        text = "Nomor saya 0812345 pendek sekali."
        result = extract_contacts(text)
        self.assertIsNone(result["citizen_phone"])

    def test_tc02_bnd_phone_too_long_is_ignored(self):
        """TC-BND-EXT-02: Verify digit strings exceeding 14 digits are ignored."""
        text = "NIK atau nomor rekening 081234567890123456 bukan no hp."
        match = RE_PHONE_INDONESIA.search(text)
        self.assertIsNone(match)

    def test_tc03_bnd_landline_prefix_not_matched_as_mobile(self):
        """TC-BND-EXT-03: Verify Indonesian landline area codes (021, 0651) do NOT match 08 mobile regex."""
        landline = "Telepon kantor 0651-123456 atau 021-9876543."
        match = RE_PHONE_INDONESIA.search(landline)
        self.assertIsNone(match)

    def test_tc04_bnd_malformed_email_rejected(self):
        """TC-BND-EXT-04: Verify malformed email strings missing domain/tld are rejected."""
        malformed = ["user@domain", "user@.com", "@domain.com", "user name@domain.com"]
        for email in malformed:
            match = RE_EMAIL.search(email)
            self.assertIsNone(match, f"Malformed email '{email}' should not match RE_EMAIL")

    def test_tc05_bnd_zero_contacts_in_message(self):
        """TC-BND-EXT-05: Verify pure issue query without contacts gracefully returns None."""
        text = "Aplikasi website layanan tidak bisa dibuka sejak semalam."
        result = extract_contacts(text)
        self.assertIsNone(result["citizen_phone"])
        self.assertIsNone(result["citizen_email"])
        self.assertIsNone(result["citizen_name"])
        self.assertEqual(result["issue_summary"], text)

    def test_tc06_bnd_mixed_whitespace_and_parentheses_phone(self):
        """TC-BND-EXT-06: Verify handling of messy phone notation e.g. +62 (08) 12-3456-7890."""
        text = "Hubungi no (+62) 812-3456-7890 jika ada kendala."
        # Clean out parentheses and test
        cleaned = text.replace("(", "").replace(")", "").replace("  ", " ")
        result = extract_contacts(cleaned)
        self.assertEqual(result["citizen_phone"], "+6281234567890")


if __name__ == "__main__":
    unittest.main()
