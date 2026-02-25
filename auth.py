"""Authentication module — local-only passthrough (no Supabase)."""

from functools import wraps
from flask import g

_LOCAL_USER = {'id': 'local', 'username': 'local', 'email': 'local@localhost'}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        g._current_user = _LOCAL_USER
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    g._current_user = _LOCAL_USER
    return _LOCAL_USER
