"""
Access control decorators for workspace-aware endpoints.

Workspaces are purely local directories under ~/.autogen/workspaces/<name>/.
Access check: the directory must exist.
"""

from functools import wraps
from flask import jsonify
from config import Config


def workspace_access_required(permission='read'):
    """
    Decorator to check that the workspace directory exists.

    Returns 404 if AUTOGEN_WORKSPACES_DIR/<workspace_name> does not exist.
    The permission argument is accepted for API compatibility but not used.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(workspace_name=None, *args, **kwargs):
            if not workspace_name:
                return jsonify({'error': 'Workspace name is required'}), 400

            ws_dir = Config.AUTOGEN_WORKSPACES_DIR / workspace_name
            if not ws_dir.is_dir():
                return jsonify({'error': 'Workspace not found'}), 404

            return f(workspace_name=workspace_name, *args, **kwargs)

        return decorated_function
    return decorator
