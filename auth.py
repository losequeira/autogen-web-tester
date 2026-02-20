"""
Authentication module for AutoGen Web Tester.

Uses Supabase Auth with JWT tokens. The Flask server validates tokens
via the Supabase client and loads local User records into flask.g.
"""

import re
import time
from functools import wraps
from flask import Blueprint, jsonify, request, g
import db
from supabase_client import get_supabase_client

# In-memory cache: token -> (user_dict, expiry_timestamp)
_user_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 300  # 5 minutes

# Create Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api')


def init_auth(app):
    """Initialize authentication with Flask app."""
    app.register_blueprint(auth_bp)


# ========== JWT helpers ==========

def login_required(f):
    """Decorator that validates the Supabase JWT and loads the local User into g."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Return the currently authenticated user dict (or None).

    Reads the Authorization header, validates the token with Supabase,
    and caches the result in-memory to avoid repeated remote calls.
    """
    if hasattr(g, '_current_user'):
        return g._current_user

    token = _extract_bearer_token()
    if not token:
        g._current_user = None
        return None

    # Check in-memory cache first
    now = time.time()
    cached = _user_cache.get(token)
    if cached:
        user, expiry = cached
        if now < expiry:
            g._current_user = user
            return user
        else:
            del _user_cache[token]

    try:
        sb = get_supabase_client()
        auth_response = sb.auth.get_user(token)
        supabase_user = auth_response.user
        if not supabase_user:
            g._current_user = None
            return None

        user = db.get_user_by_id(supabase_user.id)
        if not user:
            g._current_user = None
            return None

        # Cache the result
        _user_cache[token] = (user, now + _CACHE_TTL)
        # Evict stale entries periodically
        if len(_user_cache) > 100:
            stale = [k for k, (_, exp) in _user_cache.items() if now >= exp]
            for k in stale:
                del _user_cache[k]

        g._current_user = user
        return user
    except Exception as e:
        print(f"JWT validation error: {e}")
        g._current_user = None
        return None


def _extract_bearer_token() -> str | None:
    """Extract JWT from the Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


# ========== Validation helpers ==========

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username: str) -> bool:
    pattern = r'^[a-zA-Z0-9_-]{3,20}$'
    return re.match(pattern, username) is not None


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, ""


# ========== Endpoints ==========

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user via Supabase Auth, create local User + default Workspace."""
    try:
        data = request.get_json()

        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not all([username, email, password]):
            return jsonify({'error': 'Username, email, and password are required'}), 400

        if not validate_username(username):
            return jsonify({
                'error': 'Username must be 3-20 characters and contain only letters, numbers, underscores, and hyphens'
            }), 400

        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400

        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        # Check uniqueness
        if db.get_user_by_username(username):
            return jsonify({'error': 'Username already exists'}), 409
        if db.get_user_by_email(email):
            return jsonify({'error': 'Email already registered'}), 409

        # Create user in Supabase Auth
        sb = get_supabase_client()
        auth_response = sb.auth.sign_up({
            'email': email,
            'password': password,
            'options': {
                'data': {'username': username}
            }
        })

        supabase_user = auth_response.user
        if not supabase_user:
            return jsonify({'error': 'Registration failed'}), 500

        # Create local user record
        user = db.create_user(id=supabase_user.id, username=username, email=email)

        # Create default private workspace
        try:
            workspace = db.create_workspace(
                name=f"{username}'s Workspace",
                ws_type='private',
                owner_id=user['id'],
            )
        except Exception as ws_err:
            # If workspace creation fails, clean up the user to avoid orphans
            print(f"Warning: workspace creation failed, cleaning up user: {ws_err}")
            try:
                get_supabase_client().table('users').delete().eq('id', user['id']).execute()
            except Exception:
                pass
            return jsonify({'error': 'Registration failed'}), 500

        # Return JWT tokens
        session = auth_response.session
        return jsonify({
            'message': 'Registration successful',
            'user': user,
            'default_workspace_id': workspace['id'],
            'access_token': session.access_token if session else None,
            'refresh_token': session.refresh_token if session else None,
        }), 201

    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user via Supabase Auth and return JWT tokens."""
    try:
        data = request.get_json()

        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        # Look up email by username (Supabase Auth uses email for sign-in)
        user = db.get_user_by_username(username)
        if not user:
            return jsonify({'error': 'Invalid username or password'}), 401
        if not user.get('is_active'):
            return jsonify({'error': 'Account is disabled'}), 403

        email = user['email']

        # Sign in with Supabase Auth
        sb = get_supabase_client()
        auth_response = sb.auth.sign_in_with_password({
            'email': email,
            'password': password
        })

        session = auth_response.session
        if not session:
            return jsonify({'error': 'Invalid username or password'}), 401

        # Get workspaces
        workspaces = db.get_workspaces_for_user(user['id'])

        return jsonify({
            'message': 'Login successful',
            'user': user,
            'workspaces': workspaces,
            'access_token': session.access_token,
            'refresh_token': session.refresh_token,
        }), 200

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Invalid username or password'}), 401


@auth_bp.route('/auto-login', methods=['POST'])
def auto_login():
    """Auto-login using LOCAL_USERNAME / LOCAL_PASSWORD from .env (local Mac app only)."""
    import config as _config
    username = _config.LOCAL_USERNAME
    password = _config.LOCAL_PASSWORD
    if not username or not password:
        return jsonify({'error': 'No local credentials configured'}), 404

    try:
        user = db.get_user_by_username(username)
        if not user or not user.get('is_active'):
            return jsonify({'error': 'User not found or disabled'}), 401

        sb = get_supabase_client()
        auth_response = sb.auth.sign_in_with_password({
            'email': user['email'],
            'password': password,
        })
        session = auth_response.session
        if not session:
            return jsonify({'error': 'Auto-login failed'}), 401

        workspaces = db.get_workspaces_for_user(user['id'])
        return jsonify({
            'message': 'Auto-login successful',
            'user': user,
            'workspaces': workspaces,
            'access_token': session.access_token,
            'refresh_token': session.refresh_token,
        }), 200

    except Exception as e:
        print(f"Auto-login error: {e}")
        return jsonify({'error': 'Auto-login failed'}), 401


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout — evict the current token from the server cache."""
    token = _extract_bearer_token()
    if token:
        _user_cache.pop(token, None)
    return jsonify({'message': 'Logout successful'}), 200


