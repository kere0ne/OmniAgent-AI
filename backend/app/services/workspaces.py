import fnmatch, os, shutil, zipfile
from pathlib import Path
from ..config import CFG

class PathError(Exception): pass

def ws_root(user_id: int, workspace_id: int) -> Path:
    return CFG.DATA_DIR / "workspaces" / f"u{user_id}" / f"ws{workspace_id}"

def ensure_ws(user_id: int, workspace_id: int) -> Path:
    p = ws_root(user_id, workspace_id)
    p.mkdir(parents=True, exist_ok=True)
    return p

def resolve_safe(user_id: int, workspace_id: int, rel: str) -> Path:
    root = ensure_ws(user_id, workspace_id)
    p = (root / rel.lstrip("/")).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise PathError("path escapes the workspace")
    return p

def ws_disk_usage(user_id: int, workspace_id: int) -> int:
    root = ws_root(user_id, workspace_id)
    total = 0
    if root.exists():
        for f in root.rglob("*"):
            try:
                if f.is_file(): total += f.stat().st_size
            except OSError: pass
    return total

def list_tree(root: Path, base="") -> list[dict]:
    out = []
    try:
        entries = sorted(os.scandir(root), key=lambda e: (not e.is_dir(), e.name.lower()))
    except (NotADirectoryError, FileNotFoundError):
        return out
    for e in entries:
        rel = f"{base}{e.name}"
        if e.is_dir(follow_symlinks=False):
            out.append({"path": rel, "type": "dir"})
            out += list_tree(Path(e.path), rel + "/")
        else:
            try: size = e.stat(follow_symlinks=False).st_size
            except OSError: size = 0
            out.append({"path": rel, "type": "file", "size": size})
    return out

def safe_extract_zip(zip_path: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    dest_res = str(dest.resolve()) + os.sep
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts or (name[1:3] == ":\\" if len(name) > 2 else False):
                raise ValueError(f"unsafe path in archive: {name}")
            target = (dest / name).resolve()
            if not str(target).startswith(dest_res):
                raise ValueError(f"unsafe path in archive: {name}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)

IGNORED = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", ".next"}

def find_files(root: Path, pattern: str, base="") -> list[str]:
    hits = []
    try: entries = os.scandir(root)
    except (NotADirectoryError, FileNotFoundError): return hits
    for e in entries:
        if e.name in IGNORED: continue
        rel = f"{base}{e.name}"
        if e.is_dir(follow_symlinks=False):
            hits += find_files(Path(e.path), pattern, rel + "/")
        elif fnmatch.fnmatch(e.name, pattern):
            hits.append(rel)
    return hits[:500]
