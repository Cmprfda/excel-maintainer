# Excel Maintainer — Instructions for AI Assistant

Local web app that wraps the OneDrive Excel Online viewer and provides a one-click **sync-to-local** workflow with automatic hyperlink repair. Target user is non-technical; UI must be dead simple.

> **Language:** respond in **English**.

---

## Model Workflow for New Implementations

1. **Plan — main assistant:** design the implementation plan.
2. **Implement — Opus:** spawn subagent `model: opus` to write the code.
3. **Bug review — Sonnet:** spawn subagent `model: sonnet` to review for bugs.

Trivial edits (one-liners, typos) skip the pipeline.

---

## Quick Commands

- **Start DEV (port 8780):** `.\run-dev.bat`
- **Validate syntax:** `python -m py_compile app.py` + `Get-ChildItem maintainer\*.py | ForEach-Object { python -m py_compile $_.FullName }`
- **Test Graph download:** `python app.py download <file-id>` (CLI, no server)

---

## Architecture

- **`app.py`:** thin entry point — console encoding, server dispatch, CLI commands.
- **`maintainer/` package:**
  - `config` — constants, mutable globals (`DEV_MODE`, `SERVER_PORT`). Always read as `config.X`.
  - `server` — HTTP routes (`/`, `/api/files`, `/api/save`, `/api/graph`).
  - `graph` — Microsoft Graph auth (PKCE loopback, same pattern as BSP-tracker) + file download (`/me/drive/items/{id}/content`).
  - `hyperlinks` — zip-level hyperlink repair (raw XML string replacement, never openpyxl writes).
  - `files` — load/save `files.json` registry.
- **`index.html` + `static/`:** single-page UI. One `<iframe>` for the OneDrive embed + one big save button. No frameworks.
- **`files.json`:** registry of Excel files (OneDrive item ID, embed URL, local path, link_map). Never include in releases.
- **`graph_config.json` / `graph_token.json`:** OAuth credentials and cached token. Never include in releases.

---

## UI Rules

- **One action per screen.** Sidebar/list to pick file; main area = iframe viewer + "Guardar no computador" button.
- **Green = success, red = error.** Every action ends with a visible banner.
- **Large, labelled controls.** Minimum font size 16px for interactive elements.
- **No jargon.** Labels in plain Portuguese. "Guardar no computador" not "Sync local copy".

---

## Hyperlink Repair Rules

- Repair happens **at zip level** (read `.xlsx` as zip, string-replace in `xl/worksheets/*.xml` and `xl/sharedStrings.xml`, rewrite zip).
- **Never use openpyxl to write** — it destroys charts, formatting, and data validations.
- Each file's `link_map` in `files.json` defines the substitution pairs (OneDrive URL fragment → local path).
- After repair, verify the zip is valid (`zipfile.is_zipfile`).

---

## Graph Auth

- Authorization code + PKCE on loopback (`http://localhost:<port>/auth/callback`), same pattern as BSP-tracker.
- Scopes: `Files.Read` (read-only download sufficient for the save workflow).
- Token cached in `graph_token.json`; refresh automatically on expiry.
- All Graph endpoints are localhost-only (`/api/graph`).

---

## Safety Rules

1. **Never write via openpyxl.** Hyperlink repair is zip/XML level only.
2. **`files.json` is local state** — never ship in a release zip.
3. **No BOM in JSON** — write with Python UTF-8 without BOM.
4. **Feedback always visible** — no silent failures; log to `maintainer.log`.

---

## Environment & Paths

| Env | Path | Port |
|---|---|---|
| DEV | `C:\Users\cm-andrade\Desktop\my_projects\excel-maintainer` | 8780 |

Excel files: each has its own `local_path` in `files.json`. No global local folder.
