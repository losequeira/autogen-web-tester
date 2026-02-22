"""
Git operations for AutoGen Web Tester workspaces.
Each workspace directory is a git repository (1:1 mapping).
"""

from pathlib import Path
from typing import Optional

import git
import git.exc


def init_repo(workspace_path: Path) -> None:
    """Initialize a new git repo at workspace_path if it doesn't already have one."""
    workspace_path = Path(workspace_path)
    if (workspace_path / '.git').exists():
        return
    repo = git.Repo.init(workspace_path)
    # Set default branch name to 'main'
    try:
        repo.git.symbolic_ref('HEAD', 'refs/heads/main')
    except git.exc.GitCommandError:
        pass


def clone_repo(url: str, workspace_path: Path) -> None:
    """Clone a remote repository into workspace_path."""
    workspace_path = Path(workspace_path)
    if workspace_path.exists() and any(workspace_path.iterdir()):
        raise ValueError(f"Destination directory is not empty: {workspace_path}")
    git.Repo.clone_from(url, workspace_path)


def is_repo(workspace_path: Path) -> bool:
    """Return True if workspace_path contains a git repository."""
    workspace_path = Path(workspace_path)
    try:
        git.Repo(workspace_path)
        return True
    except git.exc.InvalidGitRepositoryError:
        return False
    except Exception:
        return False


def _get_repo(workspace_path: Path) -> git.Repo:
    """Open the git repo at workspace_path, raise ValueError if not a repo."""
    try:
        return git.Repo(Path(workspace_path))
    except git.exc.InvalidGitRepositoryError:
        raise ValueError(f"Not a git repository: {workspace_path}")


def get_status(workspace_path: Path) -> dict:
    """
    Return current git status for the workspace.
    Returns:
        {
            branch: str,
            tracking: str | None,
            ahead: int,
            behind: int,
            staged: list[{path, status}],
            unstaged: list[{path, status}],
            untracked: list[str],
        }
    """
    repo = _get_repo(workspace_path)

    # Branch info
    try:
        branch = repo.active_branch.name
    except TypeError:
        branch = repo.head.commit.hexsha[:7] if not repo.head.is_detached else 'HEAD'

    tracking = None
    ahead = 0
    behind = 0
    try:
        tracking_branch = repo.active_branch.tracking_branch()
        if tracking_branch:
            tracking = tracking_branch.name
            commits_ahead = list(repo.iter_commits(f'{tracking_branch.name}..HEAD'))
            commits_behind = list(repo.iter_commits(f'HEAD..{tracking_branch.name}'))
            ahead = len(commits_ahead)
            behind = len(commits_behind)
    except Exception:
        pass

    # Staged changes (diff between index and HEAD)
    staged = []
    try:
        if repo.head.is_valid():
            for diff in repo.index.diff('HEAD'):
                staged.append({'path': diff.b_path or diff.a_path, 'status': diff.change_type})
        else:
            # New repo with no commits — all indexed items are staged
            for entry in repo.index.entries:
                staged.append({'path': entry[0], 'status': 'A'})
    except Exception:
        pass

    # Unstaged changes (diff between working tree and index)
    unstaged = []
    try:
        for diff in repo.index.diff(None):
            unstaged.append({'path': diff.b_path or diff.a_path, 'status': diff.change_type})
    except Exception:
        pass

    # Untracked files
    untracked = list(repo.untracked_files)

    return {
        'branch': branch,
        'tracking': tracking,
        'ahead': ahead,
        'behind': behind,
        'staged': staged,
        'unstaged': unstaged,
        'untracked': untracked,
    }


def stage_file(workspace_path: Path, filepath: str) -> None:
    """Stage a specific file."""
    repo = _get_repo(workspace_path)
    repo.index.add([filepath])


def unstage_file(workspace_path: Path, filepath: str) -> None:
    """Unstage a specific file (reset to HEAD)."""
    repo = _get_repo(workspace_path)
    try:
        repo.index.reset([filepath])
    except Exception:
        # If no HEAD yet, just remove from index
        repo.index.remove([filepath], cached=True)


def stage_all(workspace_path: Path) -> None:
    """Stage all modified, new, and deleted files."""
    repo = _get_repo(workspace_path)
    repo.git.add('--all')


def commit(
    workspace_path: Path,
    message: str,
    author_name: Optional[str] = None,
    author_email: Optional[str] = None,
) -> str:
    """Commit staged changes. Returns the new commit SHA."""
    repo = _get_repo(workspace_path)
    kwargs = {'message': message}
    if author_name and author_email:
        from git import Actor
        author = Actor(author_name, author_email)
        kwargs['author'] = author
    commit_obj = repo.index.commit(**kwargs)
    return commit_obj.hexsha