@auth_bp.route('/current-user', methods=['GET'])
@login_required
def current_user_endpoint():
    """Get current authenticated user info."""
    try:
        user = get_current_user()
        workspaces = db.get_workspaces_for_user(user['id'])

        return jsonify({
            'user': user,
            'workspaces': workspaces
        }), 200

    except Exception as e:
        print(f"Get current user error: {e}")
        return jsonify({'error': 'Failed to get user info'}), 500


@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    """Check if user is authenticated (doesn't require login)."""
    user = get_current_user()
    if user:
        return jsonify({
            'authenticated': True,
            'user': user
        }), 200
    else:
        return jsonify({'authenticated': False}), 200


@auth_bp.route('/refresh-token', methods=['POST'])
def refresh_token():
    """Refresh an expired access token using the refresh token."""
    try:
        data = request.get_json()
        refresh = data.get('refresh_token', '')
        if not refresh:
            return jsonify({'error': 'Refresh token required'}), 400

        sb = get_supabase_client()
        auth_response = sb.auth.refresh_session(refresh)
        session = auth_response.session
        if not session:
            return jsonify({'error': 'Token refresh failed'}), 401

        return jsonify({
            'access_token': session.access_token,
            'refresh_token': session.refresh_token,
        }), 200
    except Exception as e:
        print(f"Token refresh error: {e}")
        return jsonify({'error': 'Token refresh failed'}), 401


ALLOWED_PREFERENCE_KEYS = {'selectedWorkspaceId', 'editorTabsState', 'theme'}


@auth_bp.route('/preferences', methods=['GET'])
@login_required
def get_preferences():
    """Get all user preferences."""
    try:
        user = get_current_user()
        prefs = db.get_preferences(user['id'])
        return jsonify({'preferences': prefs}), 200
    except Exception as e:
        print(f"Get preferences error: {e}")
        return jsonify({'error': 'Failed to get preferences'}), 500


@auth_bp.route('/preferences', methods=['PUT'])
@login_required
def update_preferences():
    """Update one or more user preferences."""
    try:
        user = get_current_user()
        data = request.get_json()
        preferences = data.get('preferences', {})

        if not preferences:
            return jsonify({'error': 'No preferences provided'}), 400

        invalid_keys = set(preferences.keys()) - ALLOWED_PREFERENCE_KEYS
        if invalid_keys:
            return jsonify({'error': f'Invalid preference keys: {", ".join(invalid_keys)}'}), 400

        db.update_preferences(user['id'], preferences)
        return jsonify({'message': 'Preferences updated'}), 200

    except Exception as e:
        print(f"Update preferences error: {e}")
        return jsonify({'error': 'Failed to update preferences'}), 500
