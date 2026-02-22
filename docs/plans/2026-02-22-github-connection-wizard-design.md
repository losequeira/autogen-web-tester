# GitHub Connection Wizard — Design

**Date:** 2026-02-22
**Status:** Approved

---

## Overview

Add a visible GitHub integration layer to the Source Control panel. Users can connect any workspace to an existing GitHub repo or create a new one via a step-by-step wizard modal. The PAT is encrypted and stored on disk so users don't re-enter it every session.

---

## Storage & Encryption

Each workspace gets a `.github-config.json` sidecar file:

```
~/.autogen/workspaces/<name>/.github-config.json
```

Contents:
```json
{
  "remote_url": "https://github.com/owner/repo.git",
  "token": "<Fernet-encrypted PAT>"
}
```

- **Encryption**: Fernet symmetric encryption via the `cryptography` package (already in `requirements.txt`).
- **Key derivation**: A stable `GITHUB_CONFIG_SECRET` env var. If absent, the app generates a random key and saves it to `~/.autogen/.github_secret` on first use (survives restarts, no manual config required).
- **Gitignore**: `.github-config.json` must be excluded from git (added to workspace `.gitignore` on creation).
- **New module**: `github_config.py` — handles read/write/delete of the config file, keeping it separate from `git_ops.py`.

---

## SCM Header Status Row

A new row at the top of the SCM panel, always visible.

### Disconnected state
```
[ gh-icon ]  Not connected to GitHub  [ Connect ▶ ]
```
- Muted GitHub icon
- Gray "Not connected to GitHub" label
- Accent-colored "Connect" button — opens the wizard modal

### Connected state
```
[ gh-icon ]  owner/repo  ↑3 ↓1  [ ··· ]
```
- Green GitHub icon
- `owner/repo` as a clickable link opening GitHub in a new tab
- Ahead (↑) / behind (↓) counts from `git_ops.get_status()` — hidden when both are zero
- `···` overflow menu:
  - **Sync** — pull then push
  - **Disconnect** — removes `.github-config.json` and `origin` remote
  - **Copy remote URL** — copies to clipboard

### Error state
```
[ gh-icon ]  owner/repo  ⚠ Token invalid — Re-authenticate  [ ··· ]
```
- Shown when a push/pull returns a 401/403 from GitHub
- Re-authenticate option in `···` reopens Step 2 of the wizard pre-filled with the existing remote URL

---

## Wizard Modal

### Step 1 — Choose path

Two equal cards:

| Connect to existing repo | Push to new GitHub repo |
|--------------------------|------------------------|
| Add a GitHub repo as the remote for this workspace | Create a new repo on GitHub and push this workspace |

### Step 2a — Connect to existing repo

Fields:
- **Repository URL** — `https://github.com/owner/repo.git`
- **Personal Access Token** — password input with show/hide toggle; label notes it is stored encrypted on disk

On submit:
1. `GET https://api.github.com/user` — validate token
2. `git remote add origin <url>` (or `set-url` if origin exists)
3. Save config via `github_config.py`
4. Close modal; status row goes green

### Step 2b — Push to new repo

Fields:
- **Personal Access Token** — same as above
- **Repository name** — pre-filled from workspace name (slugified)
- **Visibility** — radio: Public / Private
- **Description** — optional text input

On submit (sequential, with inline progress):
1. `Validating token…` — `GET /user`
2. `Creating repo…` — `POST https://api.github.com/user/repos`
3. `Pushing…` — `git remote add origin <new_url>` + `git push -u origin main`
4. Save config
5. Close modal; status row goes green

Progress shown as spinner + status text in the modal footer. Errors shown inline below the relevant field or in a modal-level error bar.

---

## New Backend Pieces

### `github_config.py`
- `get_config(workspace_path)` → `{remote_url, token}` or `None`
- `save_config(workspace_path, remote_url, token)` → encrypts token, writes file
- `delete_config(workspace_path)` → removes file
- `decrypt_token(workspace_path)` → returns plaintext PAT or `None`

### `git_ops.py` additions
- `add_remote(workspace_path, url, remote='origin')` — adds or updates origin
- `remove_remote(workspace_path, remote='origin')` — removes remote
- `get_remote_url(workspace_path, remote='origin')` → `str | None`

### New API endpoints in `web_ui.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/workspaces/<n>/github/config` | Returns `{connected, remote_url, owner, repo}` (no token) |
| `POST` | `/api/workspaces/<n>/github/connect` | Payload `{remote_url, token}` — validates, saves config, adds remote |
| `POST` | `/api/workspaces/<n>/github/create-repo` | Payload `{token, name, private, description?}` — creates GH repo, sets remote, pushes |
| `DELETE` | `/api/workspaces/<n>/github/disconnect` | Removes config + origin remote |

All endpoints: `@login_required` + `@workspace_access_required`.

---

## Frontend Pieces

### HTML additions (`templates/index.html`)
- GitHub status row inside `#panel-scm` (above existing SCM header buttons)
- `···` overflow menu (dropdown)
- `#github-wizard-modal` — 3 states: step1, step2a, step2b

### CSS additions (`static/css/style.css`)
- `.github-status-row` — flex row, border-bottom
- `.github-status-connected` / `.github-status-disconnected` variants
- `.github-wizard-cards` — side-by-side card layout for step 1
- `.wizard-progress` — footer spinner + status text
- `.github-overflow-menu` — dropdown for `···`

### JS additions (`static/js/app.js`)
- `loadGithubConfig()` — `GET /github/config` on SCM panel open, renders status row
- `openGithubWizard(step)` — shows modal, navigates steps
- `githubConnect(url, token)` — calls `/github/connect`, updates status row
- `githubCreateRepo(token, name, priv, desc)` — calls `/github/create-repo`
- `githubDisconnect()` — calls `DELETE /github/disconnect`, resets status row
- `githubSync()` — pull then push using stored token

---

## Implementation Order

1. `github_config.py` — encryption module
2. `git_ops.py` additions (`add_remote`, `remove_remote`, `get_remote_url`)
3. API endpoints in `web_ui.py`
4. HTML — status row + wizard modal
5. CSS — status row, wizard cards, progress, overflow menu
6. JS — `loadGithubConfig`, wizard flow, connect/create/disconnect/sync
