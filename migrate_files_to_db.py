#!/usr/bin/env python3
"""
One-time migration script: moves test and AI step data from JSON files to SQLite.

Reads from:
  - user_data/workspaces/{id}/saved_tests/*.json
  - user_data/workspaces/{id}/ai_steps/*.json
  - saved_tests/*.json (legacy global)
  - ai_steps/*.json (legacy global)

Writes to: SQLite tables (tests, ai_steps, test_artifacts)

JSON files are NOT deleted — they serve as backup.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from models import (
    AiStep, Test, TestArtifact, TestSource, User, Workspace,
    get_db_session, init_db,
)


def parse_iso_datetime(s):
    """Parse an ISO datetime string, returning None on failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def migrate_workspace_tests(workspace_id: int, tests_dir: Path, owner_id: int, db):
    """Migrate JSON test files for a specific workspace."""
    if not tests_dir.exists():
        return 0

    count = 0
    for filepath in tests_dir.glob('*.json'):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            filename = filepath.name

            # Skip if already migrated
            existing = db.query(Test).filter(
                Test.workspace_id == workspace_id,
                Test.filename == filename
            ).first()

            if existing:
                # Update code if missing
                if not existing.code and data.get('code'):
                    existing.code = data['code']
                    print(f"  Updated code for existing test: {filename}")
            else:
                source_str = data.get('source', 'manual')
                source = {'ai': TestSource.AI, 'codegen': TestSource.CODEGEN}.get(source_str, TestSource.MANUAL)

                test = Test(
                    filename=filename,
                    name=data.get('name', filename.replace('.json', '').replace('_', ' ')),
                    code=data.get('code', ''),
                    workspace_id=workspace_id,
                    source=source,
                    created_by=owner_id,
                    created_at=parse_iso_datetime(data.get('created')) or datetime.utcnow(),
                    updated_at=parse_iso_datetime(data.get('updated')) or datetime.utcnow(),
                    last_run_status=data.get('last_run_status'),
                    last_run_time=parse_iso_datetime(data.get('last_run_time')),
                )
                db.add(test)
                db.flush()  # get test.id

                existing = test
                print(f"  Migrated test: {filename}")

            # Migrate artifacts
            for artifact_data in data.get('artifacts', []):
                # Check if artifact already exists
                ts = artifact_data.get('timestamp', '')
                already = db.query(TestArtifact).filter(
                    TestArtifact.test_id == existing.id,
                    TestArtifact.timestamp == ts
                ).first()
                if already:
                    continue

                artifact = TestArtifact(
                    test_id=existing.id,
                    timestamp=ts,
                    video_path=artifact_data.get('video_path'),
                    video_size_mb=artifact_data.get('video_size_mb', 0),
                    har_path=artifact_data.get('har_path'),
                    status=artifact_data.get('status'),
                )
                db.add(artifact)

            count += 1

        except Exception as e:
            print(f"  ERROR migrating {filepath}: {e}")

    return count


def migrate_workspace_ai_steps(workspace_id: int, ai_steps_dir: Path, owner_id: int, db):
    """Migrate JSON AI step files for a specific workspace."""
    if not ai_steps_dir.exists():
        return 0

    count = 0
    for filepath in ai_steps_dir.glob('*.json'):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            filename = filepath.name

            # Skip if already migrated
            existing = db.query(AiStep).filter(
                AiStep.workspace_id == workspace_id,
                AiStep.filename == filename
            ).first()

            if existing:
                print(f"  Skipped (already exists): {filename}")
                continue

            ai_step = AiStep(
                filename=filename,
                name=data.get('name', filename.replace('.json', '').replace('_', ' ')),
                steps=data.get('steps', ''),
                workspace_id=workspace_id,
                created_by=owner_id,
                created_at=parse_iso_datetime(data.get('created')) or datetime.utcnow(),
                updated_at=parse_iso_datetime(data.get('updated')) or datetime.utcnow(),
                last_run_status=data.get('last_run_status') or data.get('status'),
                last_run_time=parse_iso_datetime(data.get('last_run_time') or data.get('last_run')),
            )
            db.add(ai_step)
            count += 1
            print(f"  Migrated AI step: {filename}")

        except Exception as e:
            print(f"  ERROR migrating {filepath}: {e}")

    return count


