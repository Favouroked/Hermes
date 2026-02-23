## End‑to‑End Flow
This reflects the current codebase behavior.

### 1) Provide resume and preferences (extension popup)
- Open the popup (`extensions/popup.html`, logic in `extensions/popup.js`).
- The extension creates or loads a unique `installation_id` and shows it.
- You paste:
  - Resume text (plain text)
  - Job preferences (e.g., role focus, remote/on‑site, stacks)
- On “Start Job Search”, the popup calls the backend `POST /api/install` with:
```json
{
  "installation_id": "<id>",
  "resume": "<your resume text>",
  "preferences": "<your preferences>"
}
```
- The backend stores the installation and generates Google search queries (via `LeverAgent`). It returns an array of Google search URLs.

### 2) Run Google searches and collect job links (background + content scripts)
- The background script (`extensions/background.js`) opens each returned Google search URL in a new tab, one by one.
- The content script (`extensions/content.js`) detects Google search result pages, extracts outbound result links across up to 5 pages, and sends links back to the background script.
- The background script then POSTs all collected links to `POST /api/listings` with your `installation_id`.
- Tabs are closed automatically as pages are processed.

### 3) Server processes discovered links
- The server stores and schedules processing of the discovered links (`src/web/api.py` uses a `ProcessPoolExecutor` to trigger `src/jobs/lever.execute`).
- In the popup, status is polled via `POST /api/status`:
  - `{"status": "processing"}` — still crunching
  - `{"status": "google", "urls": [...]}` — initial state when searches must be run (the popup/background will start them)
  - `{"status": "ready", "job_count": N}` — application URLs are ready

### 4) Start applying (user action)
- When status is `ready`, the popup shows the “Start Applying” button.
- Clicking it calls `POST /api/urls` to fetch job application URLs. The extension then:
  - Sequentially opens each job application URL in a new tab (foreground),
  - Waits for you to complete any manual steps,
  - On tab close, marks the job as processed via `PUT /api/job-processed` and opens the next one.

### 5) Auto‑fill assistance on application pages
- When an application page loads, the extension requests actions from the server via `POST /api/filler` with the page URL (and, in some code paths, the page HTML).
- The server responds with a list of actions like:
```json
[
  {"action": "type", "query_selector": "input[name=email]", "value": "you@example.com"},
  {"action": "select", "query_selector": "select#country", "value": "United States"},
  {"action": "click", "query_selector": "button[type=submit]"}
]
```
- The content script executes these actions to help fill the form. You can still adjust answers before submitting.

---

## API Reference (implemented in `src/web/api.py`)

- `GET /` → `{ "online": true }`

- `POST /api/install`
  - Body: `{ installation_id, resume, preferences, openai_key? }`
  - Returns: `{ urls: string[] }` (Google search URLs)

- `POST /api/listings`
  - Body: `{ installation_id, links: string[] }`
  - Returns: `{ status: "success", links_received: number }`

- `POST /api/status`
  - Body: `{ installation_id }`
  - Returns one of:
    - `{ status: "none" }`
    - `{ status: "google", urls: string[] }`
    - `{ status: "processing" }`
    - `{ status: "ready", job_count: number }`

- `POST /api/urls`
  - Body: `{ installation_id }`
  - Returns: `{ urls: string[] }` (application pages; `/apply` is appended when needed)

- `POST /api/filler`
  - Body: `{ url, html, timestamp, installation_id }`
  - Returns: `Action[]` where each action is `{ action: "type" | "click" | "select" | "alert", query_selector?, value? }`

- `PUT /api/job-processed`
  - Body: `{ url, timestamp, installation_id }`
  - Returns: `{ status: "ok" }`

---

## Notes on LLMs (OpenAI vs Local)
- The API accepts an optional `openai_key` in `/api/install` and stores it per installation. The current popup UI doesn’t expose this field yet; you can extend `popup.js` to include it if desired.
- You can configure a local LLaMA path. If you integrate a local model, point the backend agents/processors to that runtime and skip passing an OpenAI key from the extension.
