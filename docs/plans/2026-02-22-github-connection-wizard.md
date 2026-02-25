# GitHub Connection Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a visible GitHub connection status row to the SCM panel and a 2-step wizard modal to connect a workspace to an existing GitHub repo or create a new one, with the PAT stored encrypted on disk.

**Architecture:** A new `github_config.py` module handles Fernet-encrypted PAT storage per workspace. Three new `git_ops.py` functions manage the `origin` remote. Four new Flask endpoints expose the config and operations. The SCM panel gains a GitHub status row and a wizard modal wired up in JS.

**Tech Stack:** Python `cryptography` (Fernet, already installed), `requests` (new dep for GitHub API), GitPython (already installed), Flask, vanilla JS.

---

## Critical Files

| File | Role |
|------|------|
| `github_config.py` | New — encrypted PAT storage module |
| `git_ops.py` | Add `add_remote`, `remove_remote`, `get_remote_url` |
| `requirements.txt` | Add `requests~=2.31` |
| `web_ui.py` ~line 1836 | Add 4 GitHub API endpoints after git endpoints |
| `templates/index.html` lines 217-290 | Add GitHub status row + wizard modal to `#panel-scm` |
| `static/css/style.css` EOF | Append GitHub status row + wizard CSS |
| `static/js/app.js` EOF | Append GitHub JS module |

**Working directory for all commands:** `.worktrees/feature/git-integration-sidebar/`

---

### Task 1: Add `requests` to requirements and create `github_config.py`

**Files:**
- Modify: `requirements.txt`
- Create: `github_config.py`

**Step 1: Add requests dependency**

In `requirements.txt`, after the `gitpython~=3.1` line add:
```
requests~=2.31
```

**Step 2: Create `github_config.py`**

Create `github_config.py` alongside `git_ops.py`:

```python
"""
Encrypted GitHub configuration storage for AutoGen Web Tester workspaces.
Stores remote URL + Fernet-encrypted PAT in .github-config.json per workspace.
"""

import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

CONFIG_FILENAME = ".github-config.json"
_SECRET_FILE = Path.home() / ".autogen" / ".github_secret"


def _get_fernet() -> Fernet:
    """Load or generate the Fernet encryption key."""
    env_secret = os.getenv("GITHUB_CONFIG_SECRET", "").strip()
    if env_secret:
        key = env_secret.encode()
    elif _SECRET_FILE.exists():
        key = _SECRET_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SECRET_FILE.write_bytes(key)
    return Fernet(key)


def get_config(workspace_path: Path) -> dict | None:
    """
    Return {remote_url, token_encrypted} for the workspace, or None if not configured.
    token_encrypted is the raw encrypted bytes as a string — use decrypt_token() to read the PAT.
    """
    cfg_path = Path(workspace_path) / CONFIG_FILENAME
    if not cfg_path.exists():
        return None
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_config(workspace_path: Path, remote_url: str, token: str) -> None:
    """Encrypt token and write config file."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(token.encode()).decode()
    cfg_path = Path(workspace_path) / CONFIG_FILENAME
    cfg_path.write_text(
        json.dumps({"remote_url": remote_url, "token": encrypted}, indent=2),
        encoding="utf-8",
    )


def decrypt_token(workspace_path: Path) -> str | None:
    """Return the plaintext PAT, or None if not configured or decryption fails."""
    cfg = get_config(workspace_path)
    if not cfg or not cfg.get("token"):
        return None
    try:
        fernet = _get_fernet()
        return fernet.decrypt(cfg["token"].encode()).decode()
    except (InvalidToken, Exception):
        return None


def delete_config(workspace_path: Path) -> None:
    """Remove the config file if it exists."""
    cfg_path = Path(workspace_path) / CONFIG_FILENAME
    if cfg_path.exists():
        cfg_path.unlink()
```

**Step 3: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('github_config.py').read()); print('OK')"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add requirements.txt github_config.py
git commit -m "feat: add github_config.py with Fernet-encrypted PAT storage"
```

---

### Task 2: Add `add_remote`, `remove_remote`, `get_remote_url` to `git_ops.py`

**Files:**
- Modify: `git_ops.py` (append before the `_inject_token` helper at the bottom)

**Step 1: Add the three functions**

In `git_ops.py`, insert before the `def _inject_token(url, token)` line at the bottom:

```python
def get_remote_url(workspace_path: Path, remote: str = 'origin') -> str | None:
    """Return the URL of the given remote, or None if it doesn't exist."""
    repo = _get_repo(workspace_path)
    try:
        return repo.remote(remote).url
    except ValueError:
        return None


def add_remote(workspace_path: Path, url: str, remote: str = 'origin') -> None:
    """Add a remote. If origin already exists, update its URL instead."""
    repo = _get_repo(workspace_path)
    try:
        repo.remote(remote).set_url(url)
    except ValueError:
        repo.create_remote(remote, url)