def push(
    workspace_path: Path,
    remote: str = 'origin',
    branch: Optional[str] = None,
    token: Optional[str] = None,
) -> None:
    """Push to remote. Optionally inject a token into the remote URL for HTTPS auth."""
    repo = _get_repo(workspace_path)

    if branch is None:
        try:
            branch = repo.active_branch.name
        except TypeError:
            raise ValueError("Cannot determine current branch for push")

    if token:
        # Inject token into remote URL temporarily
        remote_obj = repo.remote(remote)
        original_url = remote_obj.url
        try:
            authed_url = _inject_token(original_url, token)
            remote_obj.set_url(authed_url)
            remote_obj.push(refspec=f'{branch}:{branch}')
        finally:
            remote_obj.set_url(original_url)
    else:
        repo.remote(remote).push(refspec=f'{branch}:{branch}')


def pull(
    workspace_path: Path,
    remote: str = 'origin',
    branch: Optional[str] = None,
) -> None:
    """Pull from remote."""
    repo = _get_repo(workspace_path)
    if branch is None:
        try:
            branch = repo.active_branch.name
        except TypeError:
            raise ValueError("Cannot determine current branch for pull")
    repo.remote(remote).pull(branch)


def get_branches(workspace_path: Path) -> dict:
    """Return branch information: {current, local[], remote[]}."""
    repo = _get_repo(workspace_path)

    try:
        current = repo.active_branch.name
    except TypeError:
        current = None

    local = [b.name for b in repo.branches]
    remote = [ref.name for ref in repo.remote().refs] if repo.remotes else []

    return {
        'current': current,
        'local': local,
        'remote': remote,
    }


def checkout_branch(workspace_path: Path, branch: str, create: bool = False) -> None:
    """Switch to a branch. If create=True, create a new branch first."""
    repo = _get_repo(workspace_path)
    if create:
        repo.git.checkout('-b', branch)
    else:
        repo.git.checkout(branch)


def get_diff(workspace_path: Path, filepath: str, staged: bool = False) -> str:
    """
    Return unified diff for a file.
    staged=True: diff between index and HEAD (staged changes)
    staged=False: diff between working tree and index (unstaged changes)
    """
    repo = _get_repo(workspace_path)
    try:
        if staged:
            if repo.head.is_valid():
                diff = repo.git.diff('--cached', '--', filepath)
            else:
                diff = repo.git.diff('--cached', '--', filepath)
        else:
            diff = repo.git.diff('--', filepath)
        return diff
    except git.exc.GitCommandError as e:
        raise ValueError(f"Could not get diff for {filepath}: {e}") from e


def get_log(workspace_path: Path, max_count: int = 20) -> list:
    """Return a list of recent commits as dicts."""
    repo = _get_repo(workspace_path)
    commits = []
    try:
        for c in repo.iter_commits(max_count=max_count):
            commits.append({
                'sha': c.hexsha,
                'short_sha': c.hexsha[:7],
                'message': c.message.strip(),
                'author': c.author.name,
                'email': c.author.email,
                'date': c.committed_datetime.isoformat(),
            })
    except Exception:
        pass
    return commits


def _inject_token(url: str, token: str) -> str:
    """Inject a PAT token into an HTTPS remote URL."""
    if url.startswith('https://'):
        return url.replace('https://', f'https://{token}@', 1)
    if url.startswith('http://'):
        return url.replace('http://', f'http://{token}@', 1)
    return url


# ──────────────────────────────────────────────
# Remote helpers
# ──────────────────────────────────────────────


def get_remote_url(workspace_path: Path, remote: str = 'origin') -> str | None:
    """Return the URL for *remote*, or None if the remote doesn't exist."""
    repo = _get_repo(workspace_path)
    try:
        return repo.remote(remote).url
    except ValueError:
        return None


def add_remote(workspace_path: Path, url: str, remote: str = 'origin') -> None:
    """Add *remote* pointing at *url*, or update URL if it already exists."""
    repo = _get_repo(workspace_path)
    try:
        repo.remote(remote).set_url(url)
    except ValueError:
        repo.create_remote(remote, url)


def remove_remote(workspace_path: Path, remote: str = 'origin') -> None:
    """Delete *remote* if it exists; no-op otherwise."""
    repo = _get_repo(workspace_path)
    try:
        repo.delete_remote(repo.remote(remote))
    except ValueError:
        pass
