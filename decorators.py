"""
Access control decorators for workspace-aware endpoints.

Provides permission checking for workspace operations.
"""

from functools import wraps
from flask import jsonify
from flask_login import current_user
from models import Workspace, get_db_session


def workspace_access_required(permission='read'):
    """
    Decorator to check if user has access to a workspace.

    Args:
        permission: Required permission level ('read' or 'write')

    Usage:
        @app.route('/api/workspaces/<int:workspace_id>/tests')
        @login_required
        @workspace_access_required(permission='read')
        def get_tests(workspace_id):
            # User has read access to workspace
            pass

    Returns:
        - 401 if not authenticated (handled by @login_required)
        - 404 if workspace not found
        - 403 if user doesn't have required permission
        - Calls wrapped function if access is granted
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(workspace_id=None, *args, **kwargs):
            # Ensure workspace_id is provided
            if workspace_id is None:
                return jsonify({'error': 'Workspace ID is required'}), 400

            db = get_db_session()

            # Get workspace
            workspace = db.query(Workspace).filter(
                Workspace.id == workspace_id
            ).first()

            if not workspace:
                return jsonify({'error': 'Workspace not found'}), 404

            # Check if user has required permission
            if not workspace.has_access(current_user.id, permission):
                return jsonify({'error': 'Access denied'}), 403

            # User has access - call the wrapped function
            return f(workspace_id=workspace_id, *args, **kwargs)

        return decorated_function
    return decorator


def workspace_owner_required():
    """
    Decorator to check if user is the owner of a workspace.

    Stricter than workspace_access_required - only owners can perform certain actions
    like deleting workspaces or changing settings.

    Usage:
        @app.route('/api/workspaces/<int:workspace_id>', methods=['DELETE'])
        @login_required
        @workspace_owner_required()
        def delete_workspace(workspace_id):
            # User is the owner
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(workspace_id=None, *args, **kwargs):
            if workspace_id is None:
                return jsonify({'error': 'Workspace ID is required'}), 400

            db = get_db_session()

            workspace = db.query(Workspace).filter(
                Workspace.id == workspace_id
            ).first()

            if not workspace:
                return jsonify({'error': 'Workspace not found'}), 404

            # Check if user is the owner
            if workspace.owner_id != current_user.id:
                return jsonify({'error': 'Only workspace owner can perform this action'}), 403

            return f(workspace_id=workspace_id, *args, **kwargs)

        return decorated_function
    return decorator
