#!/usr/bin/env python3
"""
Migration script to import existing tests into multi-user workspace structure.

This script:
1. Creates a default admin user (username: "admin", password: "changeme123")
2. Creates a "Legacy Tests" shared workspace owned by admin
3. Imports all existing tests from saved_tests/ directory
4. Copies artifacts from test_artifacts/ to new workspace structure
5. Creates database records for all imported tests

Run this script ONCE after setting up the database schema.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

# Import database models and config
from models import init_db, get_db_session, User, Workspace, WorkspaceType, Test, TestSource
from config import Config


def migrate_existing_tests():
    """Main migration function."""
    print("=" * 80)
    print("AutoGen Web Tester - Migration Script")
    print("=" * 80)
    print()

    # Initialize database
    print("1. Initializing database...")
    os.makedirs(Config.USER_DATA_PATH, exist_ok=True)
    os.makedirs(os.path.join(Config.USER_DATA_PATH, 'workspaces'), exist_ok=True)
    db_session = init_db(Config.DATABASE_URL)
    print("   ✓ Database initialized")
    print()

    # Check if admin user already exists
    admin_user = db_session.query(User).filter(User.username == 'admin').first()

    if admin_user:
        print("2. Admin user already exists - skipping user creation")
        print(f"   Username: {admin_user.username}")
        print(f"   Email: {admin_user.email}")
    else:
        # Create default admin user
        print("2. Creating default admin user...")
        admin_user = User(
            username='admin',
            email='admin@autogen-tester.local',
            is_active=True
        )
        admin_user.set_password('changeme123')  # Default password - user should change it
        db_session.add(admin_user)
        db_session.flush()

        print("   ✓ Admin user created:")
        print(f"     Username: admin")
        print(f"     Password: changeme123")
        print(f"     Email: admin@autogen-tester.local")
        print()
        print("   ⚠️  IMPORTANT: Change the admin password after first login!")
    print()

    # Check if Legacy Tests workspace already exists
    legacy_workspace = db_session.query(Workspace).filter(
        Workspace.name == 'Legacy Tests',
        Workspace.owner_id == admin_user.id
    ).first()

    if legacy_workspace:
        print("3. 'Legacy Tests' workspace already exists - skipping workspace creation")
        print(f"   Workspace ID: {legacy_workspace.id}")
    else:
        # Create "Legacy Tests" shared workspace
        print("3. Creating 'Legacy Tests' workspace...")
        legacy_workspace = Workspace(
            name='Legacy Tests',
            type=WorkspaceType.SHARED,
            owner_id=admin_user.id
        )
        db_session.add(legacy_workspace)
        db_session.flush()

        print(f"   ✓ Workspace created (ID: {legacy_workspace.id})")
    print()

    # Create workspace directory structure
    workspace_path = os.path.join(
        Config.USER_DATA_PATH,
        'workspaces',
        str(legacy_workspace.id)
    )

    print("4. Creating workspace directory structure...")
    os.makedirs(os.path.join(workspace_path, 'saved_tests'), exist_ok=True)
    os.makedirs(os.path.join(workspace_path, 'ai_steps'), exist_ok=True)
    os.makedirs(os.path.join(workspace_path, 'artifacts'), exist_ok=True)
    print(f"   ✓ Directory created: {workspace_path}")
    print()

    # Import existing tests from saved_tests/
    saved_tests_dir = Path(__file__).parent / 'saved_tests'

    if not saved_tests_dir.exists():
        print("5. No existing tests found in saved_tests/ - migration complete")
        db_session.commit()
        return

    test_files = list(saved_tests_dir.glob('*.json'))

    if not test_files:
        print("5. No test files found in saved_tests/ - migration complete")
        db_session.commit()
        return

    print(f"5. Importing {len(test_files)} tests from saved_tests/...")
    print()

    imported_count = 0
    skipped_count = 0

    for test_file in test_files:
        filename = test_file.name

        # Check if test already exists in database
        existing_test = db_session.query(Test).filter(
            Test.workspace_id == legacy_workspace.id,
            Test.filename == filename
        ).first()

        if existing_test:
            print(f"   ⏭  Skipping {filename} (already imported)")
            skipped_count += 1
            continue

        try:
            # Read test data
            with open(test_file, 'r') as f:
                test_data = json.load(f)

            # Create database record
            test = Test(
                filename=filename,
                name=test_data.get('name', filename.replace('.json', '')),
                workspace_id=legacy_workspace.id,
                source=TestSource.MANUAL,  # Legacy tests are manual
                created_by=admin_user.id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                last_run_status=test_data.get('last_status'),
                last_run_time=None,
                description=test_data.get('description', '')
            )
            db_session.add(test)

            # Copy test file to workspace
            dest_file = os.path.join(workspace_path, 'saved_tests', filename)
            shutil.copy2(test_file, dest_file)

            print(f"   ✓ Imported: {filename}")
            imported_count += 1

        except Exception as e:
            print(f"   ✗ Error importing {filename}: {e}")
            skipped_count += 1
            continue

    print()
    print(f"   Imported: {imported_count} tests")
    print(f"   Skipped: {skipped_count} tests")
    print()

    # Migrate artifacts if they exist
    artifacts_dir = Path(__file__).parent / 'test_artifacts'

    if artifacts_dir.exists():
        print("6. Migrating test artifacts...")
        workspace_artifacts_dir = os.path.join(workspace_path, 'artifacts')

        artifact_count = 0
        for test_dir in artifacts_dir.iterdir():
            if test_dir.is_dir():
                dest_dir = os.path.join(workspace_artifacts_dir, test_dir.name)

                if os.path.exists(dest_dir):
                    print(f"   ⏭  Skipping artifacts for {test_dir.name} (already migrated)")
                    continue

                try:
                    shutil.copytree(test_dir, dest_dir)
                    print(f"   ✓ Migrated artifacts: {test_dir.name}")
                    artifact_count += 1
                except Exception as e:
                    print(f"   ✗ Error migrating artifacts for {test_dir.name}: {e}")

        print()
        print(f"   Migrated artifacts for {artifact_count} tests")
    else:
        print("6. No test_artifacts/ directory found - skipping artifact migration")

    print()

    # Commit all changes
    db_session.commit()

    print("=" * 80)
    print("Migration Complete!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Start the web UI: python web_ui.py")
    print("2. Login with username: admin, password: changeme123")
    print("3. IMPORTANT: Change the admin password immediately!")
    print("4. All existing tests are now in the 'Legacy Tests' workspace")
    print()


if __name__ == '__main__':
    migrate_existing_tests()
