"""
Data access layer for tests, AI steps, and artifacts.

Replaces JSON file I/O with SQLite database queries.
All functions return plain dicts ready for jsonify().
"""

from datetime import datetime
from pathlib import Path
from models import AiStep, Test, TestArtifact, TestSource, Workspace, get_db_session


def sanitize_filename(name: str) -> str:
    """Generate a filesystem-safe filename from a display name."""
    filename = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    return filename.replace(' ', '_') + '.json'


# ========== TESTS ==========

def get_tests(workspace_id: int) -> list[dict]:
    """List all tests in a workspace."""
    db = get_db_session()
    tests = db.query(Test).filter(
        Test.workspace_id == workspace_id
    ).order_by(Test.created_at.desc()).all()

    return [_test_summary(t) for t in tests]


def get_test(workspace_id: int, filename: str) -> dict | None:
    """Get a single test by workspace + filename, including code."""
    db = get_db_session()
    test = db.query(Test).filter(
        Test.workspace_id == workspace_id,
        Test.filename == filename
    ).first()

    if not test:
        return None

    return {
        'filename': test.filename,
        'name': test.name,
        'code': test.code,
        'source': test.source.value,
        'created': test.created_at.isoformat() if test.created_at else None,
        'updated': test.updated_at.isoformat() if test.updated_at else None,
        'last_run_status': test.last_run_status,
        'last_run_time': test.last_run_time.isoformat() if test.last_run_time else None,
        'artifacts': [a.to_dict() for a in test.artifacts],
    }


def create_test(workspace_id: int, name: str, code: str, source: str, user_id: int) -> dict:
    """Create a test. Returns dict with filename."""
    db = get_db_session()
    filename = sanitize_filename(name)

    # Check for duplicates
    existing = db.query(Test).filter(
        Test.workspace_id == workspace_id,
        Test.filename == filename
    ).first()
    if existing:
        raise ValueError('Test with this name already exists')

    source_enum = {'ai': TestSource.AI, 'codegen': TestSource.CODEGEN}.get(source, TestSource.MANUAL)

    test = Test(
        filename=filename,
        name=name,
        code=code,
        workspace_id=workspace_id,
        source=source_enum,
        created_by=user_id,
    )
    db.add(test)
    db.commit()

    return {'message': 'Test created successfully', 'filename': filename}


def update_test(workspace_id: int, filename: str, **fields) -> dict | None:
    """Partial update of test fields. Returns updated dict or None if not found."""
    db = get_db_session()
    test = db.query(Test).filter(
        Test.workspace_id == workspace_id,
        Test.filename == filename
    ).first()

    if not test:
        return None

    for key, value in fields.items():
        if key == 'name':
            test.name = value
        elif key == 'code':
            test.code = value
        elif key == 'last_run_status':
            test.last_run_status = value
        elif key == 'last_run_time':
            if isinstance(value, str):
                test.last_run_time = datetime.fromisoformat(value)
            else:
                test.last_run_time = value
        elif key == 'description':
            test.description = value
        elif key == 'source':
            test.source = {'ai': TestSource.AI, 'codegen': TestSource.CODEGEN}.get(value, TestSource.MANUAL)

    test.updated_at = datetime.utcnow()
    db.commit()

    return {'message': 'Test updated successfully'}


def delete_test(workspace_id: int, filename: str) -> bool:
    """Delete a test and its artifact metadata. Returns True if found."""
    db = get_db_session()
    test = db.query(Test).filter(
        Test.workspace_id == workspace_id,
        Test.filename == filename
    ).first()

    if not test:
        return False

    db.delete(test)  # cascade deletes TestArtifact rows
    db.commit()
    return True


# ========== TEST ARTIFACTS ==========

def get_test_artifacts(workspace_id: int, filename: str) -> list[dict] | None:
    """Get artifact metadata for a test. Returns None if test not found."""
    db = get_db_session()
    test = db.query(Test).filter(
        Test.workspace_id == workspace_id,
        Test.filename == filename
    ).first()

    if not test:
        return None

    return [a.to_dict() for a in test.artifacts]


def add_test_artifact(workspace_id: int, filename: str, artifact_dir: Path, status: str):
    """Add artifact metadata after a test run. Discovers binary files in artifact_dir."""
    db = get_db_session()
    test = db.query(Test).filter(
        Test.workspace_id == workspace_id,
        Test.filename == filename
    ).first()

    if not test:
        # Try AI step filename as fallback — some tests run from AI steps
        # and store artifacts under the AI step filename
        print(f"Warning: Test not found for artifact update: {filename}")
        return

    # Discover binary files
    video_files = list(artifact_dir.glob("*.webm"))
    video_path = video_files[0].relative_to(Path(__file__).parent) if video_files else None
    video_size_mb = video_files[0].stat().st_size / (1024 * 1024) if video_files else 0

    har_files = list(artifact_dir.glob("*.har"))
    har_path = har_files[0].relative_to(Path(__file__).parent) if har_files else None

    timestamp = artifact_dir.name

    artifact = TestArtifact(
        test_id=test.id,
        timestamp=timestamp,
        video_path=str(video_path) if video_path else None,
        video_size_mb=round(video_size_mb, 2),
        har_path=str(har_path) if har_path else None,
        status=status,
    )
    db.add(artifact)

    # Update test run metadata
    test.last_run_status = status
    test.last_run_time = datetime.utcnow()
    test.updated_at = datetime.utcnow()

    db.commit()

    print(f"Updated test metadata with artifact: {video_path}")

    # Cleanup old artifacts (keep last 10)
    _cleanup_old_artifacts(test, keep_last_n=10)


