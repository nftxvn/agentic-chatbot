# TEST_INFRA.md — Comprehensive E2E Testing Infrastructure

**Project**: Live Chat & Helpdesk Ticket Management System (Human Handoff)  
**System Integrity Mode**: Development & Verification  
**Author**: E2E Test Writer Lead  
**Last Updated**: 2026-09-26  

---

## 1. Executive Summary & Testing Philosophy

The Live Chat & Helpdesk Ticket Management System integrates three core services:
1. **Laravel Backend (`laravel-admin`)**: REST API, MySQL models, Sanctum auth, internal token auth, WebSocket broadcasting via Reverb/Pusher protocol.
2. **Python AI Microservice (`python-ai`)**: Intent routing, regex contact extractor, session memory ticket tracking, outbound handoff HTTP dispatch, RAG hybrid retrieval preservation.
3. **React Admin Frontend (`admin-frontend`)**: Split-panel helpdesk UI, WebSocket listeners, real-time ticket state synchronization.

To ensure absolute system correctness, stability, and zero regressions, this test infrastructure establishes a **Dual-Track Opaque-Box E2E Testing Strategy**. The tests treat the system as a collection of interacting black-box components adhering strictly to the formal interface contracts defined in `PROJECT.md` and `ORIGINAL_REQUEST.md`.

### Core Testing Principles
- **Opaque-Box & Requirement-Driven**: Tests validate observable external behaviors, API request/response payloads, status codes, database schema fidelity, and event schemas without relying on private implementation details.
- **Deterministic & Standalone**: Test runs are 100% reproducible and isolated. Every test establishes its own fixture state and cleans up after execution.
- **Zero Third-Party Runtime Dependencies**: The test runner (`tests/e2e/run_e2e_tests.py`) is implemented using Python standard libraries (`unittest`, `urllib`, `json`, `re`, `uuid`, `socket`), ensuring it executes seamlessly on Windows, Linux, CI pipelines, or within Docker without requiring external package installations.
- **Clean Exit Codes**: The test suite exits with code `0` on 100% pass and code `1` on any failure, enabling seamless integration into automated CI/CD gates.

---

## 2. Testing Methodology

The E2E test architecture implements four rigorous testing methodologies across four distinct tiers:

### 2.1 Category-Partition Method (Tier 1: Feature Coverage)
Every feature (F1 through F17) is broken down into functional categories and parameter partitions:
- **Authentication Modes**: Unauthenticated, Sanctum Cookie Authenticated, Internal Bearer Token Authenticated, Invalid/Expired Token.
- **Ticket Statuses**: `open`, `in_progress`, `resolved`, `closed`.
- **Channels**: `widget`, `whatsapp`, `telegram`.
- **Intents**: `human_escalation`, `human_escalation_followup`, RAG queries, FAQ fast-path.
- **Sender Types**: `citizen`, `agent`, `bot`, `system`.
Each partition is covered by at least 5 targeted test cases verifying primary happy-path behavior.

### 2.2 Boundary Value Analysis & Negative Testing (Tier 2: Boundary & Corner Cases)
Verifies resilience against extreme inputs and failure modes:
- **String Length Boundaries**: Empty strings, 1-character strings, 255-character limits, 5,000+ character long queries.
- **Contact Extractor Variations**: Indonesian mobile numbers (`08xx`, `+62xx`, `62xx`, hyphenated, spaced), invalid prefixes, landline numbers, valid and malformed email addresses.
- **Invalid State Transitions**: Attempts to transition tickets to nonexistent statuses, double-closing, or modifying locked records.
- **Adversarial Security Inputs**: SQL injection strings, cross-site scripting (XSS) polyglots, non-ASCII Unicode/emojis, HTML entities.
- **Missing & Null Fields**: Missing mandatory keys (`session_id`, `message`), null payload handling.

### 2.3 Pairwise / Combinatorial Integration (Tier 3: Cross-Feature Interactions)
Validates interactions across service boundaries using 2-way combinatorial test pairs:
- *Intent Detection* $\times$ *Internal Handoff Ingestion* $\times$ *Session State Persistence*.
- *Admin Ticket Queue Listing* $\times$ *Admin Assignment* $\times$ *Admin Message Reply*.
- *Ticket Creation* $\times$ *WebSocket Broadcast (`TicketCreated`)* $\times$ *Status Update (`TicketUpdated`)*.
- *Citizen First Escalation* $\times$ *Follow-Up Message in Same Session* $\times$ *Single Ticket Thread Correlation*.

