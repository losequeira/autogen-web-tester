"""
Data access layer using the Supabase SDK (PostgREST).

Replaces SQLAlchemy ORM (models.py) and the old data_access.py.
All database operations go through supabase_client.get_supabase_client().table(...).
"""

from datetime import datetime
from enum import Enum as PyEnum
from pathlib import Path

from supabase_client import get_supabase_client


# ========== Enums (plain Python, no SQLAlchemy) ==========

class WorkspaceType(PyEnum):
    PRIVATE = 'private'
    SHARED = 'shared'


class WorkspaceRole(PyEnum):
    OWNER = 'owner'
    EDITOR = 'editor'
    VIEWER = 'viewer'


class TestSource(PyEnum):
    AI = 'ai'
    CODEGEN = 'codegen'
    MANUAL = 'manual'


# ========== Helpers ==========

def _sb():
    return get_supabase_client()


def sanitize_test_filename(name: str) -> str:
    """Generate a .py filename for a test."""
    filename = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    return filename.replace(' ', '_') + '.py'


def sanitize_filename(name: str) -> str:
    """Generate a .json filename (used for AI steps)."""
    filename = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    return filename.replace(' ', '_') + '.json'


# ========== Users ==========

def get_user_by_id(user_id: str) -> dict | None:
    resp = _sb().table('users').select('*').eq('id', user_id).execute()
    return resp.data[0] if resp.data else None


def get_user_by_username(username: str) -> dict | None:
    resp = _sb().table('users').select('*').eq('username', username).execute()
    return resp.data[0] if resp.data else None


def get_user_by_email(email: str) -> dict | None:
    resp = _sb().table('users').select('*').eq('email', email).execute()
    return resp.data[0] if resp.data else None


def create_user(id: str, username: str, email: str) -> dict:
    resp = _sb().table('users').insert({
        'id': id,
        'username': username,
        'email': email,
        'is_active': True,
    }).execute()
    return resp.data[0]


# ========== Workspaces ==========

def get_workspace_by_id(workspace_id: int) -> dict | None:
    resp = _sb().table('workspaces').select('*, users!workspaces_owner_id_fkey(username)').eq('id', workspace_id).execute()
    if not resp.data:
        return None
    ws = resp.data[0]
    # Flatten owner_username
    owner = ws.pop('users', None)
    ws['owner_username'] = owner['username'] if owner else None
    return ws


def get_workspaces_for_user(user_id: str) -> list[dict]:
    """Get all workspaces the user owns or is a member of."""
    # Owned
    owned_resp = _sb().table('workspaces').select(
        '*, users!workspaces_owner_id_fkey(username)'
    ).eq('owner_id', user_id).execute()

    # Shared (user is a member)
    member_resp = _sb().table('workspace_members').select(
        'workspace_id'
    ).eq('user_id', user_id).execute()

    shared_ids = [m['workspace_id'] for m in (member_resp.data or [])]

    shared_workspaces = []
    if shared_ids:
        shared_resp = _sb().table('workspaces').select(
            '*, users!workspaces_owner_id_fkey(username)'
        ).in_('id', shared_ids).execute()
        shared_workspaces = shared_resp.data or []

    # Merge and deduplicate
    all_ws = {w['id']: w for w in (owned_resp.data or []) + shared_workspaces}

    result = []
    for ws in all_ws.values():
        result.append(_format_workspace(ws))
    return result


def create_workspace(name: str, ws_type: str, owner_id: str) -> dict:
    resp = _sb().table('workspaces').insert({
        'name': name,
        'type': ws_type,
        'owner_id': owner_id,
    }).execute()
    ws = resp.data[0]
    # Fetch owner username for the response
    user = get_user_by_id(owner_id)
    ws['owner_username'] = user['username'] if user else None
    return _format_workspace(ws)


def workspace_has_access(workspace_id: int, user_id: str, permission: str = 'read') -> bool:
    ws = get_workspace_by_id(workspace_id)
    if not ws:
        return False

    # Owner has all permissions
    if ws['owner_id'] == user_id:
        return True

    # Check membership
    member_resp = _sb().table('workspace_members').select('role').eq(
        'workspace_id', workspace_id
    ).eq('user_id', user_id).execute()

    if not member_resp.data:
        return False

    role = member_resp.data[0]['role']

    if permission == 'read':
        return True  # All members can read

    if permission == 'write':
        return role in ('owner', 'editor')

    return False


def workspace_is_owner(workspace_id: int, user_id: str) -> bool:
    ws = get_workspace_by_id(workspace_id)
    if not ws:
        return False
    return ws['owner_id'] == user_id