def remove_remote(workspace_path: Path, remote: str = 'origin') -> None:
    """Remove a remote if it exists."""
    repo = _get_repo(workspace_path)
    try:
        repo.delete_remote(repo.remote(remote))
    except ValueError:
        pass  # remote didn't exist — no-op
```

**Step 2: Verify syntax**

```bash
python3 -m py_compile git_ops.py && echo "OK"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add git_ops.py
git commit -m "feat: add add_remote/remove_remote/get_remote_url to git_ops"
```

---

### Task 3: Add GitHub API endpoints to `web_ui.py`

**Files:**
- Modify: `web_ui.py`

**Step 1: Import `github_config` and `requests`**

At the top of `web_ui.py`, after `import git_ops` add:

```python
import github_config
import requests as _requests
```

**Step 2: Add the 4 endpoints**

After the `# ========== END GIT API ENDPOINTS ==========` comment block (around line 2050), insert:

```python
# ========== GITHUB INTEGRATION ENDPOINTS ==========

def _parse_github_repo(remote_url: str) -> tuple[str, str] | tuple[None, None]:
    """Extract (owner, repo) from a GitHub HTTPS or SSH URL. Returns (None, None) on failure."""
    import re
    url = remote_url.strip().rstrip('/')
    if url.endswith('.git'):
        url = url[:-4]
    m = re.search(r'github\.com[:/]([^/]+)/([^/]+)$', url)
    if m:
        return m.group(1), m.group(2)
    return None, None


@app.route('/api/workspaces/<workspace_name>/github/config', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_github_config(workspace_name):
    """Return GitHub connection info (no token) for the workspace."""
    try:
        _ensure_git_repo(workspace_name)
        cfg = github_config.get_config(_ws_dir(workspace_name))
        if not cfg:
            return jsonify({'connected': False}), 200
        remote_url = cfg.get('remote_url', '')
        owner, repo = _parse_github_repo(remote_url)
        # Get ahead/behind from git status
        ahead, behind = 0, 0
        try:
            status = git_ops.get_status(_ws_dir(workspace_name))
            ahead = status.get('ahead', 0)
            behind = status.get('behind', 0)
        except Exception:
            pass
        return jsonify({
            'connected': True,
            'remote_url': remote_url,
            'owner': owner,
            'repo': repo,
            'ahead': ahead,
            'behind': behind,
        }), 200
    except Exception as e:
        app.logger.exception("github config error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/github/connect', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def github_connect(workspace_name):
    """Connect workspace to an existing GitHub repo. Validates token, sets remote, saves config."""
    data = request.get_json() or {}
    remote_url = data.get('remote_url', '').strip()
    token = data.get('token', '').strip()
    if not remote_url or not token:
        return jsonify({'error': 'remote_url and token are required'}), 400

    # Validate token against GitHub API
    try:
        resp = _requests.get(
            'https://api.github.com/user',
            headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github+json'},
            timeout=10,
        )
        if resp.status_code == 401:
            return jsonify({'error': 'Invalid GitHub token'}), 400
        resp.raise_for_status()
    except _requests.RequestException as e:
        return jsonify({'error': f'GitHub API error: {e}'}), 400

    try:
        git_ops.add_remote(_ws_dir(workspace_name), remote_url)
        github_config.save_config(_ws_dir(workspace_name), remote_url, token)
        owner, repo = _parse_github_repo(remote_url)
        return jsonify({'success': True, 'owner': owner, 'repo': repo}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/github/create-repo', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def github_create_repo(workspace_name):
    """Create a new GitHub repo and push the workspace to it."""
    data = request.get_json() or {}
    token = data.get('token', '').strip()
    repo_name = data.get('name', '').strip()
    private = bool(data.get('private', False))
    description = data.get('description', '').strip()

    if not token or not repo_name:
        return jsonify({'error': 'token and name are required'}), 400

    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
    }

    # Validate token and get username
    try:
        user_resp = _requests.get('https://api.github.com/user', headers=headers, timeout=10)
        if user_resp.status_code == 401:
            return jsonify({'error': 'Invalid GitHub token'}), 400
        user_resp.raise_for_status()
        username = user_resp.json().get('login', '')
    except _requests.RequestException as e:
        return jsonify({'error': f'Token validation failed: {e}'}), 400

    # Create repo
    try:
        create_payload = {'name': repo_name, 'private': private}
        if description:
            create_payload['description'] = description
        create_resp = _requests.post(
            'https://api.github.com/user/repos',
            headers=headers,
            json=create_payload,
            timeout=15,
        )
        if create_resp.status_code == 422:
            return jsonify({'error': 'Repository already exists or name is invalid'}), 400
        create_resp.raise_for_status()
        repo_data = create_resp.json()
        clone_url = repo_data.get('clone_url', f'https://github.com/{username}/{repo_name}.git')
    except _requests.RequestException as e:
        return jsonify({'error': f'Failed to create repo: {e}'}), 400

    # Set remote and push
    try:
        git_ops.add_remote(_ws_dir(workspace_name), clone_url)
        git_ops.push(_ws_dir(workspace_name), token=token)
        github_config.save_config(_ws_dir(workspace_name), clone_url, token)
        return jsonify({'success': True, 'owner': username, 'repo': repo_name, 'url': clone_url}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/github/disconnect', methods=['DELETE'])
@login_required
@workspace_access_required(permission='write')
def github_disconnect(workspace_name):
    """Remove GitHub config and origin remote."""
    try:
        github_config.delete_config(_ws_dir(workspace_name))
        git_ops.remove_remote(_ws_dir(workspace_name))
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ========== END GITHUB INTEGRATION ENDPOINTS ==========
```

