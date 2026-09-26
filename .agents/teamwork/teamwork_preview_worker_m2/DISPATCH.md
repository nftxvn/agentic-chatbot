# Dispatch for Worker M2: Python AI Service Implementation

## Task Assignment
- Working Directory: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m2
- Authoritative Request: D:/magang/agentic/agentic-chatbot/.agents/teamwork/ORIGINAL_REQUEST.md
- Project Scope Document: D:/magang/agentic/agentic-chatbot/PROJECT.md
- Python AI Survey Report: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_explorer_survey_2/handoff.md
- Project Root: D:/magang/agentic/agentic-chatbot

## Exclusive File Ownership
You exclusively own and may edit files in `python-ai/`:
- `python-ai/app/config.py`
- `python-ai/app/services/tool_router.py`
- `python-ai/app/services/session_memory.py`
- `python-ai/app/services/rag_service.py`
- `python-ai/app/services/backend_client.py`
- `python-ai/test_rag_audit_fixes.py`

## Objective & Scope (Milestone 2: F8 through F12)
1. **Configuration (`app/config.py`)**:
   - Add `LARAVEL_API_URL: str = os.getenv("LARAVEL_API_URL", "http://localhost:8000")`.
2. **Citizen Contact Information Extractor (`app/services/tool_router.py`)**:
   - Implement `extract_citizen_contact_info(text: str) -> dict[str, Any]` extracting name, Indonesian phone (08xx, +62xx), email, agency/instansi, and issue summary per survey recommendation.
3. **Outbound Laravel Dispatch Client (`app/services/backend_client.py`)**:
   - Implement `dispatch_chat_ticket(...)` that sends `POST /api/v1/internal/chat-tickets` with `Authorization: Bearer <INTERNAL_API_TOKEN>`.
   - Wrap in try/except with 3-4s timeout to prevent hanging the chat stream if backend is temporarily slow.
4. **Session Ticket State (`app/services/session_memory.py`)**:
   - Implement `set_session_ticket_id(session_id, ticket_id)` and `get_session_ticket_id(session_id)`.
5. **RAG Service Integration (`app/services/rag_service.py`)**:
   - In `generate_response(...)`:
     - When `intent == "human_escalation"`: extract contact info -> call `dispatch_chat_ticket` -> store `ticket_id` in session memory -> return graceful citizen response.
     - When `intent == "human_escalation_followup"`: extract contact info -> retrieve `ticket_id` -> call `dispatch_chat_ticket` with `existing_ticket_id=ticket_id` -> return graceful acknowledgement.
6. **Tests & Verification**:
   - In `python-ai/test_rag_audit_fixes.py`, add unit tests verifying contact info extraction, intent routing, and mocked ticket dispatching.
   - Run tests: `python -m unittest test_rag_audit_fixes -v` and `python -m unittest test_alur -v` in `python-ai/` to ensure 100% pass without breaking RAG or extraction.
   - Test against live backend: test asking "saya ingin bicara dengan petugas" and verify a ticket is created in Laravel backend.
   - Document commands and results in `handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.


## 2026-09-26T10:39:29Z
You are Worker M2: Python AI Service Implementation Worker.
Your working directory is: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m2
You MUST read:
- ORIGINAL_REQUEST.md at: D:/magang/agentic/agentic-chatbot/.agents/teamwork/ORIGINAL_REQUEST.md
- PROJECT.md at: D:/magang/agentic/agentic-chatbot/PROJECT.md
- Survey Report at: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_explorer_survey_2/handoff.md
- Your dispatch at: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m2/DISPATCH.md

Your exclusive file boundaries in python-ai/:
- app/config.py
- app/services/tool_router.py
- app/services/session_memory.py
- app/services/rag_service.py
- app/services/backend_client.py
- test_rag_audit_fixes.py

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Execute Milestone 2 (F8 through F12 per PROJECT.md):
1. Add LARAVEL_API_URL to config.py.
2. Implement extract_citizen_contact_info in tool_router.py.
3. Implement dispatch_chat_ticket in backend_client.py with Bearer token authentication and error handling.
4. Implement ticket ID session memory tracking in session_memory.py.
5. Integrate dispatch in rag_service.py for human_escalation and human_escalation_followup.
6. Run unit tests in python-ai/ (test_rag_audit_fixes.py and test_alur.py) to confirm 100% pass without breaking existing RAG/FAQ functionalities.
7. Write your report to:
D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m2/handoff.md
Send a message to parent when done.
