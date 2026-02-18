"""Supabase Storage helpers for uploading, downloading, and deleting test artifacts."""

from pathlib import Path
from supabase_client import get_supabase_client
from config import Config


def upload_artifact_dir(local_dir: Path, workspace_id: int, test_name: str, timestamp: str) -> dict:
    """Upload .webm and .har files from a local directory to Supabase Storage.

    Returns a dict with keys:
        video_path  — storage path for the video (or None)
        har_path    — storage path for the HAR file (or None)
        video_local — Path object of the local video file (for size calc)
    """
    sb = get_supabase_client()
    bucket = Config.SUPABASE_STORAGE_BUCKET
    prefix = f"{workspace_id}/{test_name}/{timestamp}"

    result: dict = {}

    video_files = list(local_dir.glob("*.webm")) + list(local_dir.glob("*.mp4"))
    if video_files:
        video_file = video_files[0]
        content_type = "video/mp4" if video_file.suffix == ".mp4" else "video/webm"
        storage_path = f"{prefix}/{video_file.name}"
        try:
            with open(video_file, 'rb') as f:
                sb.storage.from_(bucket).upload(
                    storage_path,
                    f.read(),
                    {"content-type": content_type},
                )
            result['video_path'] = storage_path
            result['video_local'] = video_file
            print(f"Uploaded video to storage: {storage_path}")
        except Exception as e:
            print(f"Warning: Failed to upload video: {e}")

    har_files = list(local_dir.glob("*.har"))
    if har_files:
        har_file = har_files[0]
        storage_path = f"{prefix}/{har_file.name}"
        try:
            with open(har_file, 'rb') as f:
                sb.storage.from_(bucket).upload(
                    storage_path,
                    f.read(),
                    {"content-type": "application/json"},
                )
            result['har_path'] = storage_path
            print(f"Uploaded HAR to storage: {storage_path}")
        except Exception as e:
            print(f"Warning: Failed to upload HAR: {e}")

    return result


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str | None:
    """Return a time-limited signed URL for a storage object, or None on error."""
    try:
        sb = get_supabase_client()
        bucket = Config.SUPABASE_STORAGE_BUCKET
        print(f"[get_signed_url] bucket={bucket}, path={storage_path}")
        response = sb.storage.from_(bucket).create_signed_url(storage_path, expires_in)
        print(f"[get_signed_url] response type={type(response)}, keys={list(response.keys()) if isinstance(response, dict) else 'N/A'}")
        if response and 'signedURL' in response:
            return response['signedURL']
        if response and 'signedUrl' in response:
            return response['signedUrl']
        print(f"[get_signed_url] No signedURL/signedUrl key found in response: {response}")
        return None
    except Exception as e:
        print(f"Warning: Failed to create signed URL for {storage_path}: {e}")
        return None


def delete_artifact(storage_path: str):
    """Remove a file from the Supabase Storage bucket."""
    try:
        sb = get_supabase_client()
        bucket = Config.SUPABASE_STORAGE_BUCKET
        sb.storage.from_(bucket).remove([storage_path])
        print(f"Deleted from storage: {storage_path}")
    except Exception as e:
        print(f"Warning: Failed to delete {storage_path} from storage: {e}")
