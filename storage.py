"""Local disk storage for test artifacts.

Each test has exactly one recording at a fixed path inside the workspace:
  ~/.autogen/workspaces/<workspace_name>/saved_tests/artifacts/<test_name>/recording.webm
  ~/.autogen/workspaces/<workspace_name>/saved_tests/artifacts/<test_name>/network.har

Previous files are overwritten on each run — no history kept.
"""

import shutil
from pathlib import Path

from config import Config


def save_artifact_dir(local_dir: Path, workspace_name: str, test_name: str) -> dict:
    """Move the latest recording from a Playwright temp dir into the workspace artifacts dir.

    Always saves to a fixed path, overwriting any previous recording for this test.

    Returns:
        video_path  — path relative to AUTOGEN_WORKSPACES_DIR (or None)
        har_path    — path relative to AUTOGEN_WORKSPACES_DIR (or None)
        trace_path  — path relative to AUTOGEN_WORKSPACES_DIR (or None)
        video_local — absolute Path to the saved video file (for size calc)
    """
    dest_dir = Config.AUTOGEN_WORKSPACES_DIR / workspace_name / "saved_tests" / "artifacts" / test_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {}

    video_files = list(local_dir.glob("*.webm")) + list(local_dir.glob("*.mp4"))
    if video_files:
        dest = dest_dir / "recording.webm"
        dest.unlink(missing_ok=True)
        shutil.move(str(video_files[0]), str(dest))
        result["video_path"] = f"{workspace_name}/saved_tests/artifacts/{test_name}/recording.webm"
        result["video_local"] = dest
        print(f"Saved video: {dest}")

    har_files = list(local_dir.glob("*.har"))
    if har_files:
        dest = dest_dir / "network.har"
        dest.unlink(missing_ok=True)
        shutil.move(str(har_files[0]), str(dest))
        result["har_path"] = f"{workspace_name}/saved_tests/artifacts/{test_name}/network.har"
        print(f"Saved HAR: {dest}")

    trace_files = list(local_dir.glob("trace.zip"))
    if trace_files:
        dest = dest_dir / "trace.zip"
        dest.unlink(missing_ok=True)
        shutil.move(str(trace_files[0]), str(dest))
        result["trace_path"] = f"{workspace_name}/saved_tests/artifacts/{test_name}/trace.zip"
        print(f"Saved trace: {dest}")

    return result