def _format_workspace(ws: dict) -> dict:
    """Normalize a workspace row into a consistent dict."""
    owner = ws.pop('users', None)
    if 'owner_username' not in ws:
        ws['owner_username'] = owner['username'] if owner else None

    # Get counts
    test_count_resp = _sb().table('tests').select('id', count='exact').eq('workspace_id', ws['id']).execute()
    ai_step_count_resp = _sb().table('ai_steps').select('id', count='exact').eq('workspace_id', ws['id']).execute()

    ws['test_count'] = test_count_resp.count if test_count_resp.count is not None else 0
    ws['ai_step_count'] = ai_step_count_resp.count if ai_step_count_resp.count is not None else 0

    # Get members
    members_resp = _sb().table('workspace_members').select(
        '*, users(username, email)'
    ).eq('workspace_id', ws['id']).execute()

    members = []
    for m in (members_resp.data or []):
        user_info = m.pop('users', None)
        m['username'] = user_info['username'] if user_info else None
        m['email'] = user_info['email'] if user_info else None
        members.append(m)
    ws['members'] = members

    return ws


# ========== Workspace Members ==========

def get_workspace_members(workspace_id: int) -> list[dict]:
    resp = _sb().table('workspace_members').select(
        '*, users(username, email)'
    ).eq('workspace_id', workspace_id).execute()

    members = []
    for m in (resp.data or []):
        user_info = m.pop('users', None)
        m['username'] = user_info['username'] if user_info else None
        m['email'] = user_info['email'] if user_info else None
        members.append(m)
    return members


def add_workspace_member(workspace_id: int, user_id: str, role: str) -> dict:
    resp = _sb().table('workspace_members').insert({
        'workspace_id': workspace_id,
        'user_id': user_id,
        'role': role,
    }).execute()
    member = resp.data[0]
    user = get_user_by_id(user_id)
    member['username'] = user['username'] if user else None
    member['email'] = user['email'] if user else None
    return member


def remove_workspace_member(workspace_id: int, user_id: str) -> bool:
    resp = _sb().table('workspace_members').delete().eq(
        'workspace_id', workspace_id
    ).eq('user_id', user_id).execute()
    return bool(resp.data)


def update_member_role(workspace_id: int, user_id: str, role: str) -> dict | None:
    resp = _sb().table('workspace_members').update({
        'role': role
    }).eq('workspace_id', workspace_id).eq('user_id', user_id).execute()
    if not resp.data:
        return None
    member = resp.data[0]
    user = get_user_by_id(user_id)
    member['username'] = user['username'] if user else None
    member['email'] = user['email'] if user else None
    return member


# ========== Tests ==========

def get_tests(workspace_id: int) -> list[dict]:
    resp = _sb().table('tests').select(
        '*, test_artifacts(timestamp, video_path, video_size_mb, har_path, status)'
    ).eq('workspace_id', workspace_id).order('created_at', desc=True).execute()

    results = []
    for t in (resp.data or []):
        artifacts = t.pop('test_artifacts', []) or []
        results.append({
            'filename': t['filename'],
            'name': t['name'],
            'code': t['code'],
            'created': t['created_at'],
            'source': t['source'],
            'last_run_status': t['last_run_status'],
            'last_run_time': t['last_run_time'],
            'artifacts': artifacts,
        })
    return results


def get_test(workspace_id: int, filename: str) -> dict | None:
    resp = _sb().table('tests').select(
        '*, test_artifacts(timestamp, video_path, video_size_mb, har_path, status)'
    ).eq('workspace_id', workspace_id).eq('filename', filename).execute()

    if not resp.data:
        return None

    t = resp.data[0]
    artifacts = t.pop('test_artifacts', []) or []
    return {
        'filename': t['filename'],
        'name': t['name'],
        'code': t['code'],
        'source': t['source'],
        'created': t['created_at'],
        'updated': t['updated_at'],
        'last_run_status': t['last_run_status'],
        'last_run_time': t['last_run_time'],
        'artifacts': artifacts,
    }


def create_test(workspace_id: int, name: str, code: str, source: str, user_id: str) -> dict:
    filename = sanitize_test_filename(name)

    # Check for duplicates
    existing = _sb().table('tests').select('id').eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()
    if existing.data:
        raise ValueError('Test with this name already exists')

    _sb().table('tests').insert({
        'filename': filename,
        'name': name,
        'code': code,
        'workspace_id': workspace_id,
        'source': source,
        'created_by': user_id,
    }).execute()

    return {'success': True, 'filename': filename}


