#!/usr/bin/env python3
"""
Migrate file-based tests to workspace-scoped database tests.
"""
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from models import init_db, get_db_session, Test, TestSource
from config import Config

# Initialize database
init_db(Config.DATABASE_URL)
db = get_db_session()

# Configuration
OLD_TESTS_DIR = Path(__file__).parent / 'saved_tests'
WORKSPACE_ID = 3  # "Sunny Staging" workspace
USER_ID = 1  # Owner user ID

def migrate_tests():
    """Migrate all tests from saved_tests/ to the database and workspace directory."""

    if not OLD_TESTS_DIR.exists():
        print(f"❌ Old tests directory not found: {OLD_TESTS_DIR}")
        return

    # Get workspace directory for tests
    workspace_dir = Path(Config.USER_DATA_PATH) / 'workspaces' / str(WORKSPACE_ID) / 'tests'
    workspace_dir.mkdir(parents=True, exist_ok=True)

    migrated = 0
    skipped = 0

    print(f"📦 Migrating tests from {OLD_TESTS_DIR} to workspace {WORKSPACE_ID}...")
    print()

    for test_file in OLD_TESTS_DIR.glob('*.json'):
        try:
            # Read test data
            with open(test_file, 'r') as f:
                test_data = json.load(f)

            filename = test_file.name
            name = test_data.get('name', filename.replace('.json', ''))
            code = test_data.get('code', '')
            source = test_data.get('source', 'manual')

            # Map source to TestSource enum
            source_map = {
                'ai': TestSource.AI,
                'codegen': TestSource.CODEGEN,
                'ai_step': TestSource.AI,
                'manual': TestSource.MANUAL
            }
            test_source = source_map.get(source, TestSource.MANUAL)

            # Check if test already exists in workspace
            existing = db.query(Test).filter_by(
                workspace_id=WORKSPACE_ID,
                filename=filename
            ).first()

            if existing:
                print(f"⏭️  Skipping {filename} (already exists in database)")
                skipped += 1
                continue

            # Parse timestamps
            last_run_time = None
            if test_data.get('last_run_time'):
                try:
                    # Try parsing ISO format string
                    last_run_time = datetime.fromisoformat(test_data['last_run_time'])
                except (ValueError, TypeError):
                    try:
                        # Fallback to timestamp number
                        last_run_time = datetime.fromtimestamp(float(test_data['last_run_time']))
                    except (ValueError, TypeError):
                        pass  # Leave as None if can't parse

            # Create database record
            test = Test(
                filename=filename,
                name=name,
                workspace_id=WORKSPACE_ID,
                source=test_source,
                created_by=USER_ID,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_run_status=test_data.get('last_run_status'),
                last_run_time=last_run_time
            )
            db.add(test)

            # Copy file to workspace directory
            dest_file = workspace_dir / filename
            shutil.copy2(test_file, dest_file)

            print(f"✅ Migrated: {name} ({filename})")
            migrated += 1

        except Exception as e:
            print(f"❌ Error migrating {test_file.name}: {e}")
            continue

    # Commit all changes
    try:
        db.commit()
        print()
        print(f"🎉 Migration complete!")
        print(f"   ✅ Migrated: {migrated} tests")
        print(f"   ⏭️  Skipped: {skipped} tests")
        print()
        print(f"📁 Tests are now in workspace directory: {workspace_dir}")
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to commit changes: {e}")

if __name__ == '__main__':
    migrate_tests()
