# Excel Maintainer — Instructions for AI Assistant

Local web app that provides a one-click **copy-to-server** workflow between two local folders (configurable from the app itself, defaulting to `for_testing_original/`/`for_testing_server/`), with automatic hyperlink repair. The user edits Excel files directly (in desktop Excel) inside the original folder, including in subfolders; the app copies them into the server folder (mirroring subfolder structure), rewriting any hyperlinks that point at the original folder's path so they point at the server folder instead. Target user is non-technical; UI must be dead simple.

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
- **Test sync (CLI, no server):** `python app.py sync [filename.xlsx]` — syncs one file, or every `.xlsx` in `for_testing_original/` if the filename is omitted.
- **Publish release:** `.\make_release.bat v1.2.3` — commits, tags, and pushes to GitHub

---

## Architecture

- **`app.py`:** thin entry point — console encoding, applies persisted settings (`settings.load()`) before anything else runs, server dispatch, CLI commands (`sync`, or default: start server).
- **`maintainer/` package:**
  - `config` — constants, mutable globals (`DEV_MODE`, `SERVER_PORT`, `ORIGINAL_DIR`, `SERVER_DIR`). Always read as `config.X` — `ORIGINAL_DIR`/`SERVER_DIR` can change at runtime via `/api/settings`, so never capture them into a local variable that outlives a single call. Both directories are auto-created on import (as defaults) and again by `settings.load()`/`settings.save()` (as whatever the user configured).
  - `settings` — persists the user's chosen original/server folders to `paths.json` and applies them onto `config.ORIGINAL_DIR`/`config.SERVER_DIR` (`load`, `save`). Rejects equal or nested folder pairs (case-insensitively, since the filesystem is).
  - `server` — HTTP routes (`/`, `/static/...`, `/api/files`, `/api/sync`, `/api/sync-all`, `/api/settings` GET/POST, `/api/pick-folder`).
  - `sync` — recursively discovers `.xlsx` files under `ORIGINAL_DIR` (including subfolders, skipping dot-directories), reports sync status against `SERVER_DIR` (`list_files`), and performs the copy + hyperlink repair while mirroring the subfolder structure (`sync_file`, `sync_all`). `_resolve_within` guards every path against traversal/absolute-path tricks and resolves symlinks before checking containment.
  - `hyperlinks` — zip-level hyperlink repair (raw XML string replacement, never openpyxl writes) + `build_link_map(original_dir, server_dir)` which derives the substitution pairs from the two folder paths — recomputed fresh on every sync, never cached, since the paths can change at runtime.
- **`index.html` + `static/`:** single-page UI. A file list (nested paths shown as folder-prefix + filename) with per-row "copy to server" buttons, one "copy all" button, and a settings modal (folder pickers backed by a native pywebview dialog, with a manual-typing fallback in browser mode). No frameworks, no iframe/viewer (editing happens in desktop Excel, not in-app).
- **`for_testing_original/`:** the default original/working folder — edited directly in Excel. Can be repointed elsewhere via the settings modal.
- **`for_testing_server/`:** the default "deployed" copy folder — only ever written by the sync action, never edited by hand. Can be repointed elsewhere via the settings modal.

There is no OneDrive/Microsoft Graph integration and no `files.json` registry — files are discovered by scanning `ORIGINAL_DIR` directly, not from a persisted list. `paths.json` only stores the two folder paths, not file metadata.

---

## UI Rules

- **One action per screen.** A single list of files, each with a "copy to server" action; one "copy all" action at the top.
- **Green = success, red = error.** Every action ends with a visible banner.
- **Large, labelled controls.** Minimum font size 16px for interactive elements.
- **No jargon.** Labels in plain Portuguese.

---

## Hyperlink Repair Rules

- Repair happens **at zip level** (read `.xlsx` as zip, string-replace in `xl/worksheets/*.xml` and `xl/sharedStrings.xml`, rewrite zip).
- **Never use openpyxl to write** — it destroys charts, formatting, and data validations.
- The substitution pairs come from `hyperlinks.build_link_map(config.ORIGINAL_DIR, config.SERVER_DIR)` — not a per-file registry — covering the backslash, forward-slash, and percent-encoded spellings of the folder path.
- After repair, verify the zip is valid (`zipfile.is_zipfile`).
- Confirmed with the user: production files reference paths via `=HYPERLINK()` formulas or plain-text cell values, never via Excel's native "Insert Hyperlink" (which stores its target in `xl/worksheets/_rels/sheetN.xml.rels`, outside the current scan scope). Both formulas and plain values are inline in the sheet XML or `sharedStrings.xml`, so the current `xl/worksheets/*.xml` + `xl/sharedStrings.xml` scope is sufficient — no need to widen it to `.rels` files.

---

## Safety Rules

1. **Never write via openpyxl.** Hyperlink repair is zip/XML level only.
2. **No BOM in JSON** — write with Python UTF-8 without BOM.
3. **Feedback always visible** — no silent failures; log to `maintainer.log`.
4. **The server folder is only ever written by the sync action** — never edited by hand, never treated as a source of truth.
5. **The original and server folders must never be equal or nested inside each other** — `settings.save()` enforces this, since a nested/equal pair would make the recursive scan treat already-synced output as new input, corrupting the tree on repeated syncs.

---

## Environment & Paths

| Env | Path | Port |
|---|---|---|
| DEV | `C:\Users\cm-andrade\Desktop\my_projects\excel-maintainer` | 8780 |

Excel files live inside the configured original/server folders (defaulting to `for_testing_original/`/`for_testing_server/` at the repo root, both `.gitignore`d for `*.xlsx` at any depth, kept trackable via `.gitkeep`), including in subfolders. No per-file configuration — the folder pair is global, and can be changed from the running app via the settings modal (persisted in `paths.json`, itself gitignored since it holds a machine-specific absolute path).
