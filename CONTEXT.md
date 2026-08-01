# CONTEXT.md — Excel Maintainer

## 1) Project Vision

Local web app (Python + HTML/CSS/JS vanilla) that provides a **copy-to-server** workflow between two local folders, configurable from the app itself. Designed for users unfamiliar with computers: minimal steps, big buttons, no jargon.

**Core problem it solves:**
- Excel files are edited in one folder (the "original" folder, recursively — subfolders included) and need a synced copy in another (the "server" folder), for offline use, COM-based tools, or backups.
- Hyperlinks inside the `.xlsx` files break when the folder path changes (original path vs. server path).
- Non-technical users need a single, obvious button to copy the current files across, with hyperlinks fixed automatically, and a simple way to point the app at their own two folders instead of the default `for_testing_original/`/`for_testing_server/` pair.

---

## 2) Core Workflow

### Edit
1. User opens and edits files directly in desktop Excel, inside the original folder (including subfolders). The app is not involved in editing.

### Copy to Server
1. App starts → shows a simple list of every `.xlsx` file found anywhere under the original folder (recursive), each tagged Synced / Outdated / New relative to the server folder, nested files shown with their folder as a muted prefix. A search box above the list filters it by file name (matching the full relative path) as the user types.
2. User clicks **"Copiar para o servidor"** on a file (or "Copiar tudo" for all of them).
3. Backend reads the file from the original folder, runs **hyperlink repair** (rewrites any hyperlink pointing at the original folder's absolute path so it points at the server folder instead), and writes the result into the server folder under the same relative path, creating subfolders as needed to mirror the structure.
4. UI shows green success or red error feedback, then refreshes the file list.

### Configuring the folders
1. User clicks the **⚙ Definições** button → a modal shows the current original/server folder paths.
2. Each has a text field plus an **"Escolher pasta..."** button (native folder picker via pywebview; falls back to manual typing in browser mode).
3. Saving validates both paths are given and aren't equal or nested inside each other (case-insensitively), creates them if missing, persists them to `paths.json`, and applies them immediately — no restart needed.
4. Either folder may be a local path or a network (UNC) path such as `\\SERVIDOR\Partilha\Pasta`. If the network location is unreachable (WiFi down, wrong server name, no permission), saving fails with a plain-Portuguese message naming the folder instead of a raw OS error.

### Updating the app
1. On every launch (outside DEV mode) `maintainer/updater.py` fetches the remote tags and, if HEAD is behind the latest tag, pulls and restarts the process in place.
2. The user can also force this from the UI with the **"Verificar atualizações"** button (`POST /api/update`), which works in DEV mode too and reports "already up to date", the applied update (followed by an automatic restart), or a plain-Portuguese error.

### Hyperlink Fix Strategy
- The substitution pairs are derived directly from the two folder paths (`hyperlinks.build_link_map`), covering backslash, forward-slash, and percent-encoded spellings — no per-file configuration needed.
- The repair step is a zip-level string replacement (no openpyxl write — avoids corruption).
- Scope is `xl/worksheets/*.xml` and `xl/sharedStrings.xml` — this covers `=HYPERLINK()` formulas and plain-text cell values, which is what production files actually use (confirmed with the user). Native "Insert Hyperlink" targets (stored in `xl/worksheets/_rels/*.rels`) are out of scope but not needed.

---

## 3) Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, stdlib only |
| Frontend | HTML + CSS + JS vanilla (single `index.html` + `static/`) |
| UI launch | `pywebview` (native window) with `webbrowser` fallback |

---

## 4) File & Folder Layout

```
excel-maintainer/
  app.py                  # entry point (applies settings, server start, CLI dispatch: sync)
  maintainer/             # backend package
    config.py             # constants, mutable globals (ORIGINAL_DIR, SERVER_DIR, ...)
    settings.py           # persist/apply the configured original+server folders (paths.json)
    server.py             # HTTP routes + Handler
    sync.py               # recursively discover files, sync status, copy + repair
    hyperlinks.py          # zip-level hyperlink repair + link-map builder
    updater.py            # git-tag update check: auto on launch + manual (/api/update)
  static/
    css/theme.css
    css/main.css
    js/main.js
  index.html
  for_testing_original/   # default working folder (gitignored xlsx incl. subfolders, kept via .gitkeep)
  for_testing_server/     # default synced-copy folder (gitignored xlsx incl. subfolders, kept via .gitkeep)
  paths.json              # user's configured folder paths (gitignored, machine-specific)
  run-dev.bat
  run.bat
  setup.bat              # installs pywebview and creates the desktop shortcut
  create_shortcut.ps1    # builds the "Excel Maintainer" desktop shortcut (called by setup.bat)
  make_release.bat
```

---

## 5) Key Design Rules

- **No openpyxl writes.** Hyperlink repair works at the raw zip/XML level to avoid corrupting charts and validations.
- **The original folder is the source of truth.** The server folder is only ever written by the sync action.
- **The two folders must never be equal or nested.** Enforced on save, since that would make the recursive scan treat synced output as new input.
- **One action per screen.** The UI shows the file list, sync buttons, and a settings modal for the two folder paths. No settings buried in menus.
- **Feedback is always visible.** Every action ends with a green (OK) or red (error) banner. No silent failures.
- **No accounts, no auth.** Both folders are local; there is nothing to sign in to.

---

## 6) Environment

| Environment | Path | Port |
|---|---|---|
| DEV | `C:\Users\cm-andrade\Desktop\my_projects\excel-maintainer` | 8780 |
| Production (future) | TBD | 8779 |

`for_testing_original/` and `for_testing_server/` at the repo root are only the defaults — both folders are user-configurable from the app's settings modal (not per-file configuration; the pair is global and persisted in `paths.json`).
