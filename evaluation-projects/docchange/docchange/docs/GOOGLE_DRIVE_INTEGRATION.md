# Google Drive integration methods (evaluated before implementation)

| # | Method | Pros | Cons | Fit |
|---|--------|------|------|-----|
| 1 | **Drive API v3 + service account** (read-only scope `drive.readonly`) | Headless, automatable, no browser login; folder just needs to be *shared* with the service-account e-mail; supports `files.list`, `files.export`, `files.get_media`, **`revisions.list/get`** (true version history of Google Docs) | Needs a Google Cloud project + JSON key; revision export only for Google-native Docs; binary files expose only limited revision data | **Recommended** |
| 2 | Drive API v3 + OAuth user consent | Acts as a real user, no sharing step | Interactive consent, token refresh handling, awkward for unattended CI/tests | Good for personal use |
| 3 | Google Drive for desktop (synced folder) or manual download | No credentials in the app; trivially readable as local files | No Drive revisions, sync lag, depends on a desktop client; not a real "connection" | Fallback (supported: `LocalFolderSource`) |
| 4 | MCP / AI-assistant Drive connector (e.g. a Google Drive connector in Claude) | Zero code for interactive exploration, OAuth handled by the host | Bound to the assistant session; not an embeddable, testable app component | Great for exploring/prototyping, not for the shipped app |
| 5 | Google Apps Script web app / Workspace add-on | Runs inside Google, can see document history | Separate runtime & deployment, harder to test automatically | Not chosen |

## Recommendation
**Method 1** (service account, `drive.readonly`). Reasons: unattended and automatically testable, least privilege
(read-only scope makes modification/deletion of originals technically impossible), and it exposes native
revisions. The code also supports the common competition layout of *versioned file names* (`SRS_v1.docx`, `SRS_v2.docx`)
and *one sub-folder per document*.

## Setup (real folder)
1. Google Cloud Console -> enable **Google Drive API** -> create a **service account** -> download JSON key.
2. Share the competition folder with the service account e-mail (Viewer).
3. `pip install google-api-python-client google-auth` (+ `python-docx` for .docx)
4. ```
   export DRIVE_SOURCE=gdrive
   export GDRIVE_FOLDER_ID=<folder id from the URL>
   export GOOGLE_APPLICATION_CREDENTIALS=/path/key.json
   python run.py
   ```
