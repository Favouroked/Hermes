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

3) Start the backend server (port 8080)
```bash
python src/web/api.py
```
You should see logs and be able to GET http://localhost:8080/ (returns `{ "online": true }`). CORS is enabled for the extension.

4) Load the Chrome extension
- Open Chrome and go to `chrome://extensions/`
- Enable “Developer mode” (top‑right toggle)
- Click “Load unpacked” and select the `extensions` folder from this repo
- Pin the extension if desired

5) Use the extension
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
- No variables are strictly required for the basic flow.
- If you plan to extend LLM usage on the server, you may add vars like `OPENAI_API_KEY` to `.env` and wire them into agents.

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

---

## Repository Layout (selected files)
- `extensions/manifest.json` — extension config
- `extensions/popup.html`, `extensions/popup.js` — popup UI and logic
- `extensions/background.js` — opens tabs, orchestrates search/apply flows
- `extensions/content.js` — extracts links on Google, executes form‑fill actions
- `src/web/api.py` — Flask API
- `src/jobs/` and `src/processors/` — link/job processing pipeline
- `jobs_analyzer.db` — SQLite database file created at runtime

## License
TBD