def update_test(workspace_id: int, filename: str, **fields) -> dict | None:
    # Build update payload
    update_data = {}
    for key, value in fields.items():
        if key in ('name', 'code', 'last_run_status', 'description', 'source'):
            update_data[key] = value
        elif key == 'last_run_time':
            if isinstance(value, datetime):
                update_data['last_run_time'] = value.isoformat()
            else:
                update_data['last_run_time'] = value

    if not update_data:
        return None

    update_data['updated_at'] = datetime.utcnow().isoformat()

    resp = _sb().table('tests').update(update_data).eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()

    if not resp.data:
        return None
    return {'message': 'Test updated successfully'}


def delete_test(workspace_id: int, filename: str) -> bool:
    resp = _sb().table('tests').delete().eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()
    return bool(resp.data)


# ========== Test Artifacts ==========

def get_test_artifacts(workspace_id: int, filename: str) -> list[dict] | None:
    # First get the test
    test_resp = _sb().table('tests').select('id').eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()

    if not test_resp.data:
        return None

    test_id = test_resp.data[0]['id']
    resp = _sb().table('test_artifacts').select(
        'timestamp, video_path, video_size_mb, har_path, status'
    ).eq('test_id', test_id).order('created_at', desc=True).execute()

    return resp.data or []


def delete_test_artifacts(workspace_id: int, filename: str) -> None:
    """Delete all artifact rows and local files for a test."""
    from storage import delete_artifact
    from config import Config
    import shutil

    test_resp = _sb().table('tests').select('id').eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()

    if not test_resp.data:
        return

    test_id = test_resp.data[0]['id']

    # Fetch all rows to get file paths before deleting
    rows = _sb().table('test_artifacts').select('video_path, har_path').eq(
        'test_id', test_id
    ).execute().data or []

    for row in rows:
        if row.get('video_path'):
            delete_artifact(row['video_path'])
        if row.get('har_path'):
            delete_artifact(row['har_path'])

    # Delete the test dir entirely if empty
    test_name = Path(filename).stem
    test_dir = Config.ARTIFACTS_DIR / str(workspace_id) / test_name
    try:
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass

    _sb().table('test_artifacts').delete().eq('test_id', test_id).execute()


def add_test_artifact(workspace_id: int, filename: str, artifact_dir: Path, status: str):
    """Save the latest recording to disk and upsert one artifact row per test."""
    import shutil
    from storage import save_artifact_dir

    test_resp = _sb().table('tests').select('id').eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()

    if not test_resp.data:
        print(f"Warning: Test not found for artifact update: {filename}")
        return

    test_id = test_resp.data[0]['id']
    artifact_dir_abs = artifact_dir.resolve()
    test_name = Path(filename).stem
    timestamp = datetime.utcnow().isoformat()

    # Move files to fixed path ~/.autogen/artifacts/{workspace_id}/{test_name}/
    storage_paths = save_artifact_dir(artifact_dir_abs, workspace_id, test_name)

    video_size_mb = 0
    if storage_paths.get('video_local'):
        video_size_mb = storage_paths['video_local'].stat().st_size / (1024 * 1024)

    # Upsert: replace any existing artifact row for this test with the latest run
    _sb().table('test_artifacts').delete().eq('test_id', test_id).execute()
    _sb().table('test_artifacts').insert({
        'test_id': test_id,
        'timestamp': timestamp,
        'video_path': storage_paths.get('video_path'),
        'video_size_mb': round(video_size_mb, 2),
        'har_path': storage_paths.get('har_path'),
        'status': status,
    }).execute()

    _sb().table('tests').update({
        'last_run_status': status,
        'last_run_time': timestamp,
        'updated_at': timestamp,
    }).eq('id', test_id).execute()

    print(f"Artifact saved: {storage_paths.get('video_path')}")

    # Clean up Playwright temp dir
    try:
        if artifact_dir_abs.exists():
            shutil.rmtree(artifact_dir_abs)
    except Exception as e:
        print(f"Warning: Could not remove temp dir: {e}")


def get_recent_recordings(workspace_id: int, limit: int = 20) -> list[dict]:
    """Get recent test artifacts with video recordings for a workspace."""
    resp = _sb().table('test_artifacts').select(
        '*, tests!inner(filename, name, workspace_id)'
    ).neq('video_path', '').neq('video_path', 'null').not_.is_('video_path', 'null').order(
        'created_at', desc=True
    ).limit(limit).execute()

    results = []
    for a in (resp.data or []):
        test_info = a.get('tests', {})
        # Filter by workspace_id (inner join doesn't support .eq on related table in all SDK versions)
        if test_info.get('workspace_id') != workspace_id:
            continue
        results.append({
            'test_filename': test_info.get('filename'),
            'test_name': test_info.get('name'),
            'timestamp': a['timestamp'],
            'video_path': a['video_path'],
            'video_size_mb': a.get('video_size_mb'),
            'har_path': a.get('har_path'),
            'status': a.get('status'),
            'created_at': a.get('created_at'),
        })
    return results