### 2.4 Real-World Workload Scenarios (Tier 4: Citizen Journeys)
End-to-end multi-turn scenarios mirroring authentic citizen and government agency interactions:
- **Journey 1: SPBE Portal Authentication Failure** (Citizen escalation with name, phone, agency, followed by admin resolution).
- **Journey 2: WhatsApp Citizen Multi-Turn Dialogue** (General inquiry $\to$ Escalation intent $\to$ Follow-up additional context $\to$ Thread consolidation).
- **Journey 3: High-Volume Concurrent Escalations** (Multiple distinct citizens submitting simultaneous tickets across different agencies).
- **Journey 4: Full Ticket Lifecycle & Audit Trail** (Creation $\to$ Assignment $\to$ Internal Note vs Public Reply $\to$ Resolution $\to$ Closed state immutability).
- **Journey 5: Non-Escalation Citizen Queries (Anti-False-Positive)** (Ensuring standard municipal regulations and FAQ queries route cleanly to RAG without creating phantom tickets).

---

## 3. Feature Inventory & Test Mapping (F1 - F17)

| Feature # | Feature Name | Primary Scope | Corresponding Test Files |
|-----------|--------------|---------------|--------------------------|
| **F1** | `chat_tickets` Migration & Model | Schema validation, ticket number generation, priority, timestamps | `test_f1_f2_models_schema.py`, `test_boundary_inputs_and_auth.py` |
| **F2** | `chat_ticket_messages` Migration & Model | Schema, sender types, internal notes flag, relations | `test_f1_f2_models_schema.py`, `test_pairwise_interactions.py` |
| **F3** | Admin REST API: Queue Listing & Stats | `GET /api/tickets`, search, status filter, pagination, stats | `test_f3_f4_admin_api.py`, `test_citizen_journeys.py` |
| **F4** | Admin REST API: Detail, Assign & Status | `GET /api/tickets/{id}`, assign admin, patch status | `test_f3_f4_admin_api.py`, `test_boundary_status_transitions.py` |
| **F5** | Admin REST API: Message Thread & Reply | `GET/POST /api/tickets/{id}/messages`, message broadcast | `test_f5_f6_messages_and_internal_ingestion.py`, `test_handoff_lifecycle_pipeline.py` |
| **F6** | Internal Handoff Ingestion Endpoint | `POST /api/v1/internal/chat-tickets`, `auth.internal` Bearer token | `test_f5_f6_messages_and_internal_ingestion.py`, `test_boundary_inputs_and_auth.py` |
| **F7** | Laravel WebSocket Broadcasting Setup | Reverb/Pusher port 8085, `TicketCreated`, `TicketMessageSent`, `TicketUpdated` | `test_f7_websocket_broadcasting.py`, `test_handoff_lifecycle_pipeline.py` |
| **F8** | Citizen Contact & Issue Extractor | Regex parser: Indonesian phone, email, agency, name, issue | `test_f8_f9_extractor_and_session.py`, `test_boundary_extractor_and_regex.py` |
| **F9** | Session Ticket ID State Management | Memory tracking of active ticket ID across conversation turns | `test_f8_f9_extractor_and_session.py`, `test_pairwise_interactions.py` |
| **F10** | Python AI Outbound Handoff Dispatch | Resilient HTTP POST to Laravel internal endpoint | `test_f10_f11_f12_ai_dispatch_and_rag.py`, `test_citizen_journeys.py` |
| **F11** | Graceful Citizen Escalation Responses | Contextual canned responses, Call Center 112 / Balai Kota info | `test_f10_f11_f12_ai_dispatch_and_rag.py`, `test_citizen_journeys.py` |
| **F12** | Existing RAG Pipeline Preservation | Hybrid retrieval, document extraction, FAQ fast-path integrity | `test_f10_f11_f12_ai_dispatch_and_rag.py`, `test_citizen_journeys.py` |
| **F13** | Echo & WebSocket Client Infrastructure | Port 8085 config, event subscription contract, polling fallback | `test_f13_to_f17_frontend_contracts.py`, `test_f7_websocket_broadcasting.py` |
| **F14** | Navigation & Route Integration | `/live-chat` route, sidebar NAV_ITEMS, QUICK_FEATURES | `test_f13_to_f17_frontend_contracts.py` |
| **F15** | Split-Panel Ticket List UI (Left Panel) | Filter tabs (All, Open, In Progress, Resolved), search, badges | `test_f13_to_f17_frontend_contracts.py` |
| **F16** | Split-Panel Conversation Thread UI (Right Panel) | Header, status dropdown, assign button, bubbles, reply bar | `test_f13_to_f17_frontend_contracts.py` |
| **F17** | Real-Time UI Synchronization | Auto-insert incoming tickets, instant message append | `test_f13_to_f17_frontend_contracts.py`, `test_handoff_lifecycle_pipeline.py` |
| **F18** | End-to-End Multi-Tier Verification | Comprehensive cross-tier execution and regression validation | `run_e2e_tests.py`, `test_citizen_journeys.py` |