def _cleanup_old_artifacts(test: Test, keep_last_n: int = 10):
    """Remove old artifact DB rows and disk files, keeping only the last N."""
    import shutil

    db = get_db_session()
    artifacts = db.query(TestArtifact).filter(
        TestArtifact.test_id == test.id
    ).order_by(TestArtifact.created_at.desc()).all()

    if len(artifacts) <= keep_last_n:
        return

    for old_artifact in artifacts[keep_last_n:]:
        # Try to remove on-disk files
        if old_artifact.video_path:
            video_dir = Path(__file__).parent / Path(old_artifact.video_path).parent
            if video_dir.exists():
                try:
                    shutil.rmtree(video_dir)
                    print(f"Cleaned up old artifact: {video_dir}")
                except Exception as e:
                    print(f"Warning: Could not remove old artifacts: {e}")

        db.delete(old_artifact)

    db.commit()


# ========== AI STEPS ==========

def get_ai_steps(workspace_id: int) -> list[dict]:
    """List all AI steps in a workspace."""
    db = get_db_session()
    steps = db.query(AiStep).filter(
        AiStep.workspace_id == workspace_id
    ).order_by(AiStep.created_at.desc()).all()

    return [{
        'filename': s.filename,
        'name': s.name,
        'created': s.created_at.isoformat() if s.created_at else None,
        'last_run_status': s.last_run_status,
        'last_run_time': s.last_run_time.isoformat() if s.last_run_time else None,
    } for s in steps]


def get_ai_step(workspace_id: int, filename: str) -> dict | None:
    """Get a single AI step including steps content."""
    db = get_db_session()
    step = db.query(AiStep).filter(
        AiStep.workspace_id == workspace_id,
        AiStep.filename == filename
    ).first()

    if not step:
        return None

    return {
        'filename': step.filename,
        'name': step.name,
        'steps': step.steps,
        'created': step.created_at.isoformat() if step.created_at else None,
        'updated': step.updated_at.isoformat() if step.updated_at else None,
        'last_run': step.last_run_time.isoformat() if step.last_run_time else None,
        'last_run_status': step.last_run_status,
        'last_run_time': step.last_run_time.isoformat() if step.last_run_time else None,
        'status': step.last_run_status,
    }


def create_ai_step(workspace_id: int, name: str, steps: str, user_id: int) -> dict:
    """Create an AI step. Returns dict with filename."""
    db = get_db_session()
    filename = sanitize_filename(name)

    existing = db.query(AiStep).filter(
        AiStep.workspace_id == workspace_id,
        AiStep.filename == filename
    ).first()
    if existing:
        raise ValueError('AI step with this name already exists')

    ai_step = AiStep(
        filename=filename,
        name=name,
        steps=steps,
        workspace_id=workspace_id,
        created_by=user_id,
    )
    db.add(ai_step)
    db.commit()

    return {'success': True, 'filename': filename}


def update_ai_step(workspace_id: int, filename: str, **fields) -> dict | None:
    """Partial update of AI step fields. Returns updated dict or None if not found."""
    db = get_db_session()
    step = db.query(AiStep).filter(
        AiStep.workspace_id == workspace_id,
        AiStep.filename == filename
    ).first()

    if not step:
        return None

    for key, value in fields.items():
        if key == 'name':
            step.name = value
        elif key == 'steps':
            step.steps = value
        elif key == 'last_run_status':
            step.last_run_status = value
        elif key in ('last_run', 'last_run_time'):
            if isinstance(value, str):
                step.last_run_time = datetime.fromisoformat(value)
            else:
                step.last_run_time = value
        elif key == 'status':
            step.last_run_status = value

    step.updated_at = datetime.utcnow()
    db.commit()

    return {'success': True}


def delete_ai_step(workspace_id: int, filename: str) -> bool:
    """Delete an AI step. Returns True if found."""
    db = get_db_session()
    step = db.query(AiStep).filter(
        AiStep.workspace_id == workspace_id,
        AiStep.filename == filename
    ).first()

    if not step:
        return False

    db.delete(step)
    db.commit()
    return True


# ========== RECORDINGS ==========

def get_recent_recordings(workspace_id: int, limit: int = 20) -> list[dict]:
    """Get recent test artifacts with video recordings for a workspace."""
    db = get_db_session()
    artifacts = (
        db.query(TestArtifact)
        .join(Test, TestArtifact.test_id == Test.id)
        .filter(
            Test.workspace_id == workspace_id,
            TestArtifact.video_path.isnot(None),
            TestArtifact.video_path != 'null',
            TestArtifact.video_path != '',
        )
        .order_by(TestArtifact.created_at.desc())
        .limit(limit)
        .all()
    )

    return [{
        'test_filename': a.test.filename,
        'test_name': a.test.name,
        'timestamp': a.timestamp,
        'video_path': a.video_path,
        'video_size_mb': a.video_size_mb,
        'har_path': a.har_path,
        'status': a.status,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    } for a in artifacts]


# ========== HELPERS ==========

def get_default_workspace_id(user_id: int) -> int | None:
    """Get the user's first owned workspace (used by legacy endpoints)."""
    db = get_db_session()
    workspace = db.query(Workspace).filter(
        Workspace.owner_id == user_id
    ).order_by(Workspace.created_at).first()
    return workspace.id if workspace else None


def _test_summary(test: Test) -> dict:
    """Convert a Test to a summary dict (no code, for list views)."""
    return {
        'filename': test.filename,
        'name': test.name,
        'created': test.created_at.isoformat() if test.created_at else None,
        'source': test.source.value,
        'last_run_status': test.last_run_status,
        'last_run_time': test.last_run_time.isoformat() if test.last_run_time else None,
        'artifacts': [a.to_dict() for a in test.artifacts],
    }