# ========== AI Steps ==========

def get_ai_steps(workspace_id: int) -> list[dict]:
    resp = _sb().table('ai_steps').select('*').eq(
        'workspace_id', workspace_id
    ).order('created_at', desc=True).execute()

    return [{
        'id': s['id'],
        'filename': s['filename'],
        'name': s['name'],
        'created': s['created_at'],
        'last_run_status': s['last_run_status'],
        'last_run_time': s['last_run_time'],
    } for s in (resp.data or [])]


def get_ai_step(workspace_id: int, filename: str) -> dict | None:
    resp = _sb().table('ai_steps').select('*').eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()

    if not resp.data:
        return None

    s = resp.data[0]
    return {
        'id': s['id'],
        'filename': s['filename'],
        'name': s['name'],
        'steps': s['steps'],
        'created': s['created_at'],
        'updated': s['updated_at'],
        'last_run': s['last_run_time'],
        'last_run_status': s['last_run_status'],
        'last_run_time': s['last_run_time'],
        'status': s['last_run_status'],
    }


def get_ai_step_by_id(step_id: int, workspace_id: int = None) -> dict | None:
    query = _sb().table('ai_steps').select('*').eq('id', step_id)
    if workspace_id is not None:
        query = query.eq('workspace_id', workspace_id)
    resp = query.execute()

    if not resp.data:
        return None

    s = resp.data[0]
    return {
        'id': s['id'],
        'filename': s['filename'],
        'name': s['name'],
        'steps': s['steps'],
        'workspace_id': s['workspace_id'],
        'created': s['created_at'],
        'updated': s['updated_at'],
        'last_run': s['last_run_time'],
        'last_run_status': s['last_run_status'],
        'last_run_time': s['last_run_time'],
        'status': s['last_run_status'],
    }


def create_ai_step(workspace_id: int, name: str, steps: str, user_id: str) -> dict:
    filename = sanitize_filename(name)

    existing = _sb().table('ai_steps').select('id').eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()
    if existing.data:
        raise ValueError('AI step with this name already exists')

    _sb().table('ai_steps').insert({
        'filename': filename,
        'name': name,
        'steps': steps,
        'workspace_id': workspace_id,
        'created_by': user_id,
    }).execute()

    return {'success': True, 'filename': filename}


def update_ai_step(workspace_id: int, filename: str, **fields) -> dict | None:
    update_data = {}
    for key, value in fields.items():
        if key in ('name', 'steps'):
            update_data[key] = value
        elif key == 'last_run_status' or key == 'status':
            update_data['last_run_status'] = value
        elif key in ('last_run', 'last_run_time'):
            if isinstance(value, datetime):
                update_data['last_run_time'] = value.isoformat()
            else:
                update_data['last_run_time'] = value

    if not update_data:
        return None

    update_data['updated_at'] = datetime.utcnow().isoformat()

    resp = _sb().table('ai_steps').update(update_data).eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()

    if not resp.data:
        return None
    return {'success': True}


def delete_ai_step(workspace_id: int, filename: str) -> bool:
    resp = _sb().table('ai_steps').delete().eq(
        'workspace_id', workspace_id
    ).eq('filename', filename).execute()
    return bool(resp.data)


# ========== User Preferences ==========

def get_preferences(user_id: str) -> dict:
    resp = _sb().table('user_preferences').select('key, value').eq('user_id', user_id).execute()
    return {p['key']: p['value'] for p in (resp.data or [])}


def update_preferences(user_id: str, preferences: dict) -> bool:
    for key, value in preferences.items():
        str_value = value if isinstance(value, str) else str(value)
        # Upsert: insert or update on conflict
        _sb().table('user_preferences').upsert({
            'user_id': user_id,
            'key': key,
            'value': str_value,
            'updated_at': datetime.utcnow().isoformat(),
        }, on_conflict='user_id,key').execute()
    return True


# ========== Helpers ==========

def get_default_workspace_id(user_id: str) -> int | None:
    resp = _sb().table('workspaces').select('id').eq(
        'owner_id', user_id
    ).order('created_at').limit(1).execute()
    return resp.data[0]['id'] if resp.data else None