**Step 3: Verify syntax**

```bash
python3 -m py_compile web_ui.py && echo "OK"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add web_ui.py
git commit -m "feat: add GitHub connect/disconnect/create-repo API endpoints"
```

---

### Task 4: Update `git_ops.push` to use stored token + update `init_repo` `.gitignore`

**Files:**
- Modify: `git_ops.py` — update push to accept token from `github_config`
- Modify: `web_ui.py` — update `create_workspace` to add `.github-config.json` to workspace `.gitignore`

**Step 1: Update workspace `.gitignore` on creation**

In `web_ui.py`, find the `create_workspace` function. After the `git_ops.init_repo(ws_dir)` call in the non-clone branch, add:

```python
gitignore = ws_dir / '.gitignore'
existing = gitignore.read_text(encoding='utf-8') if gitignore.exists() else ''
if '.github-config.json' not in existing:
    with gitignore.open('a', encoding='utf-8') as f:
        f.write('\n.github-config.json\n')
```

Also add the same after `git_ops.clone_repo(clone_url, ws_dir)` in the clone branch.

**Step 2: Update `scmPush` in JS to use stored token (done in Task 6 — skip here)**

**Step 3: Verify syntax**

```bash
python3 -m py_compile web_ui.py && echo "OK"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add web_ui.py
git commit -m "fix: add .github-config.json to workspace .gitignore on creation"
```

---

### Task 5: HTML — GitHub status row + wizard modal

**Files:**
- Modify: `templates/index.html`

**Step 1: Add GitHub status row inside `#panel-scm`**

In `templates/index.html`, find:
```html
                    <div id="panel-scm" class="sidebar-panel sidebar-panel--hidden">

                        <!-- SCM header -->
                        <div class="unified-tree-header">
```

Insert this block **between** the opening `<div id="panel-scm"...>` and `<!-- SCM header -->`:

```html
                        <!-- GitHub connection status row -->
                        <div id="github-status-row" class="github-status-row github-status-disconnected">
                            <i class="lni lni-github github-status-icon"></i>
                            <span id="github-status-label" class="github-status-label">Not connected to GitHub</span>
                            <div id="github-status-actions" class="github-status-actions">
                                <button id="github-connect-btn" class="btn btn-small btn-accent">Connect</button>
                            </div>
                            <!-- Connected state extras (hidden when disconnected) -->
                            <a id="github-repo-link" class="github-repo-link" href="#" target="_blank" rel="noopener" style="display:none;"></a>
                            <span id="github-sync-counts" class="github-sync-counts" style="display:none;"></span>
                            <div class="github-overflow-wrapper" style="display:none;" id="github-overflow-wrapper">
                                <button id="github-overflow-btn" class="btn-icon-small" title="More options">···</button>
                                <div id="github-overflow-menu" class="github-overflow-menu" style="display:none;">
                                    <button class="github-overflow-item" id="github-sync-btn"><i class="lni lni-reload"></i> Sync</button>
                                    <button class="github-overflow-item" id="github-copy-url-btn"><i class="lni lni-copy"></i> Copy remote URL</button>
                                    <button class="github-overflow-item github-overflow-item--danger" id="github-disconnect-btn"><i class="lni lni-unlink"></i> Disconnect</button>
                                </div>
                            </div>
                        </div>
```

**Step 2: Add wizard modal before `</body>`**

In `templates/index.html`, find the `<!-- Right-Click Context Menu -->` comment block (near the bottom, before `</body>`). Insert this modal **before** it:

```html
    <!-- GitHub Wizard Modal -->
    <div id="github-wizard-modal" class="modal" style="display:none;">
        <div class="modal-content github-wizard-content">
            <div class="modal-header">
                <h2><i class="lni lni-github"></i> Connect to GitHub</h2>
                <span id="github-wizard-close" class="modal-close">&times;</span>
            </div>
            <div class="modal-body">

                <!-- Step 1: Choose path -->
                <div id="github-wizard-step1" class="github-wizard-step">
                    <p class="github-wizard-subtitle">How do you want to connect this workspace?</p>
                    <div class="github-wizard-cards">
                        <button class="github-wizard-card" id="github-choose-connect">
                            <i class="lni lni-link github-wizard-card-icon"></i>
                            <strong>Connect to existing repo</strong>
                            <span>Add a GitHub repo as the remote for this workspace</span>
                        </button>
                        <button class="github-wizard-card" id="github-choose-create">
                            <i class="lni lni-github github-wizard-card-icon"></i>
                            <strong>Push to a new GitHub repo</strong>
                            <span>Create a new repo on GitHub and push this workspace</span>
                        </button>
                    </div>
                </div>

                <!-- Step 2a: Connect to existing repo -->
                <div id="github-wizard-step2a" class="github-wizard-step" style="display:none;">
                    <button class="github-wizard-back" id="github-back-2a"><i class="lni lni-arrow-left"></i> Back</button>
                    <div class="form-group">
                        <label for="github-remote-url">Repository URL</label>
                        <input type="text" id="github-remote-url" placeholder="https://github.com/owner/repo.git" autocomplete="off">
                    </div>
                    <div class="form-group">
                        <label for="github-token-2a">Personal Access Token <span class="github-token-note">(stored encrypted on disk)</span></label>
                        <div class="github-token-input-row">
                            <input type="password" id="github-token-2a" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" autocomplete="new-password">
                            <button type="button" class="btn-icon-small github-token-toggle" data-target="github-token-2a" title="Show/hide token"><i class="lni lni-eye"></i></button>
                        </div>
                    </div>
                    <div id="github-error-2a" class="github-wizard-error" style="display:none;"></div>
                    <div class="github-wizard-footer">
                        <div id="github-progress-2a" class="github-wizard-progress" style="display:none;">
                            <span class="github-wizard-spinner"></span>
                            <span id="github-progress-2a-text"></span>
                        </div>
                        <button class="btn btn-primary" id="github-connect-submit">Connect</button>
                    </div>
                </div>

                <!-- Step 2b: Create new repo -->
                <div id="github-wizard-step2b" class="github-wizard-step" style="display:none;">
                    <button class="github-wizard-back" id="github-back-2b"><i class="lni lni-arrow-left"></i> Back</button>
                    <div class="form-group">
                        <label for="github-token-2b">Personal Access Token <span class="github-token-note">(stored encrypted on disk)</span></label>
                        <div class="github-token-input-row">
                            <input type="password" id="github-token-2b" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" autocomplete="new-password">
                            <button type="button" class="btn-icon-small github-token-toggle" data-target="github-token-2b" title="Show/hide token"><i class="lni lni-eye"></i></button>
                        </div>
                    </div>
                    <div class="github-wizard-row">
                        <div class="form-group" style="flex:1;">
                            <label for="github-repo-name">Repository name</label>
                            <input type="text" id="github-repo-name" placeholder="my-tests" autocomplete="off">
                        </div>
                        <div class="form-group github-visibility-group">
                            <label>Visibility</label>
                            <div class="github-radio-group">
                                <label><input type="radio" name="github-visibility" value="public" checked> Public</label>
                                <label><input type="radio" name="github-visibility" value="private"> Private</label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="github-repo-desc">Description <span class="github-token-note">(optional)</span></label>
                        <input type="text" id="github-repo-desc" placeholder="Automated tests for …" autocomplete="off">
                    </div>
                    <div id="github-error-2b" class="github-wizard-error" style="display:none;"></div>
                    <div class="github-wizard-footer">
                        <div id="github-progress-2b" class="github-wizard-progress" style="display:none;">
                            <span class="github-wizard-spinner"></span>
                            <span id="github-progress-2b-text"></span>
                        </div>
                        <button class="btn btn-primary" id="github-create-submit">Create &amp; Push</button>
                    </div>
                </div>

            </div>
        </div>
    </div>
```

**Step 3: Verify HTML is well-formed**

```bash
python3 -c "
from html.parser import HTMLParser
class V(HTMLParser): pass
V().feed(open('templates/index.html').read())
print('HTML OK')
"
```
Expected: `HTML OK`

**Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: add GitHub status row and wizard modal to SCM panel"
```

---

### Task 6: CSS — GitHub status row, wizard, overflow menu

**Files:**
- Modify: `static/css/style.css` (append to end of file)

**Step 1: Append all GitHub CSS**

Append this entire block to the end of `static/css/style.css`:

```css
/* ========== GITHUB INTEGRATION ========== */