def ensure_schema(database_url: str):
    """Add new columns to existing tables that create_all won't handle."""
    if 'sqlite' not in database_url:
        return

    import sqlite3
    # Extract path from sqlite:///path
    db_path = database_url.replace('sqlite:///', '')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add 'code' column to tests if missing
    cursor.execute('PRAGMA table_info(tests)')
    existing_cols = {row[1] for row in cursor.fetchall()}
    if 'code' not in existing_cols:
        cursor.execute('ALTER TABLE tests ADD COLUMN code TEXT')
        print("Added 'code' column to tests table")

    conn.commit()
    conn.close()


def main():
    print("=" * 60)
    print("Migration: JSON files -> SQLite database")
    print("=" * 60)

    # Ensure schema is up to date before init_db
    ensure_schema(Config.DATABASE_URL)

    # Initialize database (creates new tables)
    db_session = init_db(Config.DATABASE_URL)
    db = get_db_session()

    total_tests = 0
    total_ai_steps = 0

    # 1. Migrate workspace-scoped files
    workspaces_dir = Path(Config.USER_DATA_PATH) / 'workspaces'
    if workspaces_dir.exists():
        for ws_dir in sorted(workspaces_dir.iterdir()):
            if not ws_dir.is_dir():
                continue

            try:
                workspace_id = int(ws_dir.name)
            except ValueError:
                continue

            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not workspace:
                print(f"\nWARNING: Workspace directory {workspace_id} has no DB record, skipping")
                continue

            owner_id = workspace.owner_id
            print(f"\nWorkspace {workspace_id} ({workspace.name}):")

            tests_dir = ws_dir / 'saved_tests'
            tc = migrate_workspace_tests(workspace_id, tests_dir, owner_id, db)
            total_tests += tc

            ai_dir = ws_dir / 'ai_steps'
            ac = migrate_workspace_ai_steps(workspace_id, ai_dir, owner_id, db)
            total_ai_steps += ac

    # 2. Migrate legacy global files
    legacy_tests_dir = Path(__file__).parent / 'saved_tests'
    legacy_ai_dir = Path(__file__).parent / 'ai_steps'

    has_legacy_tests = legacy_tests_dir.exists() and any(legacy_tests_dir.glob('*.json'))
    has_legacy_ai = legacy_ai_dir.exists() and any(legacy_ai_dir.glob('*.json'))

    if has_legacy_tests or has_legacy_ai:
        # Find a target workspace for legacy files
        first_user = db.query(User).order_by(User.id).first()
        if first_user:
            default_ws = db.query(Workspace).filter(
                Workspace.owner_id == first_user.id
            ).order_by(Workspace.created_at).first()

            if default_ws:
                print(f"\nLegacy global files -> Workspace {default_ws.id} ({default_ws.name}):")

                if has_legacy_tests:
                    tc = migrate_workspace_tests(default_ws.id, legacy_tests_dir, first_user.id, db)
                    total_tests += tc

                if has_legacy_ai:
                    ac = migrate_workspace_ai_steps(default_ws.id, legacy_ai_dir, first_user.id, db)
                    total_ai_steps += ac
            else:
                print("\nWARNING: No workspace found for legacy files, skipping")
        else:
            print("\nWARNING: No users found, skipping legacy files")

    # Commit all changes
    db.commit()

    # Summary
    print("\n" + "=" * 60)
    print(f"Migration complete!")
    print(f"  Tests migrated:    {total_tests}")
    print(f"  AI steps migrated: {total_ai_steps}")

    # Verification
    db_test_count = db.query(Test).count()
    db_ai_count = db.query(AiStep).count()
    db_artifact_count = db.query(TestArtifact).count()
    print(f"\nDB totals:")
    print(f"  Tests:     {db_test_count}")
    print(f"  AI steps:  {db_ai_count}")
    print(f"  Artifacts: {db_artifact_count}")
    print("=" * 60)
    print("\nJSON files have NOT been deleted (kept as backup).")


if __name__ == '__main__':
    main()
