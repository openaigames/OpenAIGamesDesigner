"""Extract data-only ZIPs into a fresh directory, preserving relative dependencies."""
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

DATA_EXTENSIONS = {'.glb', '.gltf', '.obj', '.fbx', '.ply', '.stl', '.blend', '.usd', '.usdz',
                   '.png', '.jpg', '.jpeg', '.webp', '.tga', '.exr', '.hdr', '.dds', '.ktx2',
                   '.bin', '.mtl', '.txt', '.md', '.json', '.xml', '.csv', '.wav', '.ogg', '.mp3',
                   '.flac', '.ttf', '.otf', '.svg', '.tres', '.tscn', '.uasset', '.uexp', '.ubulk'}


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('File paths must be relative POSIX paths')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or str(path) in ('.', ''):
        raise ValueError('File path escapes its destination')
    for part in path.parts:
        if part.endswith((' ', '.')) or re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', part, re.I):
            raise ValueError('Unsupported portable filename')
    return path


def extract_zip(archive, destination, max_bytes=2 * 1024**3):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Extraction destination already exists')
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) > 20000 or sum(m.file_size for m in members) > max_bytes:
            raise ValueError('Archive exceeds extraction limit')
        seen = set()
        for entry in members:
            rel = relative_path(entry.filename.rstrip('/'))
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                raise ValueError('Encrypted archives and links require manual handling')
            if not entry.is_dir() and rel.suffix.lower() not in DATA_EXTENSIONS:
                raise ValueError('Archive contains code or an unsupported format; retain package for explicit engine import')
            key = str(rel).casefold()
            if key in seen:
                raise ValueError('Duplicate archive path')
            seen.add(key)
        destination.mkdir(parents=True)
        files = []
        for entry in members:
            target = destination / str(relative_path(entry.filename.rstrip('/')))
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(entry) as source, target.open('xb') as out:
                    shutil.copyfileobj(source, out)
                if target.stat().st_size:
                    files.append(target)
        return files
