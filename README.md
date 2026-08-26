# Hermes — Job Search + Auto-Apply (Server + Chrome Extension)

Hermes helps you discover job postings and semi‑automate applications:
- A Flask backend (HTTP API on localhost:8080)
- A Chrome extension that: collects your resume + preferences, runs Google searches, sends discovered job links to the backend, and then helps you open application pages and fill forms with server‑generated actions.

## Prerequisites
- macOS/Linux/Windows
- Python 3.10+ (tested on 3.12)
- Google Chrome (latest) with Extensions “Developer mode” enabled

Optional (only if you plan to extend LLM behavior):
- OpenAI API key or a local LLM endpoint (not required for basic flow)

## Quick Start
1) Clone and enter the project directory
```bash
git clone git@github.com:Favouroked/Hermes.git Hermes
cd Hermes
```

2) Create a virtual environment and install dependencies
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

3) Initialize the database schema
```bash
alembic upgrade head
```

To install the CLI command into the active virtualenv, install Hermes from the
repository root:

```bash
pip install -e .
hermes --help
```

Use `pip install .` instead for a regular, non-editable installation. The
database-backed commands should be run from the directory containing the
intended `jobs_analyzer.db` file.

4) Start the backend server (port 8080)
```bash
python src/web/api.py
```
You should see logs and be able to GET http://localhost:8080/ (returns `{ "online": true }`). CORS is enabled for the extension.

5) Load the Chrome extension
- Open Chrome and go to `chrome://extensions/`
- Enable “Developer mode” (top‑right toggle)
- Click “Load unpacked” and select the `extensions` folder from this repo
- Pin the extension if desired

6) Use the extension
- Click the extension icon to open the popup
- Paste your Resume text and Job Preferences
- Click “Start Job Search” and follow the guidance in the popup

That’s it for setup. See the sections below for the full flow and details.


---

## Backend — How to Run & Configure

### Run
```bash
# From project root, with the virtualenv active
python src/web/api.py
```
- Runs a Flask server on `http://localhost:8080` (see `src/web/api.py`).
- CORS is enabled for ease of local extension interaction.
- A SQLite database file `jobs_analyzer.db` is used in the project root.

### Environment
- The server loads `.env` if present (`dotenv.load_dotenv('.env')`).
- Ollama is the default provider and must be running at `http://localhost:11434`.
- Optional environment settings are `LLM_PROVIDER`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, and `OPENAI_MODEL`.
- LM Studio can be selected with `LLM_PROVIDER=lm_studio`. It uses the OpenAI-compatible endpoint at `http://localhost:1234/v1` by default; configure `LM_STUDIO_MODEL`, `LM_STUDIO_BASE_URL`, and optionally `LM_STUDIO_API_KEY` as needed.
- OpenAI can be selected in the extension with a per-installation API key. A preferred model can also be saved per installation with `llm_model`; if omitted, the selected provider’s configured model is used. If using the API directly, send `llm_provider: "openai"`, `llm_model` (optional), and `openai_key` to `/api/install`.
- `OPENAI_API_KEY` can be used as a server-side fallback for OpenAI requests.
- API keys are stored with the installation record; use a protected local database and do not commit `.env` or database files.

---

## Chrome Extension — Install & Use

### Install
- `chrome://extensions/` → enable Developer mode → Load unpacked → choose the `extensions` folder.
- The extension requires permissions listed in `extensions/manifest.json` (activeTab, scripting, notifications, storage, host access to `http://localhost:8080/*`).

### Use
- Start the backend first.
- Open the popup and provide resume text and job preferences.
- Click “Start Job Search”. The extension opens search pages automatically. Solve any Google captcha if prompted (the extension waits and resumes).
- Return later (or keep the popup open). When status becomes `ready`, click “Start Applying”. Keep closing each application tab after you’re done to proceed to the next.

---

## Troubleshooting
- Extension says it can’t reach the server
  - Ensure the backend is running on `http://localhost:8080`
  - Confirm that macOS firewall or corporate VPN/endpoint security isn’t blocking `localhost`
- Google captcha appears repeatedly
  - Solve the captcha; the extension waits and then resumes automatically
  - Reduce search frequency; keep only one Chrome window focused
- No jobs appear after waiting
  - Open the popup again; it checks `/api/status`
  - Review backend logs for errors while processing
- Tabs don’t advance during applying
  - You must close each application tab to open the next; the background script listens for tab close and advances

## Reprocess job-analysis rows

To rerun selected rows from an existing processing run, filter by the run ID and
one or more processing statuses:

```bash
python scripts/reprocess_job_analysis.py \
  --processing-run-id <run-id> \
  --status failed
```

Repeat `--status` for multiple statuses and use `--limit` to cap the number of
rows. The script processes only rows matching both filters and preserves existing
application actions if a rerun fails.

## Settings CLI

View or update settings for an existing installation from the database-backed
CLI. The command uses the database in the current working directory:

```bash
hermes settings show --installation-id <installation-id>
hermes settings update --installation-id <installation-id> \
  --resume-file path/to/resume.txt \
  --preferences "Remote Python roles in Europe" \
  --llm-provider openai \
  --api-key <provider-api-key> \
  --auto-fill
```

Updates are partial, so omitted settings remain unchanged. Use
`--clear-api-key`, `--clear-resume`, or `--clear-preferences` to clear a
stored value. API keys are masked when settings are displayed.

## Cover-letter CLI

The CLI uses jobs that already have stored page text. Configure an installation
and run generation in the background:

```bash
python -m src.cli cover-letter generate --installation-id <installation-id>
python -m src.cli cover-letter status --run-id <run-id>
python -m src.cli cover-letter stop --run-id <run-id>
```

Use `--resume-file path/to/resume.txt` to override the configured resume and
`--limit N` to cap a run. To review applications interactively, copy each
generated letter and open its link:

```bash
python -m src.cli apply --installation-id <installation-id>
```

Each job’s link is copied first. Press `g` to generate and copy a cover letter,
`gf` to generate a new one if it already exists, Enter after applying to mark a job
processed, `n` to save notes, or `s` to stop. Equivalent wrappers are available
in `scripts/`.

---

## Repository Layout (selected files)
- `extensions/manifest.json` — extension config
- `extensions/popup.html`, `extensions/popup.js` — popup UI and logic
- `extensions/background.js` — opens tabs, orchestrates search/apply flows
- `extensions/content.js` — extracts links on Google, executes form‑fill actions
- `src/web/api.py` — Flask API
- `migrations/` — Alembic database migrations
- `src/jobs/` and `src/processors/` — link/job processing pipeline
- `jobs_analyzer.db` — SQLite database file created at runtime

## License
TBD
