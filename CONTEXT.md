# CONTEXT.md — Excel Maintainer

## 1) Project Vision

Local web app (Python + HTML/CSS/JS vanilla) that wraps the **OneDrive Excel online viewer** and provides a **sync-to-local** workflow. Designed for users unfamiliar with computers: minimal steps, big buttons, no jargon.

**Core problem it solves:**
- Excel files live in two places: OneDrive (for editing/sharing) and a local folder (for offline use, COM-based tools, backups).
- Hyperlinks inside the `.xlsx` files break when switching context (local paths vs. OneDrive URLs).
- Non-technical users need a single, obvious interface to open, edit, and save without knowing where the file is.

---

## 2) Core Workflows

### Open & View
1. App starts → shows a simple file list (files registered in `files.json`).
2. User picks a file → app opens it in the embedded **OneDrive Excel Online viewer** (iframe embed URL).
3. User edits directly in the OneDrive viewer (no local copy involved during editing).

### Save to Local
1. User clicks **"Guardar no computador"** (big green button).
2. Backend downloads the current OneDrive version of the file via Microsoft Graph (`/me/drive/items/{id}/content`).
3. Backend runs **hyperlink repair**: replaces OneDrive/SharePoint web URLs in `xl/worksheets/*.xml` with the correct local absolute paths (configured per file in `files.json`).
4. File is written to the configured local folder path.
5. UI shows green success or red error feedback.

### Hyperlink Fix Strategy
- Each registered file has a `link_map` in `files.json`: a list of `{"from": "<onedrive_url_fragment>", "to": "<local_path>"}` pairs.
- The repair step is a zip-level string replacement (no openpyxl write — avoids corruption).
- Local-to-OneDrive direction (if needed in future): reverse the map.

---

## 3) Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, stdlib only + `requests` for Graph API |
| Auth | Microsoft Graph, authorization code + PKCE on loopback (same pattern as BSP-tracker) |
| Frontend | HTML + CSS + JS vanilla (single `index.html` + `static/`) |
| UI launch | `pywebview` (native window) with `webbrowser` fallback |
| Excel viewer | OneDrive embed URL in an `<iframe>` |

---

## 4) File & Folder Layout

```
excel-maintainer/
  app.py                  # entry point (server start, CLI dispatch)
  maintainer/             # backend package
    config.py             # constants, mutable globals
    server.py             # HTTP routes + Handler
    graph.py              # Microsoft Graph auth + file download
    hyperlinks.py         # zip-level hyperlink repair
    files.py              # load/save files.json registry
  static/
    css/theme.css
    css/main.css
    js/main.js
  index.html
  files.json              # registered file registry (NOT in releases)
  graph_config.json       # Graph app credentials (NOT in releases)
  graph_token.json        # cached token (NOT in releases)
  run-dev.bat
  run.bat
  setup.bat
```

---

## 5) files.json Schema

```json
[
  {
    "id": "unique-slug",
    "label": "Nome legível para o utilizador",
    "onedrive_item_id": "<Graph item id>",
    "onedrive_embed_url": "<Office Online embed URL>",
    "local_path": "C:\\Users\\...\\file.xlsx",
    "link_map": [
      { "from": "https://criticalsoftware.sharepoint.com/...", "to": "C:\\Users\\..." }
    ]
  }
]
```

---

## 6) Key Design Rules

- **No openpyxl writes.** Hyperlink repair works at the raw zip/XML level to avoid corrupting charts and validations.
- **OneDrive is the source of truth** for editing. The local copy is a read/offline mirror.
- **One action per screen.** The UI shows the viewer and one prominent save button. No settings buried in menus.
- **Feedback is always visible.** Every action ends with a green (OK) or red (error) banner. No silent failures.
- **Auth is automatic.** Token is cached in `graph_token.json`; re-login only when expired. User never sees OAuth steps day-to-day.

---

## 7) Environment

| Environment | Path | Port |
|---|---|---|
| DEV | `C:\Users\cm-andrade\Desktop\my_projects\excel-maintainer` | 8780 |
| Production (future) | TBD | 8779 |

Local folder for Excel files: configured per file in `files.json` (not a global setting — each file has its own `local_path`).
