# Dispatch for Worker M3: React Admin Frontend Implementation

## Task Assignment
- Working Directory: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m3
- Authoritative Request: D:/magang/agentic/agentic-chatbot/.agents/teamwork/ORIGINAL_REQUEST.md
- Project Scope Document: D:/magang/agentic/agentic-chatbot/PROJECT.md
- Frontend Survey Report: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_explorer_survey_3/handoff.md
- Project Root: D:/magang/agentic/agentic-chatbot

## Exclusive File Ownership
You exclusively own and may edit files in `admin-frontend/`:
- `admin-frontend/package.json`
- `admin-frontend/src/lib/echo.js`
- `admin-frontend/src/api/tickets.js`
- `admin-frontend/src/pages/LiveChatPage.jsx`
- `admin-frontend/src/components/Layout/AdminLayout.jsx`
- `admin-frontend/src/App.jsx`

## Objective & Scope (Milestone 3: F13 through F17)
1. **Dependencies (`admin-frontend/package.json`)**:
   - Add `"laravel-echo": "^1.17.0"` and `"pusher-js": "^8.4.0"` to dependencies.
2. **WebSocket Echo Configuration (`src/lib/echo.js`)**:
   - Create singleton Echo instance using Reverb / Pusher broadcaster configured for port `8085` (defaulting to window.location.hostname, port `8085`, key `app-key`, scheme `http`/`https`).
3. **API Client (`src/api/tickets.js`)**:
   - Export `ticketsApi` methods: `list(params)`, `stats()`, `get(id)`, `sendMessage(id, data)`, `updateStatus(id, status)`, `assign(id, adminId)` using the Axios client in `src/api/client.js`.
4. **Live Chat Split-Panel UI (`src/pages/LiveChatPage.jsx`)**:
   - Implement the full split-panel interface:
     - Left panel: Search bar, status filter tabs using `SlidingTabs` (All, Open, In Progress, Resolved), unread count badges, ticket cards with relative timestamp (`formatRelativeTime`).
     - Right panel: Selected ticket conversation thread, citizen info header, assign-to-me button, status transition dropdown (Open, In Progress, Resolved), auto-scrolling message bubbles (citizen left, admin right, system note center), canned response buttons, reply textarea with Enter to send.
     - Real-time sync: Connect to `Echo.channel('tickets')` for `.ticket.created` and `.ticket.updated`, and `Echo.channel('ticket.' + selectedTicket.id)` for `.message.sent`.
     - Resilient fallback: Implement periodic polling interval (every 8-10s) when WebSocket is disconnected or degraded.
5. **Route & Navigation Registration**:
   - In `src/App.jsx`, add route `<Route path="/live-chat" element={<LiveChatPage />} />`.
   - In `src/components/Layout/AdminLayout.jsx`, add `{ to: "/live-chat", label: "Live Chat / Helpdesk", icon: ... }` to `NAV_ITEMS` and `QUICK_FEATURES`.
6. **Build Verification**:
   - Run `npm run build` in `admin-frontend/` (or via docker if needed) to ensure zero Vite build errors.
   - Document commands and results in `handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.


## 2026-09-26T10:39:29Z
You are Worker M3: React Admin Frontend Implementation Worker.
Your working directory is: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m3
Execute Milestone 3 (F13 through F17 per PROJECT.md):
1. Add laravel-echo and pusher-js to package.json.
2. Create src/lib/echo.js configuring Echo with Reverb on port 8085.
3. Create src/api/tickets.js for ticket REST calls.
4. Create src/pages/LiveChatPage.jsx implementing the complete split-panel live chat UI with status tabs, conversation stream, reply box, and WebSocket listeners.
5. Register route in src/App.jsx and menu item in src/components/Layout/AdminLayout.jsx.
6. Verify build passes without errors (e.g. npm run build).
7. Write your report to: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m3/handoff.md
Send a message to parent when done.
