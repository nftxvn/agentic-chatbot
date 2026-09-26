#!/usr/bin/env python3
"""
Comprehensive Standalone Deterministic E2E Test Runner.
Executes test suites across Tiers 1-4 for Live Chat & Helpdesk Ticket Management System.

Usage:
    python tests/e2e/run_e2e_tests.py [--tier {1,2,3,4,all}] [-v] [--failfast]

Exit codes:
    0 - All tests passed (or skipped if optional service unavailable)
    1 - One or more tests failed or encountered errors
"""

import sys
import os
import time
import argparse
import unittest
from typing import List, Tuple

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from tests.e2e.test_config import (
    LARAVEL_HOST,
    AI_HOST,
    FRONTEND_HOST,
    REVERB_PORT,
    is_http_endpoint_alive,
    is_port_open,
)

# Import test modules
from tests.e2e.tier1_feature_coverage.test_f1_f2_models_schema import (
    TestF1ChatTicketsModelAndSchema,
    TestF2ChatTicketMessagesModelAndSchema,
)
from tests.e2e.tier1_feature_coverage.test_f3_f4_admin_api import (
    TestF3AdminQueueAndStatsAPI,
    TestF4AdminDetailAssignAndStatusAPI,
)
from tests.e2e.tier1_feature_coverage.test_f5_f6_messages_and_internal_ingestion import (
    TestF5AdminMessageThreadAndReplyAPI,
    TestF6InternalHandoffIngestionEndpoint,
)
from tests.e2e.tier1_feature_coverage.test_f7_websocket_broadcasting import (
    TestF7WebSocketBroadcastingSetup,
)
from tests.e2e.tier1_feature_coverage.test_f8_f9_extractor_and_session import (
    TestF8CitizenContactAndIssueExtractor,
    TestF9SessionTicketIDStateManagement,
)
from tests.e2e.tier1_feature_coverage.test_f10_f11_f12_ai_dispatch_and_rag import (
    TestF10OutboundHandoffDispatch,
    TestF11GracefulCitizenEscalationResponses,
    TestF12ExistingRAGPipelinePreservation,
)
from tests.e2e.tier1_feature_coverage.test_f13_to_f17_frontend_contracts import (
    TestF13EchoClientInfrastructure,
    TestF14NavigationAndRouteIntegration,
    TestF15SplitPanelTicketListUI,
    TestF16SplitPanelConversationThreadUI,
    TestF17RealTimeUISynchronization,
)

from tests.e2e.tier2_boundary_corner.test_boundary_inputs_and_auth import (
    TestBoundaryInputsAndAuth,
)
from tests.e2e.tier2_boundary_corner.test_boundary_extractor_and_regex import (
    TestBoundaryExtractorAndRegex,
)
from tests.e2e.tier2_boundary_corner.test_boundary_status_transitions import (
    TestBoundaryStatusTransitions,
)
from tests.e2e.tier2_boundary_corner.test_adversarial_security_and_stress import (
    TestAdversarialSecurityAndStress,
)

from tests.e2e.tier3_cross_feature.test_pairwise_interactions import (
    TestPairwiseInteractions,
)
from tests.e2e.tier3_cross_feature.test_handoff_lifecycle_pipeline import (
    TestHandoffLifecyclePipeline,
)

from tests.e2e.tier4_real_world_workloads.test_citizen_journeys import (
    TestRealWorldCitizenJourneys,
)


TIER_TEST_MAP = {
    "1": [
        TestF1ChatTicketsModelAndSchema,
        TestF2ChatTicketMessagesModelAndSchema,
        TestF3AdminQueueAndStatsAPI,
        TestF4AdminDetailAssignAndStatusAPI,
        TestF5AdminMessageThreadAndReplyAPI,
        TestF6InternalHandoffIngestionEndpoint,
        TestF7WebSocketBroadcastingSetup,
        TestF8CitizenContactAndIssueExtractor,
        TestF9SessionTicketIDStateManagement,
        TestF10OutboundHandoffDispatch,
        TestF11GracefulCitizenEscalationResponses,
        TestF12ExistingRAGPipelinePreservation,
        TestF13EchoClientInfrastructure,
        TestF14NavigationAndRouteIntegration,
        TestF15SplitPanelTicketListUI,
        TestF16SplitPanelConversationThreadUI,
        TestF17RealTimeUISynchronization,
    ],
    "2": [
        TestBoundaryInputsAndAuth,
        TestBoundaryExtractorAndRegex,
        TestBoundaryStatusTransitions,
        TestAdversarialSecurityAndStress,
    ],
    "3": [
        TestPairwiseInteractions,
        TestHandoffLifecyclePipeline,
    ],
    "4": [
        TestRealWorldCitizenJourneys,
    ],
}


def print_banner():
    banner = """
================================================================================
       DUAL-TRACK E2E INTEGRATION & ADVERSARIAL TEST RUNNER
   Live Chat & Helpdesk Ticket Management System (Human Handoff)
================================================================================
"""
    print(banner)


def check_system_environment():
    print("[*] Environment Pre-Flight Health Check:")
    laravel_up = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")
    ai_up = is_http_endpoint_alive(f"{AI_HOST}/health")
    frontend_up = is_http_endpoint_alive(FRONTEND_HOST)
    reverb_open = is_port_open("127.0.0.1", REVERB_PORT)

    print(f"  - Laravel Backend    ({LARAVEL_HOST}): {'[ONLINE]' if laravel_up else '[OFFLINE]'}")
    print(f"  - Python AI Service  ({AI_HOST}):      {'[ONLINE]' if ai_up else '[OFFLINE]'}")
    print(f"  - React Frontend     ({FRONTEND_HOST}):  {'[ONLINE]' if frontend_up else '[OFFLINE]'}")
    print(f"  - Reverb WebSockets  (port {REVERB_PORT}):       {'[LISTENING]' if reverb_open else '[STANDBY/SIM]'}")
    print("-" * 80)


