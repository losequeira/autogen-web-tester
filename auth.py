"""
Authentication module for AutoGen Web Tester.

Provides Flask-Login integration, user registration, login, and logout endpoints.
"""

import re
import hmac
from flask import Blueprint, jsonify, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import User, UserPreference, Workspace, WorkspaceType, get_db_session
from functools import wraps

# Create Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api')

# Initialize Flask-Login
login_manager = LoginManager()


def init_auth(app):
    """Initialize authentication with Flask app."""
    login_manager.init_app(app)
    login_manager.session_protection = 'strong'
    login_manager.login_view = None  # API doesn't redirect, just returns 401

    # Register blueprint
    app.register_blueprint(auth_bp)


@login_manager.user_loader
def load_user(user_id):
    """Load user from database by ID for Flask-Login."""
    db = get_db_session()
    return db.query(User).filter(User.id == int(user_id)).first()


@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access for API endpoints."""
    return jsonify({'error': 'Authentication required'}), 401


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username: str) -> bool:
    """Validate username format (alphanumeric, underscore, hyphen, 3-20 chars)."""
    pattern = r'^[a-zA-Z0-9_-]{3,20}$'
    return re.match(pattern, username) is not None


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.

    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"

    return True, ""


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user account.

    Expected JSON: {username, email, password}
    Creates user + default private workspace.
    """
    try:
        data = request.get_json()

        # Validate required fields
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not all([username, email, password]):
            return jsonify({'error': 'Username, email, and password are required'}), 400

        # Validate username format
        if not validate_username(username):
            return jsonify({
                'error': 'Username must be 3-20 characters and contain only letters, numbers, underscores, and hyphens'
            }), 400

        # Validate email format
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400

        # Validate password strength
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        db = get_db_session()

        # Check if username already exists
        if db.query(User).filter(User.username == username).first():
            return jsonify({'error': 'Username already exists'}), 409

        # Check if email already exists
        if db.query(User).filter(User.email == email).first():
            return jsonify({'error': 'Email already registered'}), 409

        # Create new user
        user = User(
            username=username,
            email=email,
            is_active=True
        )
        user.set_password(password)

        db.add(user)
        db.flush()  # Get user.id before creating workspace

        # Create default private workspace for user
        default_workspace = Workspace(
            name=f"{username}'s Workspace",
            type=WorkspaceType.PRIVATE,
            owner_id=user.id
        )
        db.add(default_workspace)

        db.commit()

        # Auto-login after registration
        login_user(user, remember=True)

        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict(),
            'default_workspace_id': default_workspace.id
        }), 201

    except Exception as e:
        db.rollback()
        print(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and create session.

    Expected JSON: {username, password, remember}
    """
    try:
        data = request.get_json()

        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        db = get_db_session()

        # Find user by username
        user = db.query(User).filter(User.username == username).first()

        if not user:
            return jsonify({'error': 'Invalid username or password'}), 401

        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403

        # Verify password
        if not user.check_password(password):
            return jsonify({'error': 'Invalid username or password'}), 401

        # Create session
        login_user(user, remember=remember)

        # Get user's workspaces (owned + shared)
        owned_workspaces = db.query(Workspace).filter(
            Workspace.owner_id == user.id
        ).all()

        shared_workspaces = db.query(Workspace).join(
            Workspace.members
        ).filter(
            Workspace.members.any(user_id=user.id)
        ).all()

        all_workspaces = owned_workspaces + shared_workspaces

        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'workspaces': [w.to_dict() for w in all_workspaces]
        }), 200

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Log out current user and destroy session."""
    try:
        logout_user()
        session.clear()
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({'error': 'Logout failed'}), 500


@auth_bp.route('/current-user', methods=['GET'])
@login_required
def get_current_user():
    """Get current authenticated user info."""
    try:
        db = get_db_session()

        # Get user's workspaces
        owned_workspaces = db.query(Workspace).filter(
            Workspace.owner_id == current_user.id
        ).all()

        shared_workspaces = db.query(Workspace).join(
            Workspace.members
        ).filter(
            Workspace.members.any(user_id=current_user.id)
        ).all()

        all_workspaces = owned_workspaces + shared_workspaces

        return jsonify({
            'user': current_user.to_dict(),
            'workspaces': [w.to_dict() for w in all_workspaces]
        }), 200

    except Exception as e:
        print(f"Get current user error: {e}")
        return jsonify({'error': 'Failed to get user info'}), 500


@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    """Check if user is authenticated (doesn't require login)."""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': current_user.to_dict()
        }), 200
    else:
        return jsonify({'authenticated': False}), 200


ALLOWED_PREFERENCE_KEYS = {'selectedWorkspaceId', 'editorTabsState'}


@auth_bp.route('/preferences', methods=['GET'])
@login_required
def get_preferences():
    """Get all user preferences."""
    try:
        db = get_db_session()
        prefs = db.query(UserPreference).filter(
            UserPreference.user_id == current_user.id
        ).all()

        result = {}
        for pref in prefs:
            result[pref.key] = pref.value

        return jsonify({'preferences': result}), 200
    except Exception as e:
        print(f"Get preferences error: {e}")
        return jsonify({'error': 'Failed to get preferences'}), 500


@auth_bp.route('/preferences', methods=['PUT'])
@login_required
def update_preferences():
    """
    Update one or more user preferences.

    Expected JSON: {preferences: {key: value, ...}}
    """
    try:
        data = request.get_json()
        preferences = data.get('preferences', {})

        if not preferences:
            return jsonify({'error': 'No preferences provided'}), 400

        # Validate keys
        invalid_keys = set(preferences.keys()) - ALLOWED_PREFERENCE_KEYS
        if invalid_keys:
            return jsonify({'error': f'Invalid preference keys: {", ".join(invalid_keys)}'}), 400

        db = get_db_session()

        for key, value in preferences.items():
            pref = db.query(UserPreference).filter(
                UserPreference.user_id == current_user.id,
                UserPreference.key == key
            ).first()

            if pref:
                pref.value = value if isinstance(value, str) else str(value)
            else:
                pref = UserPreference(
                    user_id=current_user.id,
                    key=key,
                    value=value if isinstance(value, str) else str(value)
                )
                db.add(pref)

        db.commit()
        return jsonify({'message': 'Preferences updated'}), 200

    except Exception as e:
        db.rollback()
        print(f"Update preferences error: {e}")
        return jsonify({'error': 'Failed to update preferences'}), 500
