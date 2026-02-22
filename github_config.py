"""
Encrypted GitHub PAT storage per workspace.

Config file: <workspace_dir>/.github-config.json
Schema: {"remote_url": str, "token": str}   (token is Fernet-encrypted, base64)

Encryption key priority:
  1. GITHUB_CONFIG_SECRET env var (base64url Fernet key)
  2. Auto-generated key saved to ~/.autogen/.github_secret
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

_CONFIG_FILENAME = ".github-config.json"
_SECRET_PATH = Path.home() / ".autogen" / ".github_secret"

# ──────────────────────────────────────────────
# Key management
# ──────────────────────────────────────────────


def _get_fernet() -> Fernet:
    secret = os.environ.get("GITHUB_CONFIG_SECRET", "").strip()
    if secret:
        key = secret.encode()
    else:
        if _SECRET_PATH.exists():
            key = _SECRET_PATH.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            _SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SECRET_PATH.write_bytes(key)
    return Fernet(key)


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def get_config(workspace_dir: Path) -> dict | None:
    """Return raw config dict (token still encrypted) or None if not set."""
    cfg_path = workspace_dir / _CONFIG_FILENAME
    if not cfg_path.exists():
        return None
    try:
        return json.loads(cfg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_config(workspace_dir: Path, remote_url: str, pat: str) -> None:
    """Encrypt *pat* and write config. Overwrites any existing config."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(pat.encode()).decode()
    cfg = {"remote_url": remote_url, "token": encrypted}
    cfg_path = workspace_dir / _CONFIG_FILENAME
    cfg_path.write_text(json.dumps(cfg, indent=2))


def decrypt_token(workspace_dir: Path) -> str | None:
    """Return the decrypted PAT, or None if not stored / decryption fails."""
    cfg = get_config(workspace_dir)
    if not cfg or not cfg.get("token"):
        return None
    try:
        fernet = _get_fernet()
        return fernet.decrypt(cfg["token"].encode()).decode()
    except Exception:
        return None


def delete_config(workspace_dir: Path) -> None:
    """Remove the config file (disconnect)."""
    cfg_path = workspace_dir / _CONFIG_FILENAME
    if cfg_path.exists():
        cfg_path.unlink()
