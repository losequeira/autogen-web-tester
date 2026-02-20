"""Encrypted local session persistence for ~/.autogen/session.enc"""
import json
from pathlib import Path

_DIR = Path.home() / ".autogen"
_KEY_FILE = _DIR / ".key"
_SESSION_FILE = _DIR / "session.enc"


def _get_or_create_key() -> bytes:
    from cryptography.fernet import Fernet
    _DIR.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    _KEY_FILE.chmod(0o600)
    return key


def save_tokens(access_token: str, refresh_token: str, user_id: str) -> None:
    from cryptography.fernet import Fernet
    key = _get_or_create_key()
    payload = json.dumps({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user_id': user_id,
    }).encode()
    _SESSION_FILE.write_bytes(Fernet(key).encrypt(payload))
    _SESSION_FILE.chmod(0o600)


def load_tokens() -> dict | None:
    from cryptography.fernet import Fernet, InvalidToken
    if not _SESSION_FILE.exists() or not _KEY_FILE.exists():
        return None
    try:
        payload = Fernet(_KEY_FILE.read_bytes()).decrypt(_SESSION_FILE.read_bytes())
        return json.loads(payload.decode())
    except Exception:
        clear_tokens()
        return None


def clear_tokens() -> None:
    try:
        _SESSION_FILE.unlink(missing_ok=True)
    except Exception:
        pass