---

## 4. Test Directory Layout

```
D:/magang/agentic/agentic-chatbot/tests/e2e/
├── __init__.py                                 # Package marker
├── test_config.py                              # Base configuration, API endpoints, tokens, helpers
├── run_e2e_tests.py                            # Standalone deterministic runner with clean exit codes
│
├── tier1_feature_coverage/                     # Tier 1: >=5 test cases per feature (F1-F17)
│   ├── __init__.py
│   ├── test_f1_f2_models_schema.py             # F1, F2: Database models, schemas, and fields
│   ├── test_f3_f4_admin_api.py                 # F3, F4: Admin queue, stats, detail, status, assign
│   ├── test_f5_f6_messages_and_internal_ingestion.py # F5, F6: Thread replies, internal handoff endpoint
│   ├── test_f7_websocket_broadcasting.py       # F7: Reverb/Pusher broadcast channel and event contracts
│   ├── test_f8_f9_extractor_and_session.py     # F8, F9: Regex contact parser and session ticket cache
│   ├── test_f10_f11_f12_ai_dispatch_and_rag.py # F10, F11, F12: AI dispatch, escalation messages, RAG integrity
│   └── test_f13_to_f17_frontend_contracts.py   # F13-F17: UI contracts, Echo config, routes, layout
│
├── tier2_boundary_corner/                      # Tier 2: Boundary, corner, and adversarial stress cases
│   ├── __init__.py
│   ├── test_boundary_inputs_and_auth.py        # Token tampering, oversized payloads, missing fields
│   ├── test_boundary_extractor_and_regex.py    # Malformed phones, unusual emails, complex Indonesian text
│   ├── test_boundary_status_transitions.py     # Invalid status values, unauthorized transitions
│   └── test_adversarial_security_and_stress.py # SQL injection, XSS polyglots, Unicode/emojis, rapid bursts
│
├── tier3_cross_feature/                        # Tier 3: Pairwise & multi-step subsystem integrations
│   ├── __init__.py
│   ├── test_pairwise_interactions.py           # Combinatorial pairs (Intent x Ingestion x Channel)
│   └── test_handoff_lifecycle_pipeline.py      # Full lifecycle: Escalation -> Ingest -> Broadcast -> Reply
│
└── tier4_real_world_workloads/                 # Tier 4: Realistic citizen journeys & high-load simulation
    ├── __init__.py
    └── test_citizen_journeys.py                # SPBE issue, WhatsApp multi-turn, queue search, anti-false-positive
```

---

## 5. Execution Instructions

### Standalone Runner (Recommended)
Run all tiers deterministically from the workspace root:
```bash
python tests/e2e/run_e2e_tests.py
```

### Run by Specific Tier
```bash
# Tier 1 only (Feature Coverage)
python tests/e2e/run_e2e_tests.py --tier 1

# Tier 2 only (Boundary & Corner Cases)
python tests/e2e/run_e2e_tests.py --tier 2

# Tier 3 only (Cross-Feature Interactions)
python tests/e2e/run_e2e_tests.py --tier 3

# Tier 4 only (Real-World Workloads)
python tests/e2e/run_e2e_tests.py --tier 4
```

### Standard Python Unittest Runner
```bash
python -m unittest discover tests/e2e
```

### Pytest (When available)
```bash
pytest tests/e2e -v
```

---

## 6. Exit Codes & Reporting Contract
- **Exit Code 0**: All test cases executed and passed with 100% success.
- **Exit Code 1**: One or more test assertions failed, or an unhandled exception occurred.
- **Summary Output**: The test runner prints a structured table showing:
  - Total tests executed
  - Count of passed, failed, and skipped tests
  - Execution duration in seconds
  - Per-tier breakdown
  - Comprehensive feature coverage checklist