/* GitHub status row */
.github-status-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--ctp-surface0);
    flex-shrink: 0;
    font-size: 12px;
    position: relative;
}

.github-status-disconnected .github-status-icon { color: var(--ctp-overlay0); }
.github-status-connected .github-status-icon    { color: #2da44e; }
.github-status-error .github-status-icon        { color: var(--ctp-red); }

.github-status-label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--ctp-subtext1);
    font-size: 11px;
}

.github-status-connected .github-status-label { color: var(--ctp-text); }

.github-repo-link {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    font-weight: 600;
    color: var(--ctp-text);
    text-decoration: none;
}
.github-repo-link:hover { text-decoration: underline; color: var(--ctp-accent); }

.github-sync-counts {
    font-size: 11px;
    color: var(--ctp-subtext1);
    white-space: nowrap;
    flex-shrink: 0;
}

.github-status-actions { flex-shrink: 0; }

.btn-accent {
    background: var(--ctp-accent);
    color: var(--ctp-base);
    border: none;
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
}
.btn-accent:hover { opacity: 0.85; }

.github-status-token-error {
    font-size: 10px;
    color: var(--ctp-red);
    display: flex;
    align-items: center;
    gap: 4px;
}

/* Overflow menu */
.github-overflow-wrapper { position: relative; flex-shrink: 0; }

.github-overflow-menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    background: var(--ctp-surface0);
    border: 1px solid var(--ctp-surface1);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    min-width: 170px;
    z-index: 100;
    overflow: hidden;
}

.github-overflow-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    font-size: 12px;
    color: var(--ctp-text);
    background: transparent;
    border: none;
    width: 100%;
    text-align: left;
    cursor: pointer;
}
.github-overflow-item:hover { background: var(--ctp-surface1); }
.github-overflow-item--danger { color: var(--ctp-red); }
.github-overflow-item--danger:hover { background: rgba(243,139,168,0.1); }

/* Wizard modal */
.github-wizard-content { max-width: 480px; }

.github-wizard-subtitle {
    color: var(--ctp-subtext1);
    font-size: 13px;
    margin: 0 0 16px;
}

.github-wizard-cards {
    display: flex;
    gap: 12px;
}

.github-wizard-card {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    padding: 16px;
    background: var(--ctp-surface0);
    border: 1px solid var(--ctp-surface1);
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    transition: border-color 0.15s, background 0.15s;
    color: var(--ctp-text);
}
.github-wizard-card:hover {
    border-color: var(--ctp-accent);
    background: var(--ctp-surface1);
}
.github-wizard-card-icon {
    font-size: 24px;
    color: var(--ctp-accent);
    margin-bottom: 4px;
}
.github-wizard-card strong { font-size: 13px; font-weight: 600; }
.github-wizard-card span  { font-size: 11px; color: var(--ctp-subtext1); }

.github-wizard-back {
    background: transparent;
    border: none;
    color: var(--ctp-subtext1);
    cursor: pointer;
    font-size: 12px;
    padding: 0;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 4px;
}
.github-wizard-back:hover { color: var(--ctp-text); }

.github-wizard-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
}
.github-visibility-group { flex-shrink: 0; min-width: 120px; }

.github-radio-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    color: var(--ctp-text);
    margin-top: 2px;
}
.github-radio-group label { display: flex; align-items: center; gap: 6px; cursor: pointer; }

.github-token-note {
    font-size: 10px;
    color: var(--ctp-overlay1);
    font-weight: 400;
}

.github-token-input-row {
    display: flex;
    gap: 6px;
    align-items: center;
}
.github-token-input-row input { flex: 1; }

.github-wizard-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 16px;
}

.github-wizard-progress {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--ctp-subtext1);
    flex: 1;
}

