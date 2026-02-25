"""
One-time migration script: initialize git repos for all existing workspaces.

Run manually before deploying the git-integration-sidebar feature:
    python migrate_to_git.py

For each existing workspace directory that is NOT already a git repo:
  - Initializes a git repo
  - Writes a .gitignore
  - Stages all .py and .md files + .gitignore
  - Makes an initial commit
"""

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent))

import git
from config import Config

GITIGNORE_CONTENT = """\
# AutoGen Web Tester - workspace gitignore
saved_tests/artifacts/
ai_steps/artifacts/
__pycache__/
*.meta.json
*.pyc
"""

COMMIT_MESSAGE = "Initial commit — migrated from AutoGen Web Tester"


def migrate_workspace(ws_dir: Path) -> None:
    if (ws_dir / '.git').exists():
        print(f"  [skip] {ws_dir.name} — already a git repo")
        return

    print(f"  [init] {ws_dir.name}")
    repo = git.Repo.init(ws_dir)

    # Set default branch to 'main'
    try:
        repo.git.symbolic_ref('HEAD', 'refs/heads/main')
    except git.exc.GitCommandError:
        pass

    # Write .gitignore
    gitignore_path = ws_dir / '.gitignore'
    gitignore_path.write_text(GITIGNORE_CONTENT, encoding='utf-8')

    # Collect files to stage: .gitignore + all .py and .md files
    files_to_stage = ['.gitignore']
    for pattern in ('**/*.py', '**/*.md'):
        for f in ws_dir.glob(pattern):
            # Skip artifacts directories
            rel = f.relative_to(ws_dir)
            parts = rel.parts
            if 'artifacts' in parts or '__pycache__' in parts:
                continue
            files_to_stage.append(str(rel))

    if files_to_stage:
        repo.index.add(files_to_stage)

    commit = repo.index.commit(COMMIT_MESSAGE)
    print(f"  [done] {ws_dir.name} — initial commit {commit.hexsha[:7]}")


def main():
    workspaces_dir = Config.AUTOGEN_WORKSPACES_DIR
    if not workspaces_dir.is_dir():
        print(f"No workspaces directory found at {workspaces_dir}")
        return

    workspaces = [d for d in workspaces_dir.iterdir() if d.is_dir()]
    if not workspaces:
        print("No workspaces to migrate.")
        return

    print(f"Migrating {len(workspaces)} workspace(s) in {workspaces_dir}...\n")
    for ws_dir in sorted(workspaces):
        try:
            migrate_workspace(ws_dir)
        except Exception as e:
            print(f"  [error] {ws_dir.name}: {e}")

    print("\nMigration complete.")


if __name__ == '__main__':
    main()