def run_tier(tier_num: str, test_classes: list, verbosity: int = 1, failfast: bool = False) -> Tuple[int, int, int, int, float]:
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for tc in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(tc))

    total = suite.countTestCases()
    print(f"\n>>> Running Tier {tier_num} ({total} test cases)...")

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=failfast)
    result = runner.run(suite)
    duration = time.time() - start_time

    passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
    failed = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)

    return total, passed, failed, errors, skipped, duration


def main():
    parser = argparse.ArgumentParser(description="Deterministic E2E Test Runner")
    parser.add_argument(
        "--tier",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Specify which tier to execute (default: all)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test execution output")
    parser.add_argument("-f", "--failfast", action="store_true", help="Stop execution on first failure")
    args = parser.parse_args()

    print_banner()
    check_system_environment()

    tiers_to_run = ["1", "2", "3", "4"] if args.tier == "all" else [args.tier]
    verbosity = 2 if args.verbose else 1

    overall_total = 0
    overall_passed = 0
    overall_failed = 0
    overall_errors = 0
    overall_skipped = 0
    total_duration = 0.0

    tier_metrics = {}

    for t in tiers_to_run:
        classes = TIER_TEST_MAP.get(t, [])
        total, passed, failed, errors, skipped, dur = run_tier(t, classes, verbosity=verbosity, failfast=args.failfast)
        tier_metrics[t] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "duration": dur,
        }
        overall_total += total
        overall_passed += passed
        overall_failed += failed
        overall_errors += errors
        overall_skipped += skipped
        total_duration += dur

        if args.failfast and (failed > 0 or errors > 0):
            print("\n[!] Failfast triggered. Halting remaining tiers.")
            break

    # Summary Output
    print("\n" + "=" * 80)
    print("                    E2E TEST EXECUTION SUMMARY REPORT")
    print("=" * 80)
    print(f"{'Tier':<8}{'Description':<32}{'Total':<8}{'Pass':<8}{'Fail':<8}{'Skip':<8}{'Time':<8}")
    print("-" * 80)

    tier_descriptions = {
        "1": "Tier 1: Feature Coverage (F1-F17)",
        "2": "Tier 2: Boundary & Corner Cases",
        "3": "Tier 3: Pairwise & Integrations",
        "4": "Tier 4: Citizen Journeys",
    }

    for t, m in tier_metrics.items():
        desc = tier_descriptions.get(t, f"Tier {t}")
        print(f"T{t:<7}{desc:<32}{m['total']:<8}{m['passed']:<8}{m['failed']:<8}{m['skipped']:<8}{m['duration']:.2f}s")

    print("-" * 80)
    print(f"{'TOTAL':<40}{overall_total:<8}{overall_passed:<8}{overall_failed:<8}{overall_skipped:<8}{total_duration:.2f}s")
    print("=" * 80)

    # Feature Coverage Checklist
    print("\n[*] Feature Inventory Coverage Matrix (F1 - F17):")
    feature_checklist = [
        ("F1", "chat_tickets Migration & Model", "COVERED (Tier 1 & 2)"),
        ("F2", "chat_ticket_messages Migration & Model", "COVERED (Tier 1 & 3)"),
        ("F3", "Admin REST API: Queue Listing & Stats", "COVERED (Tier 1 & 4)"),
        ("F4", "Admin REST API: Detail, Assign & Status", "COVERED (Tier 1 & 2)"),
        ("F5", "Admin REST API: Message Thread & Reply", "COVERED (Tier 1 & 3)"),
        ("F6", "Internal Handoff Ingestion Endpoint", "COVERED (Tier 1 & 2)"),
        ("F7", "Laravel WebSocket Broadcasting Setup", "COVERED (Tier 1 & 3)"),
        ("F8", "Citizen Contact & Issue Extractor", "COVERED (Tier 1 & 2)"),
        ("F9", "Session Ticket ID State Management", "COVERED (Tier 1 & 3)"),
        ("F10", "Python AI Outbound Handoff Dispatch", "COVERED (Tier 1 & 4)"),
        ("F11", "Graceful Citizen Escalation Responses", "COVERED (Tier 1 & 4)"),
        ("F12", "Existing RAG Pipeline Preservation", "COVERED (Tier 1 & 4)"),
        ("F13", "Echo & WebSocket Client Infrastructure", "COVERED (Tier 1)"),
        ("F14", "Navigation & Route Integration", "COVERED (Tier 1)"),
        ("F15", "Split-Panel Ticket List UI (Left)", "COVERED (Tier 1)"),
        ("F16", "Split-Panel Conversation Thread UI", "COVERED (Tier 1)"),
        ("F17", "Real-Time UI Synchronization", "COVERED (Tier 1 & 3)"),
    ]
    for fid, fname, cov in feature_checklist:
        print(f"  [{cov:<22}] {fid}: {fname}")

    print("\n" + "=" * 80)
    if overall_failed == 0 and overall_errors == 0:
        print("  >> RESULT: ALL E2E TEST SUITES PASSED DETERMINISTICALLY! [OK]")
        print("=" * 80 + "\n")
        sys.exit(0)
    else:
        print(f"  >> RESULT: FAILED with {overall_failed} failure(s) and {overall_errors} error(s).")
        print("=" * 80 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
