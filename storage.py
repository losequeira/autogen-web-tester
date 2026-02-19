"""Local disk storage for test artifacts.

Artifacts are saved under ~/.autogen/artifacts/{workspace_id}/{test_name}/{timestamp}/.
video_path / har_path stored in the DB are paths relative to ARTIFACTS_DIR so they
remain valid even if the home directory changes.
"""

import shutil
from pathlib import Path

from config import Config


def save_artifact_dir(local_dir: Path, workspace_id: int, test_name: str, timestamp: str) -> dict:
    """Move .webm/.mp4 and .har files from a temp dir into ~/.autogen/artifacts/.

    Returns a dict with keys:
        video_path  — path relative to ARTIFACTS_DIR stored in DB (or None)
        har_path    — path relative to ARTIFACTS_DIR stored in DB (or None)
        video_local — absolute Path to the saved video file (for size calc)
    """
    dest_dir = Config.ARTIFACTS_DIR / str(workspace_id) / test_name / timestamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {}

    video_files = list(local_dir.glob("*.webm")) + list(local_dir.glob("*.mp4"))
    if video_files:
        video_file = video_files[0]
        dest = dest_dir / video_file.name
        shutil.move(str(video_file), str(dest))
        result["video_path"] = str(dest.relative_to(Config.ARTIFACTS_DIR))
        result["video_local"] = dest
        print(f"Saved video: {dest}")

    har_files = list(local_dir.glob("*.har"))
    if har_files:
        har_file = har_files[0]
        dest = dest_dir / har_file.name
        shutil.move(str(har_file), str(dest))
        result["har_path"] = str(dest.relative_to(Config.ARTIFACTS_DIR))
        print(f"Saved HAR: {dest}")

    return result


def delete_artifact(relative_path: str) -> None:
    """Delete a local artifact file (path relative to ARTIFACTS_DIR)."""
    path = Config.ARTIFACTS_DIR / relative_path
    try:
        if path.exists():
            path.unlink()
            print(f"Deleted artifact: {path}")
            # Remove the timestamp dir if now empty, then test dir, etc.
            for parent in (path.parent, path.parent.parent, path.parent.parent.parent):
                try:
                    parent.rmdir()
                except OSError:
                    break
    except Exception as e:
        print(f"Warning: Failed to delete {path}: {e}")
