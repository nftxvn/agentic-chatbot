# Project Execution Plan: Live Chat & Helpdesk Ticket Management System (Human Handoff)

## 1. Objectives
Implement an end-to-end Live Chat & Helpdesk Ticket Management system for Diskominfotik with real-time bi-directional messaging via WebSockets/Laravel Reverb, integrating:
1. Laravel Backend: migrations, models (`chat_tickets`, `chat_ticket_messages`), REST API, broadcasting with Reverb/Pusher protocol.
2. Python AI Service (`python-ai`): `human_escalation` & `human_escalation_followup` intent handling in `rag_service.py` / `tool_router.py`, dispatching internal HTTP payload to Laravel Backend.
3. React Admin Dashboard (`admin-frontend`): Live Chat / Helpdesk page, split-panel interface, real-time WebSocket listener with `laravel-echo`/`pusher-js`.
4. Verification & Testing: E2E dual-track verification and adversarial hardening.

## 2. Phases
- **Phase 0: Survey & Codebase Discovery**
  - Dispatch 3 parallel Explorers:
    - Explorer 1 (Backend): Inspect Laravel app structure, models, migrations, auth, broadcasting setup, reverb/pusher config, existing chat endpoints.
    - Explorer 2 (Python AI): Inspect `rag_service.py`, `tool_router.py`, intent handlers, HTTP client/endpoints, citizen session tracking.
    - Explorer 3 (Frontend): Inspect `admin-frontend` routes, pages, sidebar menu, state management, websocket dependencies, existing API client.
  - Synthesize reports into `PROJECT.md` with complete Feature Inventory, Interface Contracts, and Milestones.

- **Phase 1: Implementation Milestones**
  - Milestone 1: Laravel Backend Ticket & Live Chat Data Model, API, Broadcasting (Reverb/Pusher)
  - Milestone 2: Python AI Service Intent Detection & Laravel Handoff Dispatch
  - Milestone 3: React Admin Dashboard Live Chat UI & WebSocket Real-time Integration
  - Milestone 4: Dual Track E2E Integration Testing & Coverage Hardening

- **Phase 2: Gate & Acceptance Verification**
  - Verify all acceptance criteria from ORIGINAL_REQUEST.md.
  - Final Audit & Sentinel handover.