.github-wizard-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--ctp-surface1);
    border-top-color: var(--ctp-accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

.github-wizard-error {
    background: rgba(243,139,168,0.1);
    border: 1px solid var(--ctp-red);
    border-radius: 4px;
    color: var(--ctp-red);
    font-size: 12px;
    padding: 7px 10px;
    margin-top: 8px;
}
/* ========== END GITHUB INTEGRATION ========== */
```

**Step 2: Verify file has no obvious errors (line count sanity)**

```bash
wc -l static/css/style.css
```
Expected: more than 4300 lines (was ~4300 before)

**Step 3: Commit**

```bash
git add static/css/style.css
git commit -m "feat: add GitHub status row and wizard CSS"
```

---

### Task 7: JS — GitHub module (`loadGithubConfig`, wizard, connect, create, disconnect, sync)

**Files:**
- Modify: `static/js/app.js` (append new section to end of file)

**Step 1: Update `switchPanel` to call `loadGithubConfig` on SCM open**

Find the existing `switchPanel` function (near the end of `app.js`):

```javascript
function switchPanel(panelId) {
    document.querySelectorAll('.activity-bar-btn[data-panel]').forEach(btn =>
        btn.classList.toggle('active', btn.dataset.panel === panelId));
    document.querySelectorAll('.sidebar-panel').forEach(p =>
        p.classList.toggle('sidebar-panel--hidden', p.id !== `panel-${panelId}`));
    if (panelId === 'scm') refreshScmPanel();
}
```

Replace the last line to also call `loadGithubConfig`:

```javascript
    if (panelId === 'scm') { refreshScmPanel(); loadGithubConfig(); }
```

**Step 2: Append the GitHub JS module**

Append to the end of `app.js`:

```javascript
// ========================================
// GITHUB INTEGRATION
// ========================================

async function loadGithubConfig() {
    if (!currentWorkspaceName) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/config`);
        const data = await res.json();
        renderGithubStatusRow(data);
    } catch (e) {
        console.warn('loadGithubConfig failed:', e);
    }
}

function renderGithubStatusRow(data) {
    const row = document.getElementById('github-status-row');
    if (!row) return;

    const label    = document.getElementById('github-status-label');
    const repoLink = document.getElementById('github-repo-link');
    const syncCounts = document.getElementById('github-sync-counts');
    const overflowWrapper = document.getElementById('github-overflow-wrapper');
    const connectBtn = document.getElementById('github-connect-btn');

    if (!data.connected) {
        row.className = 'github-status-row github-status-disconnected';
        if (label) { label.textContent = 'Not connected to GitHub'; label.style.display = ''; }
        if (repoLink) repoLink.style.display = 'none';
        if (syncCounts) syncCounts.style.display = 'none';
        if (overflowWrapper) overflowWrapper.style.display = 'none';
        if (connectBtn) connectBtn.style.display = '';
        return;
    }

    row.className = 'github-status-row github-status-connected';
    if (label) label.style.display = 'none';
    if (connectBtn) connectBtn.style.display = 'none';

    const owner = data.owner || '';
    const repo  = data.repo  || '';
    const repoFullName = owner && repo ? `${owner}/${repo}` : data.remote_url;

    if (repoLink) {
        repoLink.style.display = '';
        repoLink.textContent = repoFullName;
        repoLink.href = `https://github.com/${owner}/${repo}`;
    }

    if (syncCounts) {
        const ahead  = data.ahead  || 0;
        const behind = data.behind || 0;
        if (ahead > 0 || behind > 0) {
            syncCounts.style.display = '';
            syncCounts.textContent = `${ahead > 0 ? '↑' + ahead : ''}${behind > 0 ? ' ↓' + behind : ''}`.trim();
        } else {
            syncCounts.style.display = 'none';
        }
    }

    if (overflowWrapper) overflowWrapper.style.display = '';
}

function openGithubWizard(step) {
    const modal = document.getElementById('github-wizard-modal');
    if (!modal) return;

    // Hide all steps
    ['github-wizard-step1', 'github-wizard-step2a', 'github-wizard-step2b'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });

    // Clear errors + progress
    ['github-error-2a', 'github-error-2b'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.style.display = 'none'; el.textContent = ''; }
    });
    ['github-progress-2a', 'github-progress-2b'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });

    const stepEl = document.getElementById(`github-wizard-${step}`);
    if (stepEl) stepEl.style.display = '';

    modal.style.display = 'flex';
}

function closeGithubWizard() {
    const modal = document.getElementById('github-wizard-modal');
    if (modal) modal.style.display = 'none';
}

function showGithubWizardProgress(step, text) {
    const progressEl = document.getElementById(`github-progress-${step}`);
    const textEl = document.getElementById(`github-progress-${step}-text`);
    if (progressEl) progressEl.style.display = 'flex';
    if (textEl) textEl.textContent = text;
}

function showGithubWizardError(step, message) {
    const errEl = document.getElementById(`github-error-${step}`);
    if (errEl) { errEl.textContent = message; errEl.style.display = ''; }
    // Hide progress
    const progressEl = document.getElementById(`github-progress-${step}`);
    if (progressEl) progressEl.style.display = 'none';
}

