"""
Local file tree for Saved Tests and AI Steps under ~/.autogen/workspaces/<id>/.
Used for prototyping: folders and .py / .md files persisted on disk.
"""

import re
from pathlib import Path


# Allowed path: alphanumeric, spaces, -, _, /, and . for extensions (.py, .md)
_PATH_RE = re.compile(r"^[a-zA-Z0-9_\-\s/.]+$")
# No leading/trailing slashes or empty segments
def _validate_path(path: str) -> str:
    if not path or not isinstance(path, str):
        raise ValueError("Path is required")
    normalized = path.strip().strip("/")
    if ".." in normalized or normalized.startswith("/"):
        raise ValueError("Invalid path")
    if not _PATH_RE.match(normalized):
        raise ValueError("Path may only contain letters, numbers, spaces, -, _, /, and .")
    return normalized


def _resolve(root: Path, relative_path: str) -> Path:
    """Resolve relative_path under root; ensure result is inside root (no escape)."""
    path = _validate_path(relative_path)
    resolved = (root / path).resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved) + "/") and resolved != root_resolved:
        raise ValueError("Path escapes workspace root")
    return resolved


def _walk_tree(dir_path: Path, base_dir: Path, tree_type: str, ext: str) -> list:
    """Build nested list of {name, type, path?, children?} for directory."""
    result = []
    if not dir_path.is_dir():
        return result
    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return result
    for entry in entries:
        rel = entry.relative_to(base_dir)
        rel_str = str(rel).replace("\\", "/")
        if entry.is_dir():
            if entry.name == "artifacts":
                continue
            result.append({
                "name": entry.name,
                "type": "folder",
                "path": rel_str,
                "children": _walk_tree(entry, base_dir, tree_type, ext),
            })
        elif entry.is_file() and entry.suffix == ext:
            name = entry.stem
            result.append({
                "name": entry.name,
                "type": "file",
                "path": rel_str,
                "display_name": name.replace("_", " "),
            })
    return result


def list_tree(root: Path, tree_type: str) -> list:
    """
    List tree under root. tree_type is 'saved_tests' (.py) or 'ai_steps' (.md).
    Returns list of nodes: folders have children, files have path and display_name.
    """
    ext = ".py" if tree_type == "saved_tests" else ".md"
    root = Path(root).resolve()
    if not root.is_dir():
        return []
    return _walk_tree(root, root, tree_type, ext)


def get_file_content(root: Path, relative_path: str, tree_type: str) -> dict:
    """
    Read file at relative_path under root. Returns {name, code} for tests or {name, steps} for ai_steps.
    """
    ext = ".py" if tree_type == "saved_tests" else ".md"
    fp = _resolve(root, relative_path)
    if not fp.is_file():
        raise FileNotFoundError(f"Not a file: {relative_path}")
    if fp.suffix != ext:
        raise ValueError(f"Expected {ext} file")
    text = fp.read_text(encoding="utf-8")
    name = fp.stem.replace("_", " ")
    if tree_type == "saved_tests":
        return {"name": name, "code": text, "filename": fp.name, "path": relative_path}
    return {"name": name, "steps": text, "filename": fp.name, "path": relative_path}


def create_folder(root: Path, relative_path: str) -> None:
    """Create directory at relative_path (and parents)."""
    fp = _resolve(root, relative_path)
    if fp.exists() and not fp.is_dir():
        raise ValueError("Path exists and is not a folder")
    fp.mkdir(parents=True, exist_ok=True)


def create_or_update_file(
    root: Path,
    relative_path: str,
    tree_type: str,
    *,
    name: str = None,
    code: str = None,
    steps: str = None,
) -> dict:
    """
    Create or update a file. For saved_tests pass name+code; for ai_steps pass name+steps.
    relative_path must end with .py (saved_tests) or .md (ai_steps).
    """
    ext = ".py" if tree_type == "saved_tests" else ".md"
    path = _validate_path(relative_path)
    if not path.endswith(ext):
        raise ValueError(f"Path must end with {ext}")
    fp = _resolve(root, path)
    content = code if tree_type == "saved_tests" else steps
    if content is None:
        content = ""
    display_name = (name or "").strip() or Path(path).stem.replace("_", " ")
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    return {
        "path": path,
        "name": display_name,
        "filename": fp.name,
    }


def delete_path(root: Path, relative_path: str) -> None:
    """Delete file or directory at relative_path (recursive for dirs)."""
    fp = _resolve(root, relative_path)
    if not fp.exists():
        raise FileNotFoundError(f"Not found: {relative_path}")
    if fp.is_dir():
        import shutil
        shutil.rmtree(fp)
    else:
        fp.unlink()


def move_path(root: Path, from_path: str, to_path: str, tree_type: str) -> None:
    """
    Move a file or folder from from_path to to_path under root.
    For folders, moves recursively. Copies .meta.json for files.
    Raises ValueError if to_path exists, or if moving a folder into its own descendant.
    """
    ext = ".py" if tree_type == "saved_tests" else ".md"
    from_norm = _validate_path(from_path)
    to_norm = _validate_path(to_path)
    if from_norm == to_norm:
        raise ValueError("Source and destination are the same")

    root = Path(root).resolve()
    fp_from = _resolve(root, from_norm)
    fp_to = _resolve(root, to_norm)

    if not fp_from.exists():
        raise FileNotFoundError(f"Not found: {from_path}")

    if fp_to.exists():
        raise ValueError("Destination already exists")

    if fp_from.is_file():
        if not fp_from.suffix == ext:
            raise ValueError(f"Expected {ext} file")
        data = get_file_content(root, from_norm, tree_type)
        if tree_type == "saved_tests":
            create_or_update_file(root, to_norm, tree_type, name=data.get("name"), code=data.get("code", ""))
        else:
            create_or_update_file(root, to_norm, tree_type, name=data.get("name"), steps=data.get("steps", ""))
        meta = get_last_run_meta(root, from_norm)
        if meta:
            write_last_run_meta(root, to_norm, status=meta.get("last_run_status"), last_run_time=meta.get("last_run_time"))
        meta_path_from = fp_from.parent / (fp_from.stem + ".meta.json")
        if meta_path_from.is_file():
            meta_path_from.unlink()
        delete_path(root, from_norm)
        return

    if fp_from.is_dir():
        if to_norm == from_norm or to_norm.startswith(from_norm + "/"):
            raise ValueError("Cannot move a folder into itself or a descendant")
        create_folder(root, to_norm)
        try:
            entries = sorted(fp_from.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            delete_path(root, from_norm)
            return
        for entry in entries:
            name = entry.name
            move_path(root, from_norm + "/" + name, to_norm + "/" + name, tree_type)
        delete_path(root, from_norm)


def get_last_run_meta(root: Path, relative_path: str) -> dict | None:
    """Read optional meta JSON for last run status (sidecar next to file)."""
    path = _validate_path(relative_path)
    fp = _resolve(root, path)
    if not fp.is_file():
        return None
    meta_path = fp.parent / (fp.stem + ".meta.json")
    if not meta_path.is_file():
        return None
    import json
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_last_run_meta(root: Path, relative_path: str, status: str = None, last_run_time: str = None) -> None:
    """Write optional meta JSON for last run status."""
    path = _validate_path(relative_path)
    fp = _resolve(root, path)
    meta_path = fp.parent / (fp.stem + ".meta.json")
    import json
    data = {}
    try:
        if meta_path.is_file():
            data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    if status is not None:
        data["last_run_status"] = status
    if last_run_time is not None:
        data["last_run_time"] = last_run_time
    meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
