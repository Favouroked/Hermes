# Hermes Job Search Chrome Extension

This Chrome extension automates the process of discovering job listings by searching Google and extracting relevant links.

## Features

- **Unique Installation ID**: Each extension installation gets a unique identifier
- **Resume & Preferences Input**: Users provide their resume text and job preferences
- **Automated Google Search**: Extension receives Google search URLs from the backend and processes them
- **Captcha Handling**: Detects Google captchas and waits for user to solve them
- **Link Extraction**: Automatically extracts all job-related links from Google search results
- **24-Hour Cooldown**: After processing, users are asked to check back in 24 hours

## Architecture

### Files

1. **manifest.json** - Extension configuration
2. **popup.html** - Extension homepage UI
3. **popup.js** - Popup logic and API communication
4. **background.js** - Background service worker for coordination
5. **content.js** - Content script for Google search page processing

### Workflow

1. User opens extension popup
2. Extension generates/retrieves unique installation ID
3. User enters resume text and job preferences
4. User clicks "Start Job Search"
5. Popup sends data to `/api/install` endpoint
6. Backend returns list of Google search URLs
7. Background script opens URLs sequentially in new tabs
8. For each tab:
   - Content script detects if it's a Google search page
   - Checks for captcha presence
   - If captcha detected, waits for user to solve it
   - Once resolved (or no captcha), extracts all search result links
   - Sends links to background script
   - Background script calls `/api/listings` with the links
   - Tab is closed and next URL is processed
9. After all URLs processed, completion message is shown
10. Extension prevents new searches for 24 hours

## Backend API Endpoints

### POST /api/install

Receives installation data and returns Google search URLs.

**Request:**
```json
{
  "installation_id": "hermes_1234567890_abc123",
  "resume": "Software Engineer with 5 years experience...",
  "preferences": "Remote positions, Python, full-time..."
}
```

**Response:**
```json
{
  "urls": [
    "https://www.google.com/search?q=software+engineer+jobs+remote",
    "https://www.google.com/search?q=python+developer+jobs"
  ]
}
```

### POST /api/listings

Receives extracted links from Google search pages.

**Request:**
```json
{
  "installation_id": "hermes_1234567890_abc123",
  "links": [
    "https://example.com/job1",
    "https://linkedin.com/jobs/view/123456"
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "links_received": 2
}
```

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `extensions` folder
5. Extension icon should appear in toolbar

## Usage

1. Make sure the backend server is running:
   ```bash
   python src/web/api.py
   ```

2. Click the Hermes extension icon in Chrome toolbar

3. Enter your resume text and job preferences

4. Click "Start Job Search"

5. The extension will:
   - Open Google search pages in new tabs
   - Extract job listing links automatically
   - Handle any captchas (you'll need to solve them manually)
   - Close tabs after processing

6. Wait for the completion message

7. Check back in 24 hours for results

## Technical Details

### Captcha Detection

The content script checks for:
- reCAPTCHA iframes
- "Unusual traffic" messages
- Google's /sorry/ page
- Various captcha-related DOM elements

### Link Extraction

The content script extracts links by:
- Finding all anchor elements on the page
- Filtering out Google's own navigation/service links
- Checking if links are within search result containers
- Removing duplicates

### State Management

The extension uses Chrome's local storage to track:
- Installation ID (persistent across sessions)
- Processing state (prevents concurrent searches)
- Completion timestamp (enforces 24-hour cooldown)

## Testing

Run the API test script:
```bash
python test_extension_api.py
```

This will test both `/api/install` and `/api/listings` endpoints.

## Future Enhancements

- LLM integration to generate better search queries from resume/preferences
- Database storage for extracted links
- More sophisticated link filtering
- Support for other search engines
- Job application tracking
