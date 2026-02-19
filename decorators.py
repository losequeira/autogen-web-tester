"""
Access control decorators for workspace-aware endpoints.

Provides permission checking for workspace operations.
"""

from functools import wraps
from flask import jsonify
from auth import get_current_user
import db


def workspace_access_required(permission='read'):
    """
    Decorator to check if user has access to a workspace.

    Args:
        permission: Required permission level ('read' or 'write')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(workspace_id=None, *args, **kwargs):
            if workspace_id is None:
                return jsonify({'error': 'Workspace ID is required'}), 400

            user = get_current_user()
            if user is None:
                return jsonify({'error': 'Authentication required'}), 401

            workspace = db.get_workspace_by_id(workspace_id)
            if not workspace:
                return jsonify({'error': 'Workspace not found'}), 404

            if not db.workspace_has_access(workspace_id, user['id'], permission):
                return jsonify({'error': 'Access denied'}), 403

            return f(workspace_id=workspace_id, *args, **kwargs)

        return decorated_function
    return decorator


def workspace_owner_required():
    """
    Decorator to check if user is the owner of a workspace.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(workspace_id=None, *args, **kwargs):
            if workspace_id is None:
                return jsonify({'error': 'Workspace ID is required'}), 400

            user = get_current_user()
            if user is None:
                return jsonify({'error': 'Authentication required'}), 401

            workspace = db.get_workspace_by_id(workspace_id)
            if not workspace:
                return jsonify({'error': 'Workspace not found'}), 404

            if workspace['owner_id'] != user['id']:
                return jsonify({'error': 'Only workspace owner can perform this action'}), 403

            return f(workspace_id=workspace_id, *args, **kwargs)

        return decorated_function
    return decorator