async function githubConnectSubmit() {
    const url    = document.getElementById('github-remote-url')?.value.trim();
    const token  = document.getElementById('github-token-2a')?.value.trim();
    const submitBtn = document.getElementById('github-connect-submit');

    if (!url || !token) {
        showGithubWizardError('2a', 'Repository URL and token are required.');
        return;
    }

    if (submitBtn) submitBtn.disabled = true;
    showGithubWizardProgress('2a', 'Validating token…');

    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ remote_url: url, token })
        });
        const data = await res.json();
        if (!res.ok) { showGithubWizardError('2a', data.error || 'Connection failed'); return; }

        closeGithubWizard();
        loadGithubConfig();
        addLogEntry('info', `Connected to GitHub: ${data.owner}/${data.repo}`);
    } catch (e) {
        showGithubWizardError('2a', e.message || 'Connection failed');
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

async function githubCreateRepoSubmit() {
    const token  = document.getElementById('github-token-2b')?.value.trim();
    const name   = document.getElementById('github-repo-name')?.value.trim();
    const desc   = document.getElementById('github-repo-desc')?.value.trim();
    const privateRadio = document.querySelector('input[name="github-visibility"]:checked');
    const isPrivate = privateRadio?.value === 'private';
    const submitBtn = document.getElementById('github-create-submit');

    if (!token || !name) {
        showGithubWizardError('2b', 'Token and repository name are required.');
        return;
    }

    if (submitBtn) submitBtn.disabled = true;

    const steps = ['Validating token…', 'Creating repo…', 'Pushing…'];
    let stepIdx = 0;
    showGithubWizardProgress('2b', steps[stepIdx]);

    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/create-repo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, name, private: isPrivate, description: desc })
        });
        const data = await res.json();
        if (!res.ok) { showGithubWizardError('2b', data.error || 'Failed'); return; }

        closeGithubWizard();
        loadGithubConfig();
        addLogEntry('info', `Created and pushed to GitHub: ${data.owner}/${data.repo}`);
    } catch (e) {
        showGithubWizardError('2b', e.message || 'Failed');
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

async function githubDisconnect() {
    if (!currentWorkspaceName) return;
    if (!confirm('Disconnect from GitHub? The local workspace and git history are preserved.')) return;

    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/disconnect`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            renderGithubStatusRow({ connected: false });
            document.getElementById('github-overflow-menu')?.setAttribute('style', 'display:none;');
            addLogEntry('info', 'Disconnected from GitHub.');
        } else {
            alert(data.error || 'Disconnect failed');
        }
    } catch (e) {
        alert('Disconnect failed: ' + e.message);
    }
}

async function githubSync() {
    if (!currentWorkspaceName) return;
    document.getElementById('github-overflow-menu')?.setAttribute('style', 'display:none;');
    try {
        // Pull first, then push — both use the stored token via the backend
        await authFetch(`/api/workspaces/${currentWorkspaceName}/git/pull`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
        });
        await authFetch(`/api/workspaces/${currentWorkspaceName}/git/push`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
        });
        addLogEntry('info', 'Synced with GitHub.');
        loadGithubConfig();
        loadFileExplorer();
        loadAiSteps();
    } catch (e) {
        alert('Sync failed: ' + e.message);
    }
}

function initGithubPanel() {
    // Connect button (disconnected state)
    document.getElementById('github-connect-btn')?.addEventListener('click', () => openGithubWizard('step1'));

    // Wizard close
    document.getElementById('github-wizard-close')?.addEventListener('click', closeGithubWizard);
    document.getElementById('github-wizard-modal')?.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeGithubWizard();
    });

    // Step 1 cards
    document.getElementById('github-choose-connect')?.addEventListener('click', () => openGithubWizard('step2a'));
    document.getElementById('github-choose-create')?.addEventListener('click', () => {
        // Pre-fill repo name from workspace name
        const nameInput = document.getElementById('github-repo-name');
        if (nameInput && currentWorkspaceName) {
            nameInput.value = currentWorkspaceName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
        }
        openGithubWizard('step2b');
    });

    // Back buttons
    document.getElementById('github-back-2a')?.addEventListener('click', () => openGithubWizard('step1'));
    document.getElementById('github-back-2b')?.addEventListener('click', () => openGithubWizard('step1'));

    // Submit buttons
    document.getElementById('github-connect-submit')?.addEventListener('click', githubConnectSubmit);
    document.getElementById('github-create-submit')?.addEventListener('click', githubCreateRepoSubmit);

    // Overflow menu toggle
    document.getElementById('github-overflow-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        const menu = document.getElementById('github-overflow-menu');
        if (menu) menu.style.display = menu.style.display === 'none' ? '' : 'none';
    });
    // Close overflow when clicking outside
    document.addEventListener('click', () => {
        document.getElementById('github-overflow-menu')?.setAttribute('style', 'display:none;');
    });

    // Overflow menu items
    document.getElementById('github-sync-btn')?.addEventListener('click', githubSync);
    document.getElementById('github-disconnect-btn')?.addEventListener('click', githubDisconnect);
    document.getElementById('github-copy-url-btn')?.addEventListener('click', () => {
        document.getElementById('github-overflow-menu')?.setAttribute('style', 'display:none;');
        const cfg = document.getElementById('github-repo-link')?.href;
        if (cfg) navigator.clipboard.writeText(cfg).then(() => addLogEntry('info', 'Remote URL copied.'));
    });

    // Show/hide token toggles
    document.querySelectorAll('.github-token-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            const input = document.getElementById(targetId);
            if (!input) return;
            input.type = input.type === 'password' ? 'text' : 'password';
            const icon = btn.querySelector('i');
            if (icon) icon.className = input.type === 'password' ? 'lni lni-eye' : 'lni lni-eye-slash';
        });
    });
}

// Call initGithubPanel on load (alongside initScmPanel)
window.addEventListener('load', () => { initGithubPanel(); });
// ========== END GITHUB INTEGRATION ==========
```

**Step 3: Update `scmPush` to use stored token**

Find the existing `scmPush` function in `app.js`:
```javascript
async function scmPush() {
    if (!currentWorkspaceName) return;
    const token = prompt('GitHub Personal Access Token (leave blank if SSH or already configured):');
    if (token === null) return; // user cancelled
```

Replace it so it reads the stored token from the backend instead of prompting:

```javascript
async function scmPush() {
    if (!currentWorkspaceName) return;
    try {
        // Use stored token if available (GitHub connected); otherwise fall back to prompt
        const cfgRes = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/config`);
        const cfgData = cfgRes.ok ? await cfgRes.json() : {};
        let body = {};
        if (!cfgData.connected) {
            const token = prompt('GitHub Personal Access Token (leave blank if SSH or already configured):');
            if (token === null) return;
            if (token) body.token = token;
        }
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/push`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (res.ok) {
            addLogEntry('info', 'Pushed to remote.');
            loadGithubConfig();
        } else {
            alert(data.error || 'Push failed');
        }
    } catch (e) {
        alert('Push failed: ' + e.message);
    }
}
```

But wait — the backend `git/push` endpoint uses `token` from the request body and doesn't read from `github_config`. We need to update the push endpoint to use the stored token if no token is provided in the request.

**Step 4: Update `git/push` endpoint in `web_ui.py` to use stored token**

Find the `git_push` route in `web_ui.py`:
```python
def git_push(workspace_name):
    data = request.get_json() or {}
    try:
        git_ops.push(
            _ws_dir(workspace_name),
            remote=data.get('remote', 'origin'),
            branch=data.get('branch') or None,
            token=data.get('token') or None,
        )
```

Update it to fall back to the stored token:
```python
def git_push(workspace_name):
    data = request.get_json() or {}
    token = data.get('token') or None
    if not token:
        token = github_config.decrypt_token(_ws_dir(workspace_name))
    try:
        git_ops.push(
            _ws_dir(workspace_name),
            remote=data.get('remote', 'origin'),
            branch=data.get('branch') or None,
            token=token,
        )
```

Similarly update `git_pull` to use the stored token when pulling:
```python
def git_pull(workspace_name):
    data = request.get_json() or {}
    # Pull doesn't take a token directly in gitpython, but the stored token
    # is already in the remote URL via add_remote (HTTPS with token injected).
    # No change needed here unless SSH is used.
    try:
        git_ops.pull(
```

**Step 5: Verify syntax**

```bash
python3 -m py_compile web_ui.py && echo "web_ui OK"
node --check static/js/app.js && echo "app.js OK"
```
Expected: both `OK`

**Step 6: Commit**

```bash
git add static/js/app.js web_ui.py
git commit -m "feat: add GitHub wizard JS module and wire push to use stored token"
```

---

### Task 8: Push branch and update PR

**Step 1: Verify all files**

```bash
python3 -m py_compile git_ops.py github_config.py web_ui.py migrate_to_git.py && echo "Python OK"
node --check static/js/app.js && echo "JS OK"
```
Expected: both `OK`

**Step 2: Push to remote**

```bash
git push
```

**Step 3: Verify PR #13 is updated**

```bash
gh pr view 13 --web
```

---

## Manual Verification Checklist

1. Open SCM panel on a fresh workspace → "Not connected to GitHub" row + "Connect" button visible
2. Click Connect → Step 1 modal with two equal cards
3. Choose "Connect to existing repo" → Step 2a with URL + PAT fields, show/hide toggle works
4. Submit with invalid token → "Invalid GitHub token" error shown inline
5. Submit with valid token + real repo URL → modal closes, status row shows `owner/repo` in green
6. `···` menu → shows Sync / Copy remote URL / Disconnect
7. Disconnect → status row returns to disconnected state
8. Choose "Push to new repo" → Step 2b with repo name pre-filled from workspace name
9. Create & Push with valid token → modal shows spinner + progress steps → closes with green status
10. After connecting, SCM Push button no longer prompts for PAT
11. Reload page → GitHub config persists (encrypted on disk), status row still shows connected
